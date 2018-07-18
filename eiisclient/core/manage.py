from __future__ import print_function

import logging
import os
import shutil
import sys
import threading
import time
import weakref

try:
    import winshell
    from win32com.client import Dispatch
except ImportError:
    NOLINKS = True
else:
    NOLINKS = False

from collections import Counter, namedtuple
from datetime import datetime
from enum import Enum
from queue import Queue
from collections.abc import Iterable
from eiisclient import DEFAULT_ENCODING, DEFAULT_INSTALL_PATH, WORKDIR
from eiisclient.core.dispatch import get_dispatcher
from eiisclient.core.utils import get_temp_dir, file_hash_calc, from_json
from eiisclient.core.exceptions import (
    RepoIsBusy, DispatcherNotActivated, DispatcherActivationError, PacketInstallError)

CONFIGFILE = os.path.normpath(os.path.join(WORKDIR, 'config.json'))
INDEXFILE = os.path.normpath(os.path.join(WORKDIR, 'index.json'))


class Action(Enum):
    ''''''
    install, update, delete = range(3)


class Status(Enum):
    installed, removed, purged = range(3)


def get_null_logger():  # todo: remove
    logger = logging.Logger(__name__)
    logger.addHandler(logging.NullHandler())
    return logger


class Manager(object):
    ''''''

    def __init__(self, repo, workdir=None, eiispath=None, logger=None, encode=None, purge=False, threads=1, **kwargs):
        self.repo = repo
        self.logger = logger or get_null_logger()
        self.workdir = workdir or WORKDIR
        self.eiispath = eiispath or DEFAULT_INSTALL_PATH
        self.encode = encode or DEFAULT_ENCODING
        self.purge = purge
        self.threads = threads
        self.task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки

        self.tempdir = get_temp_dir()
        self.buffer = os.path.join(self.workdir, 'buffer')
        self.local_index_file = os.path.join(self.workdir, 'index.json')
        self.local_index_file_hash = os.path.join('{}.sha1'.format(self.local_index_file))
        self.selected_packets_list_file = os.path.join(self.workdir, 'selected')
        self.during_time = 0
        self.files_count = 0  # -
        self.disp = None
        self.action_list = {}
        self.local_index = None
        self.remote_index = None
        self.finalize = weakref.finalize(self, self._clean)

    def __str__(self):
        return '<Manager: {}'.format(id(self))

    def _clean(self):
        self.tempdir.cleanup()

    def repo_busy_check(self):
        if self.disp.repo_is_busy():
            raise RepoIsBusy

    def repo_updated(self) -> bool:
        '''Проверка на наличие обновлений'''
        self.repo_busy_check()
        old_index_hash = self.get_local_index_hash()
        new_index_hash = self.disp.get_index_hash()
        return not old_index_hash == new_index_hash

    @property
    def activated(self):
        return True if self.disp else False

    def activate(self):
        ''''''
        try:
            self.disp = get_dispatcher(self.repo, logger=self.logger, encode=self.encode)
        except Exception as err:
            raise PacketInstallError from err

    def deactivate(self):
        self.disp = None
        self.action_list = {}
        self.local_index = None
        self.remote_index = None

    def get_info(self):
        pass

    def start(self, installed: Iterable, selected: Iterable):
        ''''''
        try:
            self.activate()

            self.logger.info('Проверка на наличие обновлений')
            if not self.repo_updated():
                self.logger.info('Обновлений нет')
                return

            self.logger.info('Обнаружены обновления.')
            self.local_index = self.get_local_index() or {}
            self.remote_index = self.get_remote_index()

            #  определяем action_list на установку, обновление и удаление
            install, update, delete = self.get_lists_difference(installed, selected)

            self.action_list['install'] = self.parse_data_by_action(install, Action.install)
            self.action_list['update'] = self.parse_data_by_action(update, Action.update)
            self.action_list['delete'] = self.parse_data_by_action(delete, Action.delete)

            # загрузка файлов пакетов из репозитория
            self.logger.info('загрузка пакетов из репозитория в буфер:')
            download_duration = self.get_new_files()
            self.logger.info('пакеты загружены за {}'.format(download_duration))

            # перемещение скачанных пакетов из буфера в папку установки
            if not self.buffer_is_empty():
                self.logger.info('перенос пакетов из буфера в папку установки')
                self.install_packets()

            # деактивация пакетов, помеченных на удаление
            if self.action_list.get('delete'):
                self.logger.info('удаление пакетов:')
                res = self.delete_packets()

            # обновление ярлыков подсистем на рабочем столе
            if NOLINKS:
                self.logger.debug('невозможно создать ярлыки - ошибка импорта библиотеки win32')
            else:
                self.update_links()

        except Exception as err:  # todo обработку исключений по типам
            self.logger.error(err)
            return
        else:
            # запись данных нового индекса и хэша локально
            # очистка буфера
            pass
        finally:
            self.deactivate()

    def get_installed_packets_list(self) -> tuple:
        '''Список активных подсистем

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список.'''

        if os.path.exists(self.eiispath):
            active_list = (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
            return tuple(sorted((name for name in active_list if not name.endswith('.removed'))))
        else:
            return tuple()

    def get_selected_packets_list(self) -> tuple:
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
                    self.logger.error('ошибка удаления пакета {}: {}'.format(packet, err))
                    self.logger.error('пакет {} будет помечен как удаленный')
                else:
                    self.logger.info('{} - удален с диска'.format(packet))
                    continue

            try:
                new_pack_path = '{}.removed'.format(pack_path)
                os.rename(pack_path, new_pack_path)
            except Exception as err:
                self.logger.error('ошибка удаления пакета {}'.format(packet))
                raise IOError(err)  #todo заменить исключение
            else:
                self.logger.info('{} - помечен как удаленный'.format(packet))

    def get_remote_index(self):
        if self.activated:
            self.repo_busy_check()
            try:
                return self.disp.get_index_data()
            except FileNotFoundError:
                self.logger.error('Не найден индекс-файл в репозитории')
                raise
        else:
            raise DispatcherNotActivated

    def get_local_index(self):
        try:
            with open(self.local_index_file) as fp:
                return from_json(fp.read())
        except FileNotFoundError:
            return {}

    def get_local_index_hash(self):
        try:
            with open(self.local_index_file_hash) as fp:
                return from_json(fp.read())
        except FileNotFoundError:
            return None

    def get_local_packet_status(self, packet_name):
        fp = os.path.join(self.eiispath, packet_name)
        if os.path.exists(fp):
            return Status.installed
        elif os.path.exists('{}.removed'.format(fp)):
            return Status.removed
        else:
            return Status.purged

    def local_packet_exists(self, packet_name):
        fp = os.path.join(self.eiispath, packet_name)
        return os.path.exists(fp)

    def claim_packet(self, packet_name):
        status = self.get_local_packet_status(packet_name)
        if status == Status.removed:
            pack_new = os.path.join(self.eiispath, packet_name)
            pack_old = '{}.removed'.format(pack_new)
            shutil.move(pack_old, pack_new)
        return self.local_packet_exists(packet_name)

    def parse_data_by_action(self, seq, action):
        ''''''
        if action == Action.install:
            self.logger.info('Обработка пакетов на установку:')
            for packet in seq:
                packet_is_present = self.claim_packet(packet)
                files = self.remote_index[packet]['files']
                for file in files:
                    if packet_is_present:
                        fp = os.path.join(self.eiispath, packet, file)
                        if file_hash_calc(fp) == files[file]:
                            continue

                    packname = packet
                    action = Action.install
                    src = file
                    crc = files[file]

                    yield packname, action, src, crc

        elif action == Action.update:
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
            for packet in seq:
                # yield packet, Action.delete, None, None
                yield packet

        else:
            raise TypeError('Тип задачи неопределен')

    def get_task(self) -> namedtuple:
        '''Составление реестра обновленных файлов'''
        for key in ('install', 'update'):
            source_data = self.action_list[key]

            for packname, action, src, crc in source_data:
                task = namedtuple('Task', ('action', 'src', 'dst', 'crc'))

                task.action = action
                if action == Action.delete:
                    task.src = os.path.join(self.eiispath, packname, src)  # путь файла для удаления
                    task.dst = None
                else:
                    task.src = os.path.join(self.disp.repopath, packname, src)  # путь файла-источника для получения
                    task.dst = os.path.join(self.buffer, packname, src)
                task.crc = crc

                yield task

    def get_new_files(self):
        '''Получить новые файлы из репозитория'''
        start_time = datetime.timestamp(datetime.now())

        main_queue = Queue(maxsize=self.threads * self.task_queue_k)
        count_queue = Queue()

        for i in range(self.threads):
            disp = get_dispatcher(self.repo, encode=self.encode, queue=count_queue)
            worker = Worker(main_queue, disp)
            worker.setName('{}'.format(worker))
            worker.setDaemon(True)
            worker.start()

        # update_gauge_data = Gauge(2, self.callback, count_queue, self.files_count)
        # update_gauge_data.start()

        gen_task = self.get_task()

        for task in gen_task:
            main_queue.put(task)

        main_queue.join()
        count_queue.join()

        # update_gauge_data.cancel()

        return datetime.timestamp(datetime.now()) - start_time

    def install_packets(self):
        '''Копирование пакетов из буфера в папку установки'''
        for packet in os.listdir(self.buffer):
            src = os.path.join(self.buffer, packet)

            if not os.path.isdir(src):
                continue

            try:
                for top, _, files in os.walk(src, topdown=False):
                    for file in files:
                        s = os.path.join(top, file)
                        d = os.path.join(self.eiispath, os.path.relpath(s, self.buffer))
                        try:
                            shutil.copy2(s, d)
                        except FileNotFoundError:  # нет директории на месте назначения
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copy2(s, d)

            except Exception as err:
                self.logger.error('ошибка установки пакета {}'.format(packet))
                raise PacketInstallError from err
            else:
                self.logger.info('{} установлен'.format(packet))

    def update_links(self):
        pass

    def buffer_is_empty(self):
        try:
            count = len(os.listdir(self.buffer))
        except FileNotFoundError:
            return True
        else:
            return count == 0

    def create_shortcut(self, title, exe_file_path):
        """
        Создание ярлыка запуска подсистемы

        :param title:           Наименование подсистемы
        :param exe_file_path:   Путь к исполняемому файлу
        :return:                Путь к ярлыку на рабочем столе
        """
        try:
            import winshell
            from win32com.client import Dispatch
        except ImportError as err:
            self.logger.error('** Не удалось установить ярлык для "{}"'.format(title))
            self.logger.debug('ошибка импорта: {}'.format(err))
            return
        else:
            desktop = winshell.desktop()
            lnpath = os.path.join(desktop, title + '.lnk')
            target = icon = exe_file_path
            # workdir = os.path.join(os.path.expandvars('%USERPROFILE%'), 'EIIS', title)
            workdir = os.path.dirname(exe_file_path)
            shell = Dispatch('WScript.Shell')

            shortcut = shell.CreateShortCut(lnpath)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = workdir
            shortcut.IconLocation = icon
            shortcut.save()

            return lnpath

    def _clean_buffer(self):
        pass


class Worker(threading.Thread):
    files_faulted = Counter()
    max_repeat = 5
    stop_retrieve = threading.Event()

    def __init__(self, queue, dispatcher, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.queue = queue
        self.dispatcher = dispatcher

    def __repr__(self):
        return '<Worker-{}>'.format(id(self))

    def run(self):
        while True:
            if self.stop_retrieve.is_set():
                raise StopIteration

            if self.dispatcher.repo_is_busy():
                self.stop_retrieve.set()
                raise StopIteration

            task = self.queue.get()

            if task.action == Action.delete:
                self.remove_file(task.src)
            else:
                fp = self.dispatcher.get_file(task.src)

                if not file_hash_calc(fp) == task.crc:
                    self.files_faulted[task.src] += 1
                    fault_count = self.files_faulted.get(task.src)
                    if fault_count is not None and fault_count > self.max_repeat:
                        raise IOError('Не удалось загрузить файл {}'.format(fault_count))
                    self.queue.put(task)
                else:
                    self.dispatcher.move(fp, task.dst)
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

# class Gauge(threading.Timer):
#     ''''''
#
#     def __init__(self, interval, callback, queue: Queue, files_volume: int,  *args, **kwargs):
#         super().__init__(interval, self.get_sum, *args, **kwargs)
#         self.callback = callback
#         self.queue = queue
#         self.files_volume = files_volume
#         self.got_volume = 0
#
#     def get_sum(self, *args, **kwargs):
#         ''''''
#         with self.queue.mutex:
#             summ = sum([s for s in self._get_item()])
#         self.got_volume += summ
#         self.callback(self.got_volume / self.files_volume)
#
#     def _get_item(self):
#         while self.queue.full():
#             yield self.queue.get(block=False)
