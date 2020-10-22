# Exceptions

class BaseManagerError(Exception):
    pass


class RepoIsBusy(BaseManagerError):
    def __str__(self):
        return 'Репозиторий заблокирован для обновлеия. Попробуйте позднее.'


class NoUpdates(BaseManagerError):
    def __str__(self):
        return 'Обновлений нет'


class DispatcherNotActivated(BaseManagerError):
    def __str__(self):
        return 'Диспетчер не активирован'


class DispatcherActivationError(BaseManagerError):
    def __str__(self):
        return 'Ошибка активации диспетчера'


class PacketInstallError(BaseManagerError):
    def __init__(self, message=''):
        self.message = message

    def __str__(self):
        return 'Ошибка при установке пакетов: {}'.format(self.message)


class CopyPackageError(BaseManagerError):
    def __str__(self):
        return 'Ошибка при копировании пакетов'


class PacketDeleteError(BaseManagerError):
    def __str__(self):
        return 'Ошибка при удалении пакетов'


class DownloadPacketError(BaseManagerError):
    pass


class HashMismatchError(BaseManagerError):
    pass


class NoIndexFileOnServerError(BaseManagerError):
    def __str__(self):
        return 'Не найден индекс-файл в репозитории'


class InstallPermissionError(BaseManagerError):
    def __init__(self, message=None):
        self.message = message or ''

    def __str__(self):
        msg = 'Недостаточно прав доступа для установки пакета подсистем'
        return msg + ': {}'.format(self.message) if self.message else msg


class LinkUpdateError(BaseManagerError):
    def __str__(self):
        return 'Ошибка обновления ярлыка'


class LinkNoData(Exception):
    pass


class LinkDisabled(Exception):
    pass


class IndexFixError(BaseManagerError):
    pass
