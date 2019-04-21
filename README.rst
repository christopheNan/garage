=====================================================
Suivi à distance de l'ouverture d'une porte de garage
=====================================================

Je suis équipé d'une porte de garage télécommandée. Bien que très pratique,
il m'est arrivé plusieurs fois d'appuyer par inadvertance sur la télécommande
(placée dans la poche) lorsque je suis dans la maison. Je ne m'aperçois pas
alors que la porte s'ouvre et reste ouverte.
Ce petit programme Python utilise un capteur de luminosité TSL 2561 connecté
à un *raspberry Pi* pour détecter l'ouverture de la porte et m'envoie un SMS
ou un mail pour m'avertir du changement de position.


Installation
============
Prérequis
---------
Il faut avoir installé Python 3, avec le paquet venv :
::

  pi@raspi:~ $ sudo apt-get install python3-venv
  pi@raspi:~ $

Pour l'envoi de mails, il faut avoir configuré un programme `sendmail`. Le
paquet `ssmtp <https://wiki.debian.org/sSMTP>`_ est parfait pour cela.

Par ailleurs, il est possible d'enregister les mesures dans une base de
données tournante (rrdtool). Dans ce cas, il faut avoir installé librrd-dev.

Récupération des sources
------------------------
Les dernières sources sont sur Github :

::

  pi@raspi:~ $ git clone git@github.com:christopheNan/garage.git
  pi@raspi:~ $ cd garage
  pi@raspi:~/garage $

Création d'un environnement virtuel
-----------------------------------
Afin de ne pas interférer avec d'autres utilisations de Python sur le
Raspberry, nous créons un environnement virtuel :
::

  pi@raspi:~/garage $ mkdir -p ~/.Envs/ && python3 -m venv ~/.Envs/garage/
  pi@raspi:~/garage $ . ~/.Envs/garage/bin/activate
  (garage)pi@raspi:~/garage $ pip install -r requirements.txt

Installation en tant que service systemd
-----------------------------------------
Afin que le programme soit lancé au démarrage du Pi et que son fonctionnement
soit surveillé, nous le lançons en tant que service systemd :
::

  (garage)pi@raspi:~/garage $ sudo cp garage.service /etc/systemd/system/
  (garage)pi@raspi:~/garage $ sudo mkdir -p /var/run/garage
  (garage)pi@raspi:~/garage $ sudo chown pi:pi /var/run/garage


Copie du fichier de configuration
----------------------------------
En tant que service systemd, plaçons son fichier de configuration dans /etc :
::

  (garage)pi@raspi:~/garage $ sudo cp config.txt /etc/garage.conf


Fichier de configuration
========================
Section serveur
---------------
Vous pouvez définir l'adresse sur laquelle écoute le serveur ainsi que le
port

Section FreeMobile
------------------
*Merci Free* : nous pouvons envoyer gratuitement des SMS à notre numéro
abonné chez Free. Rendez-vous dans votre espace abonné Free pour activer le
service, obtenir un identifiant et un mot de passe.

- user :
  identifiant obtenu dans l'espace abonné Free

- password :
  mot de passe obtenu dans l'espace abonné Free

Section Mail
------------
Si nous n'avons pas de mobile Free, nous pouvons quand même recevoir des
mails. Le programme utilise la commande `sendmail` pour envoyer des mails
(voir la section `Prérequis`_).

- destinataires :
  une liste d'adresses mail séparées par des virgules.

Section Etats
-------------
Configurer ici les différents états que vous voulez reconnaître, dans l'ordre
croissant de la luminosité.

Section Capteur
---------------
Le TSL2561 peut être configuré avec deux paramètres :

- temps d'intégration :
  13, 101 ou 402 ms

- gain :
  1 ou 16

Section Temps
-------------
Configurer ici :

- delay :
  c'est l'intervalle de temps en secondes entre 2 mesures.

- compteur :
  c'est le nombre de mesures invalides consécutives avant d'envoyer un
  message d'erreur.

Section Programme
-----------------
- logging :
  définissez ici le niveau des traces que vous souhaitez : DEBUG, INFO,
  WARNING ou ERROR
- pid :
  définissez ici le fichier dans lequel est stocké le PID du programme.

  Ce paramètre est utilisé par systemd pour suivre le programme. Si vous
  modifiez cette valeur, veillez à répercuter la modification dans le fichier
  de configuration du service systemd (/etc/systemd/system/garage.service)

Section rrd
-----------
Les valeurs lues par le capteur peuvent être stockées dans une base de
données tournante. Spécifiez ici cette base de données

Étalonnage du capteur
=====================
- lancer le serveur web ::

  (garage)pi@raspi:~/garage $ python serveur.py

- étalonner le capteur avec les différentes positions

::

  utilisateur@mon_pc:~ $ # porte fermée, lumière éteinte
  utilisateur@mon_pc:~ $ curl raspi:8080/
  La lumière vaut 0.5
  utilisateur@mon_pc:~ $
  utilisateur@mon_pc:~ $ # porte fermée, lumière allumée
  utilisateur@mon_pc:~ $ curl raspi:8080/
  La lumière vaut 0.6
  utilisateur@mon_pc:~ $
  utilisateur@mon_pc:~ $ # porte ouverte
  utilisateur@mon_pc:~ $ curl raspi:8080/
  La lumière vaut 0.7
  utilisateur@mon_pc:~ $ ...

Test du service
===============
::

  (garage)pi@raspi:~/garage $ # obtenir l'aide sur les différentes options
  (garage)pi@raspi:~/garage $ python3 garage.py -h
  (garage)pi@raspi:~/garage $ python3 garage.py -f --log-level DEBUG

Gestion du service systemd
===========================
- Lancement manuel du service :

::

  pi@raspi:~/garage $ sudo systemctl start garage.service

- Vérification de l'état :

::

  pi@raspi:~/garage $ sudo systemctl status garage.service

- Activation automatique au démarrage du raspberry :

::

  pi@raspi:~/garage $ sudo systemctl enable garage.service


Licence
=======
Ce logiciel est distribué sous la licence GPL v3.
