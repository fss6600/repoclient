###  Exceptions


class RepoIsBusy(Exception):
    def __repr__(self):
        return 'Репозиторий заблокирован для обновлеия. Попробуйте позднее'


class DispatcherNotActivated(Exception):
    def __repr__(self):
        return 'Диспетчер не активирован'


class DispatcherActivationError(Exception):
    def __repr__(self):
        return 'Ошибка активации диспетчера'


class PacketInstallError(Exception):
    def __repr__(self):
        return 'Ошибка установки пакета'


class PacketDeleteError(Exception):
    pass


class DownloadPacketError(Exception):
    pass


class LinkUpdateError(Exception):
    pass
