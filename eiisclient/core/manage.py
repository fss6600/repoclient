# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import logging
import os
import shutil
import sys
import threading
import weakref
from collections import Counter, namedtuple
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from queue import Empty, Queue

import pythoncom

try:
    import winshell, win32con
except ImportError:
    NOLINKS = True
else:
    NOLINKS = False

from eiisclient import (DEFAULT_INSTALL_PATH, PROFILE_INSTALL_PATH,
                        SELECTED_FILE_NAME, WORK_DIR, __version__)
from eiisclient.core.dispatch import BaseDispatcher, get_dispatcher
from eiisclient.core.eiisreestr import REESTR
from eiisclient.core.exceptions import (DispatcherActivationError, DispatcherNotActivated,
                                        DownloadPacketError, LinkUpdateError, PacketDeleteError, RepoIsBusy,
                                        PacketInstallError, LinkDisabled, LinkNoData)
from eiisclient.core.utils import file_hash_calc, from_json, get_temp_dir, to_json, chwmod

CONFIGFILE = os.path.normpath(os.path.join(WORK_DIR, 'config.json'))
INDEXFILE = os.path.normpath(os.path.join(WORK_DIR, 'index.json'))


def get_stdout_logger() -> logging.Logger:
    logger = logging.Logger(__name__)
    con_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(con_handler)
    logger.setLevel(logging.INFO)
    return logger


class Action(Enum):
    ''''''
    install, update, delete = range(3)


class Status(Enum):
    installed, removed, purged = range(3)


class Manager(object):
    """"""

    def __init__(self, config, **kwargs):
        for k, v in config.items():
            setattr(self, k, v)
        self.logger = kwargs.get('logger', get_stdout_logger())
        self.full = kwargs.get('full', False)

        self.eiispath = PROFILE_INSTALL_PATH if self.install_to_profile else DEFAULT_INSTALL_PATH
        self.tempdir = get_temp_dir(prefix='eiis_man_tmp_')
        self.buffer = os.path.join(WORK_DIR, 'buffer')
        self.task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки
        self.local_index_file = os.path.join(WORK_DIR, 'index.json')
        self.local_index_file_hash = os.path.join('{}.sha1'.format(self.local_index_file))
        self.selected_packets_list_file = os.path.join(WORK_DIR, SELECTED_FILE_NAME)
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
        """"""
        #  определение action_list на установку, обновление и удаление
        install, update, delete = self.get_lists_difference(installed, selected)

        try:
            self.activate()

            self.action_list['install'] = self.parse_data_by_action_gen(install, Action.install)
            self.action_list['update'] = self.parse_data_by_action_gen(update, Action.update)
            self.action_list['delete'] = self.parse_data_by_action_gen(delete, Action.delete)

            # деактивация пакетов, помеченных на удаление
            self.delete_packages()

            # загрузка файлов пакетов из репозитория
            self.handle_files()

            # перемещение скачанных пакетов из буфера в папку установки
            if self.buffer_is_empty():
                self.logger.info('НЕТ ПАКЕТОВ ДЛЯ УСТАНОВКИ ИЛИ ОБНОВЛЕНИЯ')
            else:
                self.logger.info('Перенос пакетов из буфера в папку установки:')
                self.install_packets(selected)

            # запись данных нового индекса и контрольной суммы
            if not os.path.exists(WORK_DIR):
                os.makedirs(WORK_DIR, exist_ok=True)

            with open(self.local_index_file, 'w') as fp_index, open(self.local_index_file_hash, 'w') as fp_hash:
                fp_index.write(to_json(self.remote_index))
                fp_hash.write(self.remote_index_hash)

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
            self.disp = get_dispatcher(self.repopath, logger=self.logger, encode=self.encode,
                                       ftpencode=self.ftpencode, tempdir=self.tempdir)
        except ConnectionError as err:
            self.logger.error('Ошибка активации диспетчера для репозитория {}'.format(self.repopath))
            self.logger.error('Сервер недоступен или введен неправильный путь к репозиторию')
            raise DispatcherActivationError from err

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
        if self.disp:
            self.disp.close()
        self.disp = None
        self.action_list = {}
        self.local_index = None
        self.local_index_hash = None
        self.remote_index = None
        self.remote_index_hash = None

    def get_info(self) -> dict:
        no_data = 'Нет данных'
        packets_in_repo = no_data
        local_index_last_change = no_data
        remote_index_last_change = no_data
        repo_updated = no_data
        try:
            self.activate()

            if os.path.exists(self.local_index_file):
                local_index_last_change = os.path.getmtime(self.local_index_file)
                local_index_last_change = datetime.fromtimestamp(local_index_last_change).strftime('%d-%m-%Y %H:%M:%S')

            remote_index_last_change = self.disp.index_create_date.strftime('%d-%m-%Y %H:%M:%S')

            packets_in_repo = len(self.remote_index.keys())
            repo_updated = 'Да' if self.repo_updated() else 'Нет'

        except DispatcherActivationError:
            pass

        finally:
            self.deactivate()

        info = {
            'Версия программы': __version__,
            'Пакетов в репозитории': packets_in_repo,
            'Установлено подсистем': len(self.get_installed_packages()),
            'Дата последнего обновления': local_index_last_change,
            'Дата обновления на сервере': remote_index_last_change,
            'Наличие обновлений': repo_updated,
            'Пакетов в буфере': self.buffer_count(),
            'Путь - подсистемы': self.eiispath,
            'Путь - репозиторий': self.repopath,
            }
        return info

    def get_installed_packages(self) -> tuple:
        '''Список активных подсистем

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список.'''

        if os.path.exists(self.eiispath):
            active_list = (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
            return tuple(sorted((name for name in active_list if not name.endswith('.removed'))))
        else:
            return tuple()

    def get_selected_packages(self) -> tuple:
        try:
            with open(self.selected_packets_list_file) as fp:
                return tuple(
                    line.strip() for line in fp.readlines() if not any([line.startswith('#'), line.rstrip() == '']))
        except FileNotFoundError:
            return tuple()

    def get_removed_packages(self) -> tuple:
        if os.path.exists(self.eiispath):
            active_list = (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
            return tuple(sorted((name for name in active_list if name.endswith('.removed'))))
        else:
            return tuple()

    @staticmethod
    def get_lists_difference(installed: Iterable, selected: Iterable) -> tuple:
        common = set(installed) & set(selected)
        install = sorted(set(selected) ^ common)
        delete = sorted(set(installed) ^ common)
        update = sorted(common)

        return install, update, delete

    def delete_packages(self):
        for package in self.action_list['delete']:
            pack_path = os.path.join(self.eiispath, package)
            if self.purge:
                try:
                    self._remove_dir(pack_path)
                except Exception as err:
                    self.logger.error('- ошибка удаления пакета {}: {}'.format(package, err))
                else:
                    self.logger.info('{} - удален'.format(package))
                    continue

            try:
                new_pack_path = '{}.removed'.format(pack_path)
                os.rename(pack_path, new_pack_path)
            except Exception as err:
                self.logger.debug('- ошибка удаления пакета {}: {}'.format(package, err))
                raise PacketDeleteError
            else:
                self.logger.info('{} - помечен как удаленный'.format(package))

            # удаление ярлыка подсистемы
            try:
                self.remove_shortcut(package)
                self.logger.debug('Удален ярлык для {}'.format(package))
            except LinkUpdateError:
                self.logger.error('ошибка удаления ярлыка для {}'.format(package))

    def set_full(self, value=False):
        self.full = value

    def clean_removed(self):
        for packet in os.listdir(self.eiispath):
            try:
                if packet.endswith('.removed'):
                    fp = os.path.join(self.eiispath, packet)
                    self._remove_dir(fp)
            except Exception as err:
                raise PacketDeleteError(err)

    def get_remote_index(self) -> dict:
        self.check_repo()  # ???

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

    def get_remote_index_create_date(self):
        return self.disp.index_create_date

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

        res = self.local_packet_exists(packet_name)
        self.logger.debug('Проверка на наличие уже установленного пакета: {}'.format(res))
        return res

    def parse_data_by_action_gen(self, seq, action):
        ''''''
        if action == Action.install:
            self.logger.info('Обработка данных на установку пакетов:')
            for package in seq:
                self.logger.info('\tустановка - "{}"'.format(package))
                self.claim_packet(package)
                files = self.remote_index[package]['files']

                for file in files:
                    hash = files[file]

                    if not self.file_is_exist(package, file, hash):
                        packname = package
                        action = Action.install
                        src = file
                        crc = hash
                        yield packname, action, src, crc

        elif action == Action.update:
            self.logger.info('Обработка данных на обновление пакетов:')
            for package in seq:
                if self.local_index.get(package, None) is None:  # первый запуск
                    self.local_index[package] = {'hash': '', 'files': {}, 'phash': ''}

                if self.full or not self.local_index[package]['phash'] == self.remote_index[package]['phash']:
                    self.logger.info('\tобновление - "{}"'.format(package))
                    local_files = self.local_index[package]['files']
                    remote_files = self.remote_index[package]['files']

                    install, update, delete = self.get_lists_difference(local_files.keys(), remote_files.keys())

                    for act, lst in zip((Action.install, Action.update, Action.delete), (install, update, delete)):
                        if not len(lst):
                            self.logger.debug('{}: action: {} список файлов пуст'.format(package, act))
                            continue

                        if act == Action.delete:
                            for file in lst:
                                yield package, act, file, None

                        else:
                            for file in lst:
                                dst = os.path.join(self.eiispath, package, file)
                                if act == Action.update and os.path.exists(dst) and local_files[file] == remote_files[
                                    file]:
                                    continue

                                hash = remote_files[file]

                                if not self.file_is_exist(package, file, hash):
                                    yield package, act, file, hash

        elif action == Action.delete:
            self.logger.info('Обработка данных на удаление пакетов:')
            for package in seq:
                self.logger.info('\tудаление - "{}"'.format(package))
                yield package

        else:
            raise TypeError('Тип задачи неопределен')

    def get_task(self) -> namedtuple:
        '''Составление реестра обновленных файлов'''
        for key in ('install', 'update'):
            source_data = self.action_list[key]

            # done = Counter()
            for packname, action, src, crc in source_data:
                # if packname not in done.keys():
                #     self.logger.info('- {}'.format(packname))
                # done[packname] += 1

                task = namedtuple('Task', ('packetname', 'action', 'src', 'dst', 'crc'))

                task.packetname = packname
                task.action = action
                if action == Action.delete:
                    task.src = os.path.join(self.eiispath, packname, src)  # путь файла для удаления
                    task.dst = None
                else:
                    task.src = os.path.join(self.disp.repopath, packname, src)  # путь файла-источника для получения
                    task.dst = os.path.realpath(os.path.join(self.buffer, packname, src))
                task.crc = crc

                yield task

    def handle_files(self):
        '''Получить новые файлы из репозитория или удалить локально старые'''

        main_queue = Queue()  # todo: пересмотреть работу с асинхронной очередью, ввиду блокировки из-за ожидания
        # main_queue = Queue(maxsize=self.threads * self.task_queue_k)

        for task in self.get_task():  # загрузка очереди
            main_queue.put(task)
        self.logger.debug('Запущена очередь загрузки файлов')

        if main_queue.empty():  # очередь пустая - выходим
            self.logger.debug('Очередь пустая')

        else:
            stopper = threading.Event()
            exc_queue = Queue()
            error = False
            workers = []

            for i in range(self.threads):
                dispatcher = get_dispatcher(self.repopath, encode=self.encode, ftpencode=self.ftpencode,
                                            logger=self.logger)
                worker = Worker(main_queue, exc_queue, stopper, dispatcher, logger=self.logger)
                worker.setName('{}'.format(worker))
                worker.setDaemon(True)
                workers.append(worker)

            for worker in workers:  # стартуем пчелок
                worker.start()
            # todo: добавить обработку очередей в цикл While
            self.logger.info('Обработка очереди загрузки/удаление пакетов:')
            main_queue.join()  # ожидаем окончания обработки очереди
            stopper.set()

            while True:
                try:
                    exc = exc_queue.get(block=False)
                except Empty:
                    break
                else:
                    self.logger.error(exc)
                    error = True
            if error:
                raise DownloadPacketError('Ошибка при загрузке пакетов из репозитория. Пакеты не будут установлены '
                                          'или обновлены')
            else:
                self.logger.info('Загрузка файлов завершена')

    def install_packets(self, selected: Iterable):
        '''Перемещение пакетов из буфера в папку установки'''
        for package in self.buffer_content():
            if not package in selected:  # возможно пакет остался с прошлой неудачной установки
                self.logger.debug('{} есть в буфере, но нет в списке устанавливаемых пакетов - пропуск'.format(package))
                continue

            src = os.path.join(self.buffer, package)
            dst = os.path.join(self.eiispath, package)

            try:
                self.move_package(src, dst)
            except PermissionError:
                raise PacketInstallError('Недостаточно прав на установку пакета {} в {}'.format(package, self.eiispath))
            except Exception as err:
                raise PacketInstallError('Ошибка при установке пакета {}: {}'.format(package, err))
            else:
                self.logger.debug('\t{} перемещен из буфера в {}'.format(package, dst))
                self.logger.info('\tобработан - "{}"'.format(package))

    def update_links(self):
        self.logger.info('Обновление ярлыков на рабочем столе')
        for packet in self.get_installed_packages():
            try:
                title, exe_file_path = self._get_link_data(packet)
                self.create_shortcut(title, exe_file_path)
            except (LinkDisabled, LinkNoData) as err:
                self.logger.error('Ярлык не создан {}'.format(err))
            except LinkUpdateError as err:
                self.logger.error('Ошибка создания ярлыка: {}'.format(err))

    def create_shortcut(self, title, exe_file_path):
        """
        Создание ярлыка запуска подсистемы

        :param
        """
        if NOLINKS:
            raise LinkDisabled('- отсутствует библиотека win32')

        if not exe_file_path:
            raise LinkNoData(
                '- недостаточно данных для создания ярлыка для {}. Проверьте реестр подсистем'.format(title))

        workdir = os.path.dirname(exe_file_path)
        lnpath = os.path.join(winshell.desktop(), '{}.lnk'.format(title))

        try:
            pythoncom.CoInitialize()  # для работы в threads
            with winshell.shortcut(lnpath) as lp:
                if lp.path == exe_file_path:
                    return
                lp.path = exe_file_path
                lp.description = 'Запуск подсистемы "{}" ЕИИС Соцстрах РФ'.format(title)
                lp.working_directory = workdir
                lp.write()
                self.logger.debug('создан ярлык: {}'.format(lnpath))
        except Exception as err:
            raise LinkUpdateError from err

    def remove_shortcut(self, packet):
        title, _ = self._get_link_data(packet)

        link_path = os.path.join(self.desktop, title + '.lnk')
        try:
            os.unlink(link_path)
        except PermissionError:
            chwmod(link_path)
            os.unlink(link_path)
        except FileNotFoundError:
            pass

    def _clean(self):
        self.tempdir.cleanup()

    def clean_buffer(self) -> bool:
        done = True
        packs = self.buffer_content()
        if packs:
            for pack in packs:
                try:
                    path = os.path.join(self.buffer, pack)
                    self._remove_dir(path)
                except Exception:
                    done = False
                    self.logger.error('Ошибка при удалении пакета {} из буфера'.format(pack))

        return done

    def _get_link_data(self, packet) -> tuple:
        try:
            title = self.remote_index[packet].get('title') or self.remote_index[packet].get('title') or packet
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
        self.logger.debug('{}: repo: {}'.format(self, self.repopath))
        self.logger.debug('{}: eiis: {}'.format(self, self.eiispath))
        self.logger.debug('{}: buffer: {}'.format(self, self.buffer))
        self.logger.debug('{}: encode: {}'.format(self, self.encode))
        self.logger.debug('{}: tempdir: {}'.format(self, self.tempdir.name))
        self.logger.debug('{}: task_k: {}'.format(self, self.task_queue_k))
        self.logger.debug('{}: purge: {}'.format(self, self.purge))

    def _remove_dir(self, fpath):
        """Удаление директории с файлами"""
        for top, _, files in os.walk(fpath, topdown=False):
            for file in files:
                fp = os.path.join(top, file)
                try:
                    self.logger.debug('[1] удаление {}'.format(fp))
                    os.unlink(fp)
                except PermissionError:
                    self.logger.debug('[2] удаление {}'.format(fp))
                    chwmod(fp)
                    try:
                        os.unlink(fp)
                    except Exception as err:
                        self.logger.debug('ошибка удаления {}'.format(fp))
                        raise IOError(err)
                except FileNotFoundError:
                    self.logger.debug('удаление {} - не найден'.format(fp))
                    pass

            try:
                self.logger.debug('[1] удаление {}'.format(top))
                os.rmdir(top)
            except PermissionError:
                chwmod(top)
                self.logger.debug('[2] удаление {}'.format(top))
                os.rmdir(top)
            except FileNotFoundError:
                self.logger.debug('удаление {} - не найден'.format(top))
                pass

    def file_is_exist(self, package, file, hashsum):
        for path in (self.eiispath, self.buffer):
            fp = os.path.join(path, package, file)
            if os.path.exists(fp) and file_hash_calc(fp) == hashsum:
                self.logger.debug('пропуск - файл уже присутствует: {}'.format(fp))
                return True

        return False

    def copy_package(self, src, dst):
        for top, _, files in os.walk(src, topdown=False):
            for file in files:
                s = os.path.join(top, file)
                d = os.path.join(os.path.dirname(dst), os.path.relpath(s, os.path.dirname(src)))
                try:
                    self.logger.debug('[1] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except FileNotFoundError:  # нет директории в месте назначения
                    dname = os.path.dirname(d)
                    try:
                        os.makedirs(dname, exist_ok=True)
                    except Exception as err:
                        self.logger.debug('Make dir error: {}'.format(err))
                        raise
                    self.logger.debug('создана папка {}'.format(dname))
                    self.logger.debug('[2] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except PermissionError:
                    try:
                        chwmod(d)
                    except Exception as err:
                        self.logger.debug('Chmod error: {}'.format(err))
                        raise
                    self.logger.debug('[3] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except Exception as err:
                    self.logger.debug('Error: {}'.format(err))
                    raise

    def move_package(self, src, dst):
        self.logger.debug('moving from: {} -> {}'.format(src, dst))
        self.copy_package(src, dst)
        self._remove_dir(src)


class Worker(threading.Thread):
    files_faulted = Counter()
    packages_started = set()
    max_repeat = 3

    def __init__(self, queue: Queue, exc_queue: Queue, stopper: threading.Event, dispatcher: BaseDispatcher,
                 logger=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.queue = queue
        self.exceptions = exc_queue
        self.dispatcher = dispatcher
        self.logger = logger or get_stdout_logger()
        self.stopper = stopper

    def __repr__(self):
        return '<Worker-{}>'.format(id(self))

    def run(self):
        try:
            while True:
                if self.stopper.is_set():
                    self.logger.debug('{}: обнаружен стоп-флаг. выходим'.format(self))
                    break

                if self.dispatcher.repo_is_busy():
                    self.logger.debug('{}: репозиторий заблокирован. выходим'.format(self))
                    break

                try:
                    task = self.queue.get(timeout=2)
                except Empty:
                    pass
                else:
                    task_id = id(task)
                    self.logger.debug(
                        '{}<task-{}> ({}|{}|{})'.format(self, task_id, task.packetname, task.action, task.src))

                    if not task.packetname in self.packages_started:  # для вывода информации о загрузке пакета
                        self.packages_started.add(task.packetname)
                        new_pack = True
                    else:
                        new_pack = False

                    if task.action == Action.delete:
                        if new_pack:
                            self.logger.info('\tудаляется "{}"'.format(task.packetname))
                        self.remove_file(task.src)
                    else:
                        if new_pack:
                            self.logger.info('\tзагружается "{}"'.format(task.packetname))
                        fp = self.dispatcher.get_file(task.src)
                        hash_sum = file_hash_calc(fp)

                        if not hash_sum == task.crc:
                            self.files_faulted[task.src] += 1
                            fault_count = self.files_faulted.get(task.src)
                            self.logger.debug(
                                '{}<task-{}> <{} != {}> [{}]'.format(self, task_id, hash_sum, task.crc, fault_count))
                            if fault_count is not None and fault_count > self.max_repeat - 1:
                                self.exceptions.put('Неверная контрольная сумма файла "{}" из пакета "{}"'.format(
                                    os.path.basename(task.src), task.packetname))
                            else:
                                # fixme: при установленном максимальном размере, вставка в очередь блокирует процесс. перерсмотреть на возможность асинхронной работы
                                self.queue.put(task)
                        else:
                            try:
                                self.logger.debug('{}<task-{}> move {} -> {}'.format(self, task_id, fp, task.dst))
                                self.dispatcher.move(fp, task.dst)  # move to buffer
                            except IOError as err:
                                self.exceptions.put(
                                    '{}<task-{}> Ошибка переноса в буфер файла "{}" из пакета "{}": {}'.format(
                                        self, task_id, os.path.basename(task.src), task.packetname, err))

                    self.queue.task_done()
        finally:
            self.logger.debug('{}: работу завершил'.format(self))
            self.dispatcher.close()

    def remove_file(self, fpath):
        try:
            os.unlink(fpath)
        except FileNotFoundError:
            pass
        except (PermissionError) as err:
            self.logger.debug('ошибка при удалении файла: {}: {}'.format(fpath, err))
            chwmod(fpath)
            try:
                os.unlink(fpath)
            except Exception:
                self.logger.debug('ошибка {}: файл {} не удален'.format(err, fpath))
