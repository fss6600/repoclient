# -*- coding: utf-8 -*-

"""Top-level package for eiisclient."""
import os

__author__ = 'Михаил Петров'
__email__ = 'adm_fil_02@ro66.fss.ru'
__division__ = 'филиал №2 ГУ СРО ФСС РФ'
__version__ = '0.1.4'
__license__ = 'BSD'

DEFAULT_ENCODING = 'utf-8'
WORKDIRNAME = 'Обновление ЕИИС Соцстрах'
CONFIGFILENAME = 'config.json'
SELECTEDFILENAME = 'selected.txt'
WORKDIR = os.path.join(os.path.expandvars('%APPDATA%'), WORKDIRNAME)
DEFAULT_INSTALL_PATH = os.path.normpath(os.path.join(os.path.expandvars('%PROGRAMFILES%'), r'NIST\ЕИИС ФСС РФ'))
