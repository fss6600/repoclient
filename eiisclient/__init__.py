# -*- coding: utf-8 -*-

"""Top-level package for eiisclient."""
import os

from .__version__ import __version__

__author__ = 'Михаил Петров'
__email__ = 'mb.petrov@ro66.fss.ru'
__division__ = 'филиал №2 ГУ СРО ФСС РФ'
__license__ = 'BSD'


DEFAULT_FTP_SERVER = 'ftp://10.66.2.131'  # todo remove
DEFAULT_ENCODING = 'UTF-8'
DEFAULT_FTP_ENCODING = DEFAULT_ENCODING
# WORK_DIR_NAME = 'Обновление ЕИИС Соцстрах'
# CONFIG_FILE_NAME = 'config.json'
WORK_DIR = os.path.join(os.path.expandvars('%APPDATA%'), 'Обновление ЕИИС Соцстрах')
DEFAULT_INSTALL_PATH = os.path.normpath(os.path.join(os.path.expandvars('%PROGRAMFILES%'), r'NIST\ЕИИС ФСС РФ'))
PROFILE_INSTALL_PATH = os.path.normpath(os.path.join(os.path.expandvars('%APPDATA%'), 'ЕИИС ФСС РФ'))
CONFIGFILE = os.path.normpath(os.path.join(WORK_DIR, 'config.json'))
INDEXFILE = os.path.normpath(os.path.join(WORK_DIR, 'index.json'))
