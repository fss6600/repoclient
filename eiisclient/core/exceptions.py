###  Exceptions


class RepoIsBusy(Exception):
    def __str__(self):
        return 'Репозиторий заблокирован для обновлеия. Попробуйте позднее'


class NoUpdates(Exception):
    def __str__(self):
        return 'Обновлений нет'


class DispatcherNotActivated(Exception):
    def __str__(self):
        return 'Диспетчер не активирован'


class DispatcherActivationError(Exception):
    def __str__(self):
        return 'Ошибка активации диспетчера'


class PacketInstallError(Exception):
    def __str__(self):
        return 'Ошибка при установке пакетов'


class PacketDeleteError(Exception):
    def __str__(self):
        return 'Ошибка при удалении пакетов'


class DownloadPacketError(Exception):
    def __str__(self):
        return 'Ошибка при загрузке пакетов подсистем'


class LinkUpdateError(Exception):
    def __str__(self):
        return 'Ошибка при удалении ярлыков'
