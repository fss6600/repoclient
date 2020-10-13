# Exceptions

class RepoIsBusy(Exception):
    def __str__(self):
        return 'Репозиторий заблокирован для обновлеия. Попробуйте позднее.'


class NoUpdates(Exception):
    def __str__(self):
        return 'Обновлений нет'


class DispatcherNotActivated(Exception):
    def __str__(self):
        return 'Диспетчер не активирован'


class DispatcherActivationError(Exception):
    pass


class PacketInstallError(Exception):
    def __init__(self, message=''):
        self.message = message

    def __str__(self):
        return 'Ошибка при установке пакетов: {}'.format(self.message)


class CopyPackageError(Exception):
    def __str__(self):
        return 'Ошибка при копировании пакетов'


class PacketDeleteError(Exception):
    def __str__(self):
        return 'Ошибка при удалении пакетов'


class DownloadPacketError(Exception):
    pass


class LinkUpdateError(Exception):
    pass


class LinkNoData(Exception):
    pass


class LinkDisabled(Exception):
    pass


class NoIndexFileOnServer(Exception):
    def __str__(self):
        return 'Не найден индекс-файл в репозитории'


class InstallPermissionError(Exception):
    def __init__(self, message=None):
        self.message = message or ''

    def __str__(self):
        msg = 'Недостаточно прав доступа для установки пакета подсистем'
        return msg + ': {}'.format(self.message) if self.message else msg
