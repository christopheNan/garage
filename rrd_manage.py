#!/home/pi/.Envs/garage/bin/python
# -*- coding: utf-8 -*-
"""
Gestion de la base de données tournante pour stockage et affichage des
valeurs lues.

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
import rrdtool
import os
import sys
import configparser
import argparse
import logging

FICH_CONFIG = '/etc/garage/garage.conf'


class Args:
    pass


def cree_rrd_database(db_file, step):
    nb_points = int(7 * 60 * 24 * 20 / step)
    heart_beat = int(3 * step)
    data_sources = ["DS:lumin:GAUGE:{}:0:10".format(heart_beat),
                    "RRA:MIN:0.5:1:{}".format(nb_points),
                    ]
    rrdtool.create(db_file, "-s {}".format(step*3), data_sources)
    logging.debug("Base de données {} créée.".format(db_file))
    logging.debug("Data sources : {}".format(data_sources))


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(FICH_CONFIG, encoding='utf-8')
    logging.getLogger()
    level = logging.DEBUG
    niveaux_log = [k for k in logging._nameToLevel if k != 'NOTSET']
    try:
        niveau_config = config["Programme"]["logging"].upper()
        level = logging._nameToLevel.get(niveau_config, level)
    except KeyError as e:
        level = logging.DEBUG
        logging.warning("Erreur dans la clé {} du fichier de "
                        "configuration".format(e))
    parser = argparse.ArgumentParser(description="Gérer la base de données "
                                                 "du capteur de luminosité.")
    parser.add_argument("-l", "--log-level",
                        action="store",
                        help="spécifier le niveau sous la forme "
                             "[DEBUG|INFO|WARN...]")
    parser.add_argument("-c", "--create",
                        action="store_true",
                        help="créer la base de données")
    args = Args()
    parser.parse_args(namespace=args)
    if args.log_level:
        param = logging._nameToLevel.get(args.log_level.upper())
        if param:
            level = param
        else:
            logging.error("Mauvais paramètre pour l'argument --log-level :"
                          " {} n'est pas dans {}".format(args.log_level,
                                                         niveaux_log))
    logging.basicConfig(level=level)
    logging.info("Démarrage du programme")
    try:
        db_file = config["rrd"]["base"]
    except KeyError as e:
        logging.fatal(e)
        sys.exit(2)
    if args.create:
        logging.debug("Argument create : {}".format(args.create))
        step = int(config["Temps"]["delay"])
        cree_rrd_database(db_file, step)
