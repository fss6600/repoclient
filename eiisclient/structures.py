import sys
from collections import MutableMapping

# pack status
from enum import Enum

NON = 0  # нет изменений
UPD = 1  # есть обновления, будет обновлен
DEL = 2  # будет удален
NEW = 3  # новый, будет установлен



class Action(Enum):
    """
    Тип действия над пакетом
    """
    install, update, delete = range(3)


class Status(Enum):
    """
    Статус пакета на ПК пользователя
    """
    installed, removed, purged = range(3)


class PackStatus(Enum):
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
        def __init__(self, origin: str = None, installed: bool = False, status: int = PackStatus.NON):
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


class ConfigDict(dict):
    """Настройки программы

    Класс для хранения данных параметров программы с возможностью доступа к данным через атрибуты.
    При отсутствии запрашиваемого атрибута или ключа, возвращает None, вместо ошибки KeyError
    """
    __setattr__ = dict.__setitem__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getattr__(self, item):
        if item not in self:
            return None
        else:
            return self.__getitem__(item)
