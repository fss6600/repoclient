import sys
from collections import MutableMapping, namedtuple

from enum import Enum

# # pack status
# NON = 0  # нет изменений
# UPD = 1  # есть обновления, будет обновлен
# DEL = 2  # будет удален
# NEW = 3  # новый, будет установлен


Task = namedtuple('Task', ('packetname action src dst hash'))


class State(Enum):
    """
    Статус состояния пакета, файла для обработки
    """
    NON = 0  # нет изменений
    UPD = 1  # есть обновления, будет обновлен
    DEL = 2  # будет удален
    NEW = 3  # новый, будет установлен


if sys.version_info >= (3, 7):
    """Класс для представления данных пакета в списке"""
    from dataclasses import make_dataclass
    PackData = make_dataclass('PackData', [('origin', str), ('installed', bool), ('checked', bool), ('status', int)])
else:
    class PackData:
        def __init__(self, origin: str = None,
                     installed: bool = False,
                     checked: bool = False,
                     status: State = State.NON):
            self.origin = origin
            self.installed = installed
            self.checked = checked
            self.status = status


class PackList(MutableMapping):
    """Класс для представления списка пакетов со статусом"""
    def __init__(self):
        self._store = dict()
        self._origin = dict()

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value
        self._origin[value.origin] = key

    def __delitem__(self, key):
        obj = self._store.get(key)
        if obj:
            k = getattr(obj, 'origin')
            if k:
                try:
                    del self._origin[k]
                except:
                    pass
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def get_by_origin(self, key) -> (str, PackData):
        k = self._origin.get(key)
        if k is None:
            return None, None
        val = self._store.get(k)
        return k, val

    def clear(self) -> None:
        self._store.clear()
        self._origin.clear()

    def get_action(self, pack):
        val = self._store[pack]
        if val.checked and val.installed and (val.status == State.UPD or val.status == State.NEW):
            return State.UPD
        elif val.checked and not val.installed:
            return State.NEW
        elif not val.checked and val.installed:
            return State.DEL
        return State.NON


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
