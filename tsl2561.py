# -*- coding: utf-8 -*-
"""
From https://github.com/mchobby/esp8266-upy/blob/master/tsl2561/tsl2561.py
simplifié pour Python 3 et utilisation du bus smb au lieu de i2c.

Copyright (C) 2018  christophe Nanteuil <christophe.nanteuil@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import time

_COMMAND_BIT = 0x80
_WORD_BIT = 0x20
_CLEAR_BIT = 0x40

_REGISTER_CONTROL = 0x00
_REGISTER_TIMING = 0x01
_REGISTER_THRESHHOLD_MIN = 0x02
_REGISTER_THRESHHOLD_MAX = 0x04
_REGISTER_INTERRUPT = 0x06
_REGISTER_ID = 0x0A
_REGISTER_CHANNEL0 = 0x0C
_REGISTER_CHANNEL1 = 0x0E

_CONTROL_POWERON = 0x03
_CONTROL_POWEROFF = 0x00

_INTERRUPT_NONE = 0x00
_INTERRUPT_LEVEL = 0x10

_INTEGRATION_TIME = {
#  time     hex     wait    clip    min     max     scale
    13:     (0x00,  15,     4900,   100,    4850,   0x7517),
    101:    (0x01,  120,    37000,  200,    36000,  0x0FE7),
    402:    (0x02,  450,    65000,  500,    63000,  1 << 10),
    0:      (0x03,  0,      0,      0,      0,      0),
}


class TSL2561:
    _LUX_SCALE = (
    #       K       B       M
        (0x0040, 0x01f2, 0x01be),
        (0x0080, 0x0214, 0x02d1),
        (0x00c0, 0x023f, 0x037b),
        (0x0100, 0x0270, 0x03fe),
        (0x0138, 0x016f, 0x01fc),
        (0x019a, 0x00d2, 0x00fb),
        (0x029a, 0x0018, 0x0012),
    )

    def __init__(self, bus, address=0x39):
        self.bus = bus
        self.address = address
        sensor_id = self.sensor_id()
        if not sensor_id & 0x10:
            raise RuntimeError("bad sensor id 0x{:x}".format(sensor_id))
        self._active = self._register8(_REGISTER_CONTROL) != 0
        self._gain, self._integration_time = self._get_gain_and_time()

    def _register16(self, register, value=None):
        register |= _COMMAND_BIT | _WORD_BIT
        if value is None:
            return self.bus.read_word_data(self.address, register)
        self.bus.write_word_data(self.address, register, value)

    def _register8(self, register, value=None):
        register |= _COMMAND_BIT
        if value is None:
            return self.bus.read_byte_data(self.address, register)
        self.bus.write_byte_data(self.address, register, value)

    def active(self, value=None):
        if value is None:
            return self._active
        value = bool(value)
        if value != self._active:
            self._active = value
            self._register8(_REGISTER_CONTROL,
                _CONTROL_POWERON if value else _CONTROL_POWEROFF)

    def gain(self, value=None):
        if value is None:
            return self._gain
        if value not in (1, 16):
            raise ValueError("gain must be either 1x or 16x")
        self._gain = value
        self._update_gain_and_time()

    def integration_time(self, value=None):
        if value is None:
            return self._integration_time
        if value not in _INTEGRATION_TIME:
            raise ValueError("integration time must be 0, 13ms, 101ms or 402ms")
        self._integration_time = value
        self._update_gain_and_time()

    def _update_gain_and_time(self):
        was_active = self.active()
        self.active(True)
        self._register8(_REGISTER_TIMING,
            _INTEGRATION_TIME[self._integration_time][0] |
            {1: 0x00, 16: 0x10}[self._gain]);
        self.active(was_active)

    def _get_gain_and_time(self):
        result = self._register8(_REGISTER_TIMING)
        if (result & 0xF0) == 0:
            gain = 1
        else:
            gain =  16
        integration_time = next(key for key,(value, _, _, _, _, _)  in _INTEGRATION_TIME.items() if value == (result & 0x0F))
        return gain, integration_time

    def sensor_id(self):
        return self._register8(_REGISTER_ID)

    def _read(self):
        was_active = self.active()
        self.active(True)
        if not was_active:
            # if the sensor was off, wait for measurement
            time.sleep(_INTEGRATION_TIME[self._integration_time][1] / 1000)
        broadband = self._register16(_REGISTER_CHANNEL0)
        ir = self._register16(_REGISTER_CHANNEL1)
        self.active(was_active)
        return broadband, ir

    def _lux(self, channels):
        if self._integration_time == 0:
            raise ValueError(
                "can't calculate lux with manual integration time")
        broadband, ir = channels
        clip = _INTEGRATION_TIME[self._integration_time][2]
        if broadband > clip or ir > clip:
            raise ValueError("sensor saturated")
        scale = _INTEGRATION_TIME[self._integration_time][5] / self._gain
        channel0 = (broadband * scale) / 1024
        channel1 = (ir * scale) / 1024
        ratio = (((channel1 * 1024) / channel0 if channel0 else 0) + 1) / 2
        for k, b, m in self._LUX_SCALE:
            if ratio <= k:
                break
        else:
            b = 0
            m = 0
        return (max(0, channel0 * b - channel1 * m) + 8192) / 16384

    def read(self, autogain=False, raw=False):
        broadband, ir = self._read()
        if autogain:
            if self._integration_time == 0:
                raise ValueError(
                    "can't do autogain with manual integration time")
            new_gain = self._gain
            if broadband < _INTEGRATION_TIME[self._integration_time][3]:
                new_gain = 16
            elif broadband > _INTEGRATION_TIME[self._integration_time][4]:
                new_gain = 1
            if new_gain != self._gain:
                self.gain(new_gain)
                broadband, ir = self._read()
        if raw:
            return broadband, ir
        return self._lux((broadband, ir))

    def threshold(self, cycles=None, min_value=None, max_value=None):
        if min_value is None and max_value is None and cycles is None:
            min_value = self._register16(_REGISTER_THRESHHOLD_MIN)
            max_value = self._register16(_REGISTER_THRESHHOLD_MAX)
            cycles = self._register8(_REGISTER_INTERRUPT)
            if not cycles & _INTERRUPT_LEVEL:
                cycles = -1
            else:
                cycles &= 0x0f
            return cycles, min_value, max_value
        was_active = self.active()
        self.active(True)
        if min_value is not None:
            self._register16(_REGISTER_THRESHHOLD_MIN, int(min_value))
        if max_value is not None:
            self._register16(_REGISTER_THRESHHOLD_MAX, int(max_value))
        if cycles is not None:
            if cycles == -1:
                self._register8(_REGISTER_INTERRUPT, _INTERRUPT_NONE)
            else:
                self._register8(_REGISTER_INTERRUPT,
                    min(15, max(0, int(cycles))) | _INTERRUPT_LEVEL)
        self.active(was_active)

    def interrupt(self, value):
        if value or value is None:
            raise ValueError("can only clear the interrupt")
        self.bus.write_byte_data(self.address,
            _CLEAR_BIT | _REGISTER_CONTROL, b'\x00')


# Those packages are identical.
TSL2561T = TSL2561
TSL2561FN = TSL2561
TSL2561CL = TSL2561


class TSL2561CS(TSL2561):
    # This package has different lux scale.
    _LUX_SCALE = (
    #       K       B       M
        (0x0043, 0x0204, 0x01ad),
        (0x0085, 0x0228, 0x02c1),
        (0x00c8, 0x0253, 0x0363),
        (0x010a, 0x0282, 0x03df),
        (0x014d, 0x0177, 0x01dd),
        (0x019a, 0x0101, 0x0127),
        (0x029a, 0x0037, 0x002b),
    )
