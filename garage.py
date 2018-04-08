#!/home/pi/.Envs/garage/bin/python
# -*- coding: utf-8 -*-
"""
Surveillance de la luminosité dans le garage. Si la luminosité est
supérieure à un seuil pendant une certaine durée, provoque l'envoi
d'une notification.

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
from tsl2561 import TSL2561
from smbus2 import SMBus
import configparser
import argparse
import datetime
import time
import logging
import logging.handlers
import freesms
import sys
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
import rrdtool
from daemon3x import daemon

FICH_CONFIG = '/etc/garage/garage.conf'
ERR_I2C = 1
ERR_TSL = 2
FMT_DATE = "%H:%M:%S"


def envoi_mail(message):
    msg = MIMEText(message)
    msg["To"] = config["Mail"]["destinataires"]
    msg["Subject"] = "Porte garage"
    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE, stderr=PIPE)
    rep, err = p.communicate(msg.as_bytes())
    return not err


def previens(msg, f):
    """ rendre compte que la luminosité a changé
    param: msg: message à envoyer
    param: f: descripteur pour envoi sms
    """
    logger.info(msg)
    reponse = f.send_sms(msg)
    if reponse.success():
        logger.info("SMS envoyé")
    else:
        logger.error("Erreur lors de l'envoi du SMS")
    if not envoi_mail(msg):
        logger.error("Erreur lors de l'envoi du mail")


def init_capteur():
    logger.debug("Initialisation du bus I2C")
    try:
        bus = SMBus(1)
    except FileNotFoundError as e:
        logger.fatal("Erreur dans la recherche du bus I2C : %s", e)
        sys.exit(ERR_I2C)
    logger.debug("Initialisation du capteur TSL")
    try:
        tsl = TSL2561(bus)
    except IOError as e:
        logger.fatal("Erreur dans la recherche du capteur : %s", e)
        sys.exit(ERR_TSL)
    try:
        gain = int(config["Capteur"]["gain"])
        tsl.gain(gain)
    except (KeyError, ValueError) as e:
        logger.error("Erreur dans le fichier de configuration."
                     "lecture du gain du capteur : %s", e)
    logger.info("Gain du capteur : %s", tsl.gain())
    try:
        integration = int(config["Capteur"]["integration"])
        tsl.integration_time(integration)
    except (KeyError, ValueError) as e:
        logger.error("Erreur dans le fichier de configuration."
                     "lecture du temps d'intégration du capteur : %s", e)
    logger.info("Temps d'intégration du capteur : %s ms.",
                tsl.integration_time())
    return tsl


class Surveille(daemon):
    def main(self, delai, attente):
        """ lit le capteur en boucle et déclenche previens si capteur dans
        l'état allumé depuis attente lectures
        """
        tsl = init_capteur()
        logger.debug("fichier pid : %s", self.pidfile)
        etat_avant = 'fermé'
        compteur = 0
        deja_malade = False
        f = freesms.FreeClient(user=config["FreeMobile"]["user"],
                               passwd=config["FreeMobile"]["password"])
        logger.debug("initialisation SMS pour %s",
                     config["FreeMobile"]["user"])
        gdh = datetime.datetime.now()
        while True:
            time.sleep(delai - 1)
            try:
                lux = tsl.read()
                tsl.active(False)
            except (IOError, ValueError) as e:
                if not deja_malade:
                    msg = "Erreur dans la lecture du capteur : {e}".format(e=e)
                    logger.fatal(msg)
                    previens(msg)
                deja_malade = True
                continue
            if deja_malade:
                deja_malade = False
                msg = "Capteur ok."
                logger.info(msg)
                previens(msg)
            etat = [k for k, v in config["Etats"].items()
                    if float(v) <= lux][-1]
            logger.debug("Valeur lue : %s - état : %s", lux, etat)
            if etat != etat_avant:
                gdh = datetime.datetime.now()
                msg = "garage : etat {statut} a {gdh}".format(statut=etat,
                                                  gdh=gdh.strftime(FMT_DATE))

                previens(msg, f)
            etat_avant = etat
            try:
                rrdtool.update(config["rrd"]["base"], "N:{}".format(lux))
            except rrdtool.OperationalError:
                pass

    def run(self):
        self.main(delai, attente)


def init_prog(args):
    config = configparser.ConfigParser()
    config_file = FICH_CONFIG
    if hasattr(args, 'config'):
        if hasattr(args.config, 'name'):
            config_file = args.config.name
    config.read(config_file, encoding='utf-8')
    if args.log_level is None:
        try:
            level = logging._nameToLevel.get(
                config["Programme"]["logging"].upper(), logging.DEBUG)
        except KeyError as e:
            level = logging.DEBUG
            logger.warning("Niveau de log défini à la valeur par défaut. "
                           "Erreur dans la clé %s du fichier de "
                           "configuration", e)
    else:
        level = args.log_level
    if args.foreground:
        handler = logging.StreamHandler()
    else:
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        if hasattr(args, "log_file"):
            handler = logging.FileHandler(args.log_file)
        else:
            try:
                logfile = config["Programme"]["logfile"]
                handler = logging.FileHandler(logfile)
            except KeyError as e:
                pass
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.info("Démarrage du programme")
    logger.debug("Niveau de débogage : %s", level)
    return config


def lit_config(config):
    try:
        delay = int(config['Temps']['delay'])
    except (KeyError, ValueError) as e:
        delay = 30
        logger.warning("Intervalle de lecture du capteur définie à la "
                       "valeur par défaut. Erreur dans la clé %s "
                       "du fichier de configuration", e)
    try:
        attente = int(config['Temps']['compteur'])
    except (KeyError, ValueError) as e:
        attente = 10
        logger.warning("Nombre de lecture défini à la valeur par défaut."
                       "Erreur dans la clé %s du fichier de "
                       "configuration", e)
    return delay, attente


class Args:
    """ arguments de la ligne de commande"""


def lit_params_ligne_cmd():
    parser = argparse.ArgumentParser(description="Suivre l'état de la "
                                                 "porte du garage.")
    parser.add_argument("-l", "--log-level",
                        action="store",
                        help="spécifier le niveau sous la forme "
                             "[DEBUG|INFO|WARN...]")
    parser.add_argument("-f", "--foreground",
                        action="store_true",
                        help="fonctionner en premier plan")
    parser.add_argument("-c", "--config",
                        type=argparse.FileType('r'),
                        default=FICH_CONFIG,
                        help="emplacement du fichier de configuration")
    args = Args()
    parser.parse_args(namespace=args)
    return args


if __name__ == "__main__":
    logger = logging.getLogger('Garage')
    args = lit_params_ligne_cmd()
    config = init_prog(args)
    delai, attente = lit_config(config)
    envoi_mail("Début du programme")
    surveille = Surveille(config["Programme"]["pid"])
    if args.foreground:
        surveille.run()
    else:
        surveille.start()
