#!/home/pi/.Envs/garage/bin/python
# -*- coding: utf-8 -*-
"""
Serveur HTTP minimal pour obtenir la mesure de luminosité.
Peut être placé derrière un stunnel pour assurer le contrôle d'accès.

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
from http.server import BaseHTTPRequestHandler, HTTPServer
import configparser
from smbus2 import SMBus
from tsl2561 import TSL2561
import sys

ERR_I2C = 1
ERR_TSL = 2
ERR_CONFIG = 3
FICH_CONFIG = "/etc/garage.conf"


class mon_serveur(BaseHTTPRequestHandler):

    def serve_image(self, filename):
        if 'garage' in filename:
            filename = '/var/log/garage' + filename
        else:
            filename = '.' + filename
        try:
            with open(filename, mode='rb') as fich:
                contenu = fich.read()
        except FileNotFoundError:
            self.send_response(404)
            return
        self.send_response(200)
        self.send_header("Content-type", "image/png")
        self.send_header("Content-length", len(contenu))
        self.end_headers()
        self.wfile.write(contenu)

    def do_GET(self):
        if self.path in ('/favicon.ico', '/garage_annee.png',
            '/garage_jour.png', '/garage_mois.png'):
            return self.serve_image(self.path)

        if self.path != '/':
            self.send_response(404)
            return

        # envoi code status
        self.send_response(200)

        # envoi entête
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        # envoi message
        lu = tsl.read()
        tsl.active(False)
        self.wfile.write(bytes(
        """La lumière vaut {lu}<br>
        <img src='/garage_jour.png' alt='Graphique du jour'</img><br>
        <img src='/garage_mois.png' alt='Graphique du mois'</img><br>
        <img src='/garage_annee.png' alt='Graphique de année'</img><br>
        """.format(lu=lu), "utf8"))


def initialisation():
    print("Vérification du capteur...")
    try:
        bus = SMBus(1)
    except FileNotFoundError as e:
        print("Erreur dans la recherche du bus I2C : {}".format(e),
              file=sys.stderr)
        sys.exit(ERR_I2C)
    try:
        tsl = TSL2561(bus)
    except IOError as e:
        print("Erreur dans la recherche du capteur : {}".format(e),
              file=sys.stderr)
        sys.exit(ERR_TSL)
    print("Démarrage du serveur.")
    config = configparser.ConfigParser()
    config.read(FICH_CONFIG)
    try:
        addr = config["Serveur"]["address"]
        port = int(config["Serveur"]["port"])
    except (KeyError, ValueError) as e:
        print("Erreur dans la lecture du fichier de configuration :  "
              "{}".format(e), file=sys.stderr)
        sys.exit(ERR_CONFIG)
    return tsl, addr, port


if __name__ == '__main__':
    tsl, addr, port = initialisation()
    httpd = HTTPServer((addr, port), mon_serveur)
    print("Serveur en écoute sur {ad}:{port}...".format(ad=addr, port=port))
    httpd.serve_forever()
