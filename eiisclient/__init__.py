# -*- coding: utf-8 -*-

"""Top-level package for eiisclient."""
import os

__author__ = 'Михаил Петров'
__email__ = 'mb.petrov@ro66.fss.ru'
__division__ = 'филиал №2 ГУ СРО ФСС РФ'
__version__ = '0.1.12'
__license__ = 'BSD'

DEFAULT_FTP_SERVER = 'ftp://10.66.2.131'
DEFAULT_ENCODING = 'CP1251'
DEFAULT_FTP_ENCODING = 'UTF-8'
WORK_DIR_NAME = 'Обновление ЕИИС Соцстрах'
CONFIG_FILE_NAME = 'config.json'
SELECTED_FILE_NAME = 'selected.txt'
WORK_DIR = os.path.join(os.path.expandvars('%APPDATA%'), WORK_DIR_NAME)
DEFAULT_INSTALL_PATH = os.path.normpath(os.path.join(os.path.expandvars('%PROGRAMFILES%'), r'NIST\ЕИИС ФСС РФ'))
PROFILE_INSTALL_PATH = os.path.normpath(os.path.join(os.path.expandvars('%APPDATA%'), 'ЕИИС ФСС РФ'))
