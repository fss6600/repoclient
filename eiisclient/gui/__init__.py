##
import logging
import os
import sys
from collections import MutableMapping
from logging.handlers import RotatingFileHandler

from wx.core import wx

from eiisclient import WORK_DIR, DEFAULT_ENCODING
from eiisclient.core.manage import Manager

__all__ = ['PackData',
           'PackList',
           'get_manager',
           'get_logger',

           'PCK_NEW',
           'PCK_DEL',
           'PCK_ABD',
           'PCK_INS',
           'PCK_UPD',

           'NON',
           'UPD',
           'DEL',
           'NEW',
           ]


# colors
PCK_NEW = wx.Colour(210, 240, 250, 0)  # новый пакет - нет локально, есть в репозитории
PCK_UPD = wx.Colour(210, 250, 210, 0)  # обновленный пакет - есть локально, есть в репозитории
PCK_ABD = wx.Colour(250, 220, 210, 0)  # исиротевший пакет (abandoned) - есть локально, нет в репозитории
PCK_INS = wx.BLUE  # пакет помечен на установку
PCK_DEL = wx.RED  # пакет помечен на удаление

# pack status
NON = 0  # нет изменений
UPD = 1  # есть обновления, будет обновлен
DEL = 2  # будет удален
NEW = 3  # новый, будет установлен


if sys.version_info >= (3, 7):
    """Класс для представления данных пакета в списке"""
    from dataclasses import make_dataclass
    PackData = make_dataclass('PackData', [('origin', str), ('installed', bool), ('status', int)])
else:
    class PackData:
        def __init__(self, origin: str = None, installed: bool = False, status: int = NON):
            self.origin = origin
            self.installed = installed
            self.status = status


class PackList(MutableMapping):
    """Класс для представления списка пакетов для отображения в панели пакетов"""
    def __init__(self):
        self.store = dict()
        self.origin = dict()

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value
        self.origin[value.origin] = key

    def __delitem__(self, key):
        obj = self.store.get(key)
        if obj:
            k = getattr(obj, 'origin')
            if k:
                try:
                    del self.origin[k]
                except:
                    pass
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def get_by_origin(self, key) -> (str, PackData):
        k = self.origin.get(key)
        if k is None:
            return None, None
        val = self.store.get(k)
        return k, val

    def clear(self) -> None:
        self.store.clear()
        self.origin.clear()


def get_manager(config, logger, full=False):
    try:
        manager = Manager(config, logger=logger, full=full)
    except Exception as err:
        logger.error('Ошибка инициализации менеджера: {}'.format(err))
        manager = None
    else:
        logger.debug('Менеджер инициализирован: {}'.format(manager))
    return manager


def get_logger(func_log_out, debug=False, logfile=False):
    logger = logging.getLogger(__name__)
    level = logging.INFO
    formatter = logging.Formatter('%(message)s')
    if debug:
        level = logging.DEBUG
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    if logfile:
        logfile = os.path.join(WORK_DIR, 'messages.log')
        log_handler = RotatingFileHandler(logfile, maxBytes=1024 * 1024, encoding=DEFAULT_ENCODING)
        logger.addHandler(log_handler)
    logger.setLevel(level)
    handler = WxLogHandler(func_log_out)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class WxLogHandler(logging.StreamHandler):
    def __init__(self, func_log_out=None):
        super(WxLogHandler, self).__init__()
        self.func_log_out = func_log_out
        self.level = logging.DEBUG

    def emit(self, record):
        try:
            msg = ('{}\n'.format(self.format(record)), record.levelname)
            wx.CallAfter(self.func_log_out, *msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
