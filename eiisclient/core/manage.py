from __future__ import print_function

import glob
import logging
import os
import shutil
import sys
import threading
import time
import weakref
try:
    import winshell, win32con
except ImportError:
    NOLINKS = True
else:
    NOLINKS = False

from collections import Counter, namedtuple
from enum import Enum
from queue import Queue, Empty
from collections.abc import Iterable
from eiisclient import DEFAULT_ENCODING, DEFAULT_INSTALL_PATH, WORKDIR, SELECTEDFILENAME
from eiisclient.core.dispatch import get_dispatcher
from eiisclient.core.eiisreestr import REESTR
from eiisclient.core.exceptions import (
    RepoIsBusy, DispatcherNotActivated, DispatcherActivationError, PacketInstallError, DownloadPacketError,
    PacketDeleteError, LinkUpdateError, NoUpdates)
from eiisclient.core.utils import get_temp_dir, file_hash_calc, from_json, to_json
from eiisclient import __version__

CONFIGFILE = os.path.normpath(os.path.join(WORKDIR, 'config.json'))
INDEXFILE = os.path.normpath(os.path.join(WORKDIR, 'index.json'))


class Action(Enum):
    ''''''
    install, update, delete = range(3)


class Status(Enum):
    installed, removed, purged = range(3)


def get_stdout_logger() -> logging.Logger:
    logger = logging.Logger(__name__)
    con_handler = logging.StreamHandler(sys.stdout())
    logger.addHandler(con_handler)
    logger.setLevel(logging.INFO)

    return logger


class Manager(object):
    ''''''

    def __init__(self, repo, workdir=None, eiispath=None, logger=None, encode=None, purge=False, threads=1, **kwargs):
        self.repo = repo
        self.logger = logger or get_stdout_logger()
        self.workdir = workdir or WORKDIR  #????
        self.eiispath = eiispath or DEFAULT_INSTALL_PATH
        self.tempdir = get_temp_dir(prefix='eiis_man_tmp_')
        self.buffer = os.path.join(self.workdir, 'buffer')
        self.encode = encode or DEFAULT_ENCODING
        self.purge = purge
        self.threads = threads
        self.task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки
        self.local_index_file = os.path.join(self.workdir, 'index.json')
        self.local_index_file_hash = os.path.join('{}.sha1'.format(self.local_index_file))
        self.selected_packets_list_file = os.path.join(self.workdir, SELECTEDFILENAME)
        self.action_list = {}
        self.disp = None
        self.local_index = None
        self.local_index_hash = None
        self.remote_index = None
        self.remote_index_hash = None
        self.desktop = winshell.desktop() if not NOLINKS else \
            os.path.normpath(os.path.join(os.path.expandvars('%USERPROFILE%'), 'Desktop'))
        self.finalize = weakref.finalize(self, self._clean)

        if self.logger.level == logging.DEBUG:
            self._init_log()

    def __repr__(self):
        return '<Manager: {}>'.format(id(self))

    def start(self, installed: Iterable, selected: Iterable):
        ''''''
        #  определение action_list на установку, обновление и удаление
        install, update, delete = self.get_lists_difference(installed, selected)

        try:
            self.activate()

            # проверка на наличие обновлений
            if not install and not delete and not self.repo_updated():
                raise NoUpdates

            self.action_list['install'] = self.parse_data_by_action_gen(install, Action.install)
            self.action_list['update'] = self.parse_data_by_action_gen(update, Action.update)
            self.action_list['delete'] = self.parse_data_by_action_gen(delete, Action.delete)

            # загрузка файлов пакетов из репозитория
            self.handle_files()

            # деактивация пакетов, помеченных на удаление
            # if delete:
            self.delete_packets()

            # перемещение скачанных пакетов из буфера в папку установки
            if self.buffer_is_empty():
                self.logger.info('Нет пакетов для установки или обновления')
            else:
                self.logger.info('Перенос пакетов из буфера в папку установки:')
                self.install_packets()

            # запись данных нового индекса и контрольной суммы
            if not os.path.exists(self.workdir):
                os.makedirs(self.workdir, exist_ok=True)

            with open(self.local_index_file, 'w') as fp_index, open(self.local_index_file_hash, 'w') as fp_hash:
                fp_index.write(to_json(self.remote_index))
                fp_hash.write(self.remote_index_hash)

            # очистка буфера
            self._clean_buffer()

            # обновление ярлыков на рабочем столе
            self.update_links()

        finally:
            self.deactivate()

    def check_repo(self):
        if self.disp.repo_is_busy():
            raise RepoIsBusy

    def repo_updated(self) -> bool:
        '''Проверка на наличие обновлений'''
        if self.remote_index_hash is None:
            self.remote_index_hash = self.get_remote_index_hash()
        if self.local_index_hash is None:
            self.local_index_hash = self.get_local_index_hash()
        return not self.local_index_hash == self.remote_index_hash

    def buffer_content(self) -> tuple:
        if not os.path.exists(self.buffer):
            return ()
        return tuple(pack for pack in os.listdir(self.buffer) if os.path.isdir(os.path.join(self.buffer, pack)))

    def buffer_count(self) -> int:
        return len(list(self.buffer_content()))

    def buffer_is_empty(self) -> bool:
        try:
            count = self.buffer_count()
        except FileNotFoundError:
            return True
        else:
            return count == 0

    @property
    def activated(self) -> bool:
        return True if self.disp else False

    def activate(self):
        ''''''
        try:
            self.disp = get_dispatcher(self.repo, logger=self.logger, encode=self.encode, tempdir=self.tempdir)
        except Exception as err:
            self.logger.debug('repo: {}'.format(self.repo))
            self.logger.debug('encode: {}'.format(self.encode))
            raise DispatcherActivationError(err)

        self.check_repo()

        self.local_index = self.get_local_index()

        if self.repo_updated():
            self.remote_index = self.get_remote_index() or {}
        else:
            self.remote_index = self.local_index

        self.action_list['install'] = ()
        self.action_list['update'] = ()
        self.action_list['delete'] = ()

    def deactivate(self):
        self.disp = None
        self.action_list = {}
        self.local_index = None
        self.local_index_hash = None
        self.remote_index = None
        self.remote_index_hash = None

    def get_info(self) -> dict:
        try:
            self.activate()
            return {
                'Версия программы': __version__,
                'Пакетов в репозитории': len(self.remote_index.keys()),
                'Установлено подсистем': len(self.get_installed_packets()),
                'Последнее обновление': os.path.getmtime(self.local_index_file) if os.path.exists(
                    self.local_index_file) else None,
                'Наличие обновлений': 'Да' if self.repo_updated() else 'Нет',
                'Пакетов в буфере': self.buffer_count(),
                'Путь: подсистемы': self.eiispath,
                'Путь: репозиторий': self.repo,
                }
        finally:
            self.deactivate()

    def get_installed_packets(self) -> tuple:
        '''Список активных подсистем

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список.'''

        if os.path.exists(self.eiispath):
            active_list = (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
            return tuple(sorted((name for name in active_list if not name.endswith('.removed'))))
        else:
            return tuple()

    def get_selected_packets(self) -> tuple:
        try:
            with open(self.selected_packets_list_file) as fp:
                return tuple(line.strip() for line in fp.readlines() if not any([line.startswith('#'), line.rstrip() == '']))
        except FileNotFoundError:
            return tuple()

    @staticmethod
    def get_lists_difference(installed: Iterable, selected: Iterable) -> tuple:
        common = set(installed) & set(selected)
        install = sorted(set(selected) ^ common)
        delete = sorted(set(installed) ^ common)
        update = sorted(common)

        return install, update, delete

    def delete_packets(self):
        for packet in self.action_list['delete']:
            pack_path = os.path.join(self.eiispath, packet)
            if self.purge:
                try:
                    shutil.rmtree(pack_path)
                except Exception as err:
                    self.logger.error('- ошибка удаления пакета {}: {}'.format(packet, err))
                else:
                    self.logger.info('{} - удален'.format(packet))
                    continue

            try:
                new_pack_path = '{}.removed'.format(pack_path)
                os.rename(pack_path, new_pack_path)
            except Exception as err:
                self.logger.debug('- ошибка удаления пакета {}: {}'.format(packet, err))
                raise PacketDeleteError
            else:
                self.logger.info('{} - помечен как удаленный'.format(packet))

            # удаление ярлыка подсистемы
            try:
                self.remove_shortcut(packet)
            except LinkUpdateError:
                self.logger.error('ошибка удаления ярлыка для {}'.format(packet))

    def clean_removed(self):
        for packet in os.listdir(self.eiispath):
            if packet.endswith('.removed'):
                fp = os.path.join(self.eiispath, packet)
                shutil.rmtree(fp)

    def get_remote_index(self) -> dict:
        self.check_repo()

        if self.activated:
            try:
                return self.disp.get_index_data()
            except FileNotFoundError:
                self.logger.error('Не найден индекс-файл в репозитории')
                raise
        else:
            raise DispatcherNotActivated

    def get_remote_index_hash(self) -> str:
        return self.disp.get_index_hash()

    def get_local_index(self) -> dict:
        try:
            with open(self.local_index_file) as fp:
                return from_json(fp.read())
        except Exception:
            return {}

    def get_local_index_hash(self) -> str:
        try:
            with open(self.local_index_file_hash) as fp:
                # return from_json(fp.read())
                return fp.read()
        except FileNotFoundError:
            return ''

    def get_local_packet_status(self, packet_name) -> Status:
        fp = os.path.join(self.eiispath, packet_name)
        if os.path.exists(fp):
            return Status.installed
        elif os.path.exists('{}.removed'.format(fp)):
            return Status.removed
        else:
            return Status.purged

    def local_packet_exists(self, packet_name) -> bool:
        fp = os.path.join(self.eiispath, packet_name)
        return os.path.exists(fp)

    def claim_packet(self, packet_name) -> bool:
        status = self.get_local_packet_status(packet_name)
        if status == Status.removed:
            pack_new = os.path.join(self.eiispath, packet_name)
            pack_old = '{}.removed'.format(pack_new)
            shutil.move(pack_old, pack_new)
        return self.local_packet_exists(packet_name)

    def parse_data_by_action_gen(self, seq, action):
        ''''''
        if action == Action.install:
            self.logger.info('Обработка данных на установку пакетов')
            for packet in seq:
                packet_is_present = self.claim_packet(packet)
                files = self.remote_index[packet]['files']
                for file in files:
                    if packet_is_present:
                        fp = os.path.join(self.eiispath, packet, file)
                        if os.path.exists(fp) and file_hash_calc(fp) == files[file]:
                            continue
                    fp = os.path.join(self.buffer, packet, file)
                    if os.path.exists(fp) and file_hash_calc(fp) == files[file]:
                        continue

                    packname = packet
                    action = Action.install
                    src = file
                    crc = files[file]

                    yield packname, action, src, crc

        elif action == Action.update:
            self.logger.info('Обработка данных на обновление пакетов')
            for packet in seq:
                if self.local_index[packet]['phash'] == self.remote_index[packet]['phash']:
                    continue

                local_files = self.local_index[packet]['files']
                remote_files = self.remote_index[packet]['files']

                install, update, delete = self.get_lists_difference(local_files.keys(), remote_files.keys())

                for data in zip((Action.install, Action.update, Action.delete), (install, update, delete)):
                    act, lst = data

                    fcount = len(lst)

                    if fcount and act == Action.install:
                        for file in lst:
                            yield packet, act, file, remote_files[file]

                    elif fcount and act == Action.delete:
                        for file in lst:
                            yield packet, act, file, None

                    elif fcount:
                        for file in lst:
                            if not local_files[file] == remote_files[file]:
                                yield packet, act, file, remote_files[file]

        elif action == Action.delete:
            self.logger.info('Обработка данных на удаление пакетов')
            for packet in seq:
                # yield packet, Action.delete, None, None
                yield packet

        else:
            raise TypeError('Тип задачи неопределен')

    def get_task(self) -> namedtuple:
        '''Составление реестра обновленных файлов'''
        for key in ('install', 'update'):
            source_data = self.action_list[key]

            done = Counter()
            for packname, action, src, crc in source_data:
                if packname not in done.keys():
                    self.logger.info('- {}'.format(packname))
                done[packname] += 1

                task = namedtuple('Task', ('packetname', 'action', 'src', 'dst', 'crc'))

                task.packetname = packname
                task.action = action
                if action == Action.delete:
                    task.src = os.path.join(self.eiispath, packname, src)  # путь файла для удаления
                    task.dst = None
                else:
                    task.src = os.path.join(self.disp.repopath, packname, src)  # путь файла-источника для получения
                    task.dst = os.path.join(self.buffer, packname, src)
                task.crc = crc

                yield task

    def handle_files(self):
        '''Получить новые файлы из репозитория или удалить локально старые'''
        error = False

        main_queue = Queue()  # todo: пересмотреть работу с асинхронной очередью, ввиду блокировки из-за ожидания
        # main_queue = Queue(maxsize=self.threads * self.task_queue_k)
        exc_queue = Queue()

        for i in range(self.threads):
            dispatcher = get_dispatcher(self.repo, encode=self.encode, logger=self.logger, tempdir=self.tempdir)
            worker = Worker(main_queue, exc_queue, dispatcher, logger=self.logger)
            worker.setName('{}'.format(worker))
            worker.setDaemon(True)
            worker.start()

        gen_task = self.get_task()

        for task in gen_task:
            main_queue.put(task)

        main_queue.join()  # ожидаем окончания обработки очереди

        while True:
            try:
                exc = exc_queue.get(block=False)
            except Empty:
                break
            else:
                self.logger.error(exc)
                error = True
        if error:
            raise DownloadPacketError

    def install_packets(self):
        '''Копирование пакетов из буфера в папку установки'''
        for packet in self.buffer_content():
            src = os.path.join(self.buffer, packet)

            try:
                for top, _, files in os.walk(src, topdown=False):
                    for file in files:
                        s = os.path.join(top, file)
                        d = os.path.join(self.eiispath, os.path.relpath(s, self.buffer))
                        try:
                            shutil.copyfile(s, d)
                        except FileNotFoundError:  # нет директории в месте назначения
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copyfile(s, d)

                # создание ярлыка
                if NOLINKS:
                    self.logger.debug('не создан ярлык для пакета {}'.format(packet))
                else:
                    title, exe_file_path = self._get_link_data(packet)
                    self.create_shortcut(title, exe_file_path)

            except LinkUpdateError as err:
                self.logger.debug('ошибка создания ярлыка для {}: {}'.format(packet, err))

            except Exception as err:
                self.logger.error('Ошибка установки пакета {}'.format(packet))
                raise PacketInstallError(err)
            else:
                self.logger.info(' - {} обработан'.format(packet))

    def update_links(self):
        for packet in self.get_installed_packets():
            try:
                title, exe_file_path = self._get_link_data(packet)
                self.create_shortcut(title, exe_file_path)
            except LinkUpdateError as err:
                self.logger.error('Ошибка создания ярлыка: {}'.format(err))

    def create_shortcut(self, title, exe_file_path):
        """
        Создание ярлыка запуска подсистемы

        :param
        """
        # if NOLINKS:
        #     raise LinkUpdateError('Ошибка создания ярлыка - отсутствует библиотека win32')

        if not exe_file_path:
            raise LinkUpdateError('недостаточно данных для создания ярлыка для {}'.format(title))

        lnpath = os.path.join(self.desktop, title + '.lnk')
        # target = icon = exe_file_path
        workdir = os.path.dirname(exe_file_path)
        # shell = Dispatch('WScript.Shell')

        # shortcut = shell.CreateShortCut(lnpath)
        # shortcut.Targetpath = target
        # shortcut.WorkingDirectory = workdir
        # shortcut.IconLocation = icon
        # shortcut.save()

        lnpath = os.path.join(winshell.desktop(), '{}.lnk'.format(title))

        try:
            with winshell.shortcut(lnpath) as lp:
                lp.path = exe_file_path
                lp.description = 'Зупуск подсистемы {} ЕИИС Соцстрах РФ'
                lp.working_directory = workdir
                lp.write()
        except Exception as err:
            raise LinkUpdateError('Ошибка создания ярлыка - отсутствует библиотека win32: {}'.format(err))

    def remove_shortcut(self, packet):
        title, _ = self._get_link_data(packet)

        link_path = os.path.join(self.desktop, title + '.lnk')
        try:
            os.unlink(link_path)
        except FileNotFoundError:
            pass

    def _clean(self):
        self.tempdir.cleanup()

    def _clean_buffer(self):
        try:
            shutil.rmtree(self.buffer)
        except FileNotFoundError:
            pass

    def _get_link_data(self, packet) -> tuple:
        try:
            title = self.local_index[packet].get('title') or packet
        except Exception:
            title = packet

        binaries = glob.glob(r'{}\*.exe'.format(os.path.join(self.eiispath, packet)))
        count = len(binaries)
        if count > 1:
            # todo: добавить возможность добавлять свои данные в реестр подсистем
            exefilename = REESTR.get(packet)
            exe_file_path = os.path.join(self.eiispath, packet, exefilename) if exefilename else None
        elif count == 1:
            exe_file_path = binaries[0]
        else:
            exe_file_path = None

        return title, exe_file_path

    def _init_log(self):
        self.logger.debug('{}: repo: {}'.format(self, self.repo))
        self.logger.debug('{}: eiis: {}'.format(self, self.eiispath))
        self.logger.debug('{}: buffer: {}'.format(self, self.buffer))
        self.logger.debug('{}: encode: {}'.format(self, self.encode))
        self.logger.debug('{}: tempdir: {}'.format(self, self.tempdir.name))
        self.logger.debug('{}: task_k: {}'.format(self, self.task_queue_k))
        self.logger.debug('{}: purge: {}'.format(self, self.purge))


class Worker(threading.Thread):
    files_faulted = Counter()
    max_repeat = 3
    stop_retrieve = threading.Event()

    def __init__(self, queue, exc_queue, dispatcher, logger=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.queue = queue
        self.exceptions = exc_queue
        self.dispatcher = dispatcher
        self.logger = logger or get_stdout_logger()

    def __repr__(self):
        return '<Worker-{}>'.format(id(self))

    def run(self):
        while True:
            if self.stop_retrieve.is_set():
                self.logger.debug('{}: обнаружен стоп-флаг. выходим'.format(self))
                raise StopIteration

            if self.dispatcher.repo_is_busy():
                self.logger.debug('{}: репозиторий заблокирован. установка стоп-флага'.format(self))
                self.stop_retrieve.set()
                raise StopIteration

            task = self.queue.get()
            task_id = id(task)
            self.logger.debug('{}<task-{}> ({}|{}|{})'.format(self, task_id, task.packetname, task.action, task.src))

            if task.action == Action.delete:
                self.remove_file(task.src)
            else:
                fp = self.dispatcher.get_file(task.src)
                hash_sum = file_hash_calc(fp)

                if not hash_sum == task.crc:
                    self.files_faulted[task.src] += 1
                    fault_count = self.files_faulted.get(task.src)
                    self.logger.debug('{}<task-{}> <{} != {}> [{}]'.format(self, task_id, hash_sum, task.crc, fault_count))
                    if fault_count is not None and fault_count > self.max_repeat - 1:
                        self.exceptions.put('Неверная контрольная сумма файла "{}" из пакета "{}"'.format(
                            os.path.basename(task.src), task.packetname))
                    else:
# fixme: при установленном максимальном размере, вставка в очередь блокирует процесс. перерсмотреть на возможность асинхронной работы
                        self.queue.put(task)
                else:
                    try:
                        self.dispatcher.move(fp, task.dst)
                        self.logger.debug('{}<task-{}> move {} -> {}'.format(self, task_id, fp, task.dst ))
                    except IOError:
                        self.exceptions.put('Ошибка переноса в буфер файла "{}" из пакета "{}"'.format(
                            os.path.basename(task.src), task.packetname))

            self.queue.task_done()

    def remove_file(self, fpath):
        try:
            os.unlink(fpath)
        except FileNotFoundError:
            pass
        except (PermissionError) as err:
            #  err to log
            import stat
            if not os.access(fpath, os.W_OK):
                os.chmod(fpath, stat.S_IWUSR)
                time.sleep(0.3)
                try:
                    os.unlink(fpath)
                except Exception:
                    pass
