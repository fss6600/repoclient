# -*- coding: utf-8 -*-
from __future__ import print_function

import logging
import os
import shutil
import threading
import weakref
from collections import Counter, OrderedDict, namedtuple
from collections.abc import Iterable, Iterator
from datetime import datetime
from enum import Enum
from queue import Empty, Queue

import pythoncom
import winshell

from eiisclient import DEFAULT_ENCODING, DEFAULT_FTP_ENCODING, WORK_DIR, PROFILE_INSTALL_PATH, DEFAULT_INSTALL_PATH
from eiisclient.dispatch import BaseDispatcher, get_dispatcher
from eiisclient.exceptions import (DispatcherActivationError, DownloadPacketError, LinkUpdateError, NoUpdates,
                                   PacketDeleteError, RepoIsBusy, PacketInstallError, LinkDisabled, LinkNoData)
from eiisclient.utils import (file_hash_calc, from_json, get_temp_dir, to_json, chwmod, get_config_data)
from eiisclient.structures import (PackList, Status, ConfigDict, PackStatus, PackData)


def get_stdout_logger() -> logging.Logger:
    return logging.Logger(__name__)


class Manager(object):
    """
    Основной обработчик пакетов на клиенте.
    """

    def __init__(self, logger=None, **kwargs):
        # инициализация параметров
        self.config = ConfigDict()
        self.config.repopath = None
        self.config.threads = 1
        self.config.purge = False
        self.config.encode = DEFAULT_ENCODING
        self.config.ftpencode = DEFAULT_FTP_ENCODING
        self.config.install_to_profile = False
        if not os.path.exists(WORK_DIR):
            os.makedirs(WORK_DIR, exist_ok=True)
        # обновление параметров из файла настроек
        self.config.update(get_config_data(WORK_DIR))
        #
        self.full = False
        self.eiispath = PROFILE_INSTALL_PATH if self.config.install_to_profile else DEFAULT_INSTALL_PATH
        self.tempdir = get_temp_dir(prefix='eiis_man_tmp_')
        self.buffer = os.path.join(WORK_DIR, 'buffer')
        self.task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки
        self.local_index_file = os.path.join(WORK_DIR, 'index.json')
        self.local_index_file_hash = os.path.join('{}.sha1'.format(self.local_index_file))
        self._pack_list = self._get_pack_list(False)  # dict - перечень пакетов со статусами
        self._info_list = self._get_info_list(False)  # dict - информация о репозитории, установленных пакетах,..
        self._desktop = winshell.desktop()
        self._finalize = weakref.finalize(self, self._clean)

        self.disp = None
        self.logger = logger or get_stdout_logger()
        if self.logger.level == logging.DEBUG:
            self._init_log()

    def __repr__(self):
        return '<Manager: {}>'.format(id(self))

    @property
    def pack_list(self):
        return self._pack_list

    @property
    def info_list(self):
        return self._info_list

    def check_updates(self):
        try:
            self._activate()
            self.check_repo()

            if not self.repo_updated:
                raise NoUpdates

            self._pack_list = self._get_pack_list(remote=True)
            self._info_list = self._get_info_list(remote=True)

        finally:
            self._deactivate()

    def start_update(self):
        """"""
        #  определение action_list на установку, обновление и удаление
        # install, update, delete = self.get_lists_difference(
        #     self.get_installed_packages(), selected=selected
        # )

        try:
            # self.activate()
            # self.action_list['install'] = self.parse_data_by_action_gen(install, Action.install)
            # self.action_list['update'] = self.parse_data_by_action_gen(update, Action.update)
            # self.action_list['delete'] = self.parse_data_by_action_gen(delete, Action.delete)

            # загрузка файлов пакетов из репозитория
            self.handle_files(pack_list)

            # деактивация пакетов, помеченных на удаление
            self.delete_packages()

            # перемещение скачанных пакетов из буфера в папку установки
            if self.buffer_is_empty():
                self.logger.info('НЕТ ПАКЕТОВ ДЛЯ УСТАНОВКИ ИЛИ ОБНОВЛЕНИЯ')
            else:
                self.logger.info('Перенос пакетов из буфера в папку установки:')
                self.install_packets(selected)

            with open(self.local_index_file, 'w') as fp_index, open(self.local_index_file_hash, 'w') as fp_hash:
                fp_index.write(to_json(self.remote_index))
                fp_hash.write(self.remote_index_hash)

            # обновление ярлыков на рабочем столе
            self.update_links(pack_list)
        except Exception as err:

            self.logger.exception(err)
            self.logger.error('Ошибка при удалении пакета')

        finally:
            self._deactivate()

    def check_repo(self):
        """Проверка репозитория на регламентные работы"""
        if self.disp.repo_is_busy():
            raise RepoIsBusy

    @property
    def repo_updated(self) -> bool:
        """Проверка на наличие обновлений"""
        remote_index_hash = self.get_remote_index_hash()
        local_index_hash = self.get_local_index_hash()
        return not local_index_hash == remote_index_hash

    def buffer_content(self) -> list:
        if os.path.exists(self.buffer):
            return [pack for pack in os.listdir(self.buffer) if os.path.isdir(os.path.join(self.buffer, pack))]
        return []

    def buffer_count(self) -> int:
        return len(self.buffer_content())

    def buffer_is_empty(self) -> bool:
        return self.buffer_count() == 0

    # @property
    # def activated(self) -> bool:
    #     return True if self.disp else False

    def _activate(self):
        ''''''
        try:
            self.disp = get_dispatcher(self.config.repopath, logger=self.logger, encode=self.config.encode,
                                       ftpencode=self.config.ftpencode, tempdir=self.tempdir)
        except ConnectionError as err:
            self.logger.error('Ошибка активации диспетчера для репозитория {}'.format(self.config.repopath))
            self.logger.error('Сервер недоступен или введен неправильный путь к репозиторию')
            raise DispatcherActivationError from err

    def _deactivate(self):
        if self.disp:
            self.disp.close()
            self.disp = None

    def _get_info_list(self, remote=False) -> dict:
        packets_in_repo = None
        local_index_last_change = None
        remote_index_last_change = None
        repo_updated = None

        if remote:
            if os.path.exists(self.local_index_file):
                local_index_last_change = os.path.getmtime(self.local_index_file)
                local_index_last_change = datetime.fromtimestamp(local_index_last_change).strftime(
                    '%d-%m-%Y %H:%M:%S')
            remote_index_last_change = self.disp.index_create_date.strftime('%d-%m-%Y %H:%M:%S')
            packets_in_repo = len(self._get_remote_index().get('packages', {}))
            repo_updated = 'имеются обновления' if self.repo_updated else 'нет обновлений'

        info = OrderedDict()
        info.setdefault('Дата последнего обновления', local_index_last_change)
        info.setdefault('Дата обновления на сервере', remote_index_last_change)
        info.setdefault('Наличие обновлений', repo_updated)
        info.setdefault('Пакетов в репозитории', packets_in_repo)
        info.setdefault('Установлено подсистем', len(self._installed_packages()))
        info.setdefault('Пакетов в буфере', self.buffer_count())
        info.setdefault('Путь - подсистемы', self.eiispath)
        info.setdefault('Путь - репозиторий', self.config.repopath)

        return info

    def _get_local_packages(self) -> Iterator:
        """Возвращает имена всех директорий (пакетов) по пути установки подсистем"""
        if os.path.exists(self.eiispath):
            return (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
        else:
            return iter()

    def _installed_packages(self) -> list:
        """Список активных подсистем

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список."""
        return [name for name in self._get_local_packages() if not name.endswith('.removed')]

    def _removed_packages(self) -> list:
        return [name for name in self._get_local_packages() if name.endswith('.removed')]

    # @staticmethod
    # def get_lists_difference(installed: Iterable, selected: Iterable) -> tuple:
    #     common = set(installed) & set(selected)
    #     install = sorted(set(selected) ^ common)
    #     delete = sorted(set(installed) ^ common)
    #     update = sorted(common)
    #
    #     return install, update, delete

    def delete_packages(self):
        for package in self.action_list['delete']:
            pack_path = os.path.join(self.eiispath, package)
            if self.config.purge:
                try:
                    self._remove_dir(pack_path)
                except Exception as err:
                    self.logger.error('- ошибка удаления пакета {}: {}'.format(package, err))
                else:
                    self.logger.info('{} - удален'.format(package))

            else:
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

    def _get_remote_index(self) -> dict:
        try:
            return self.disp.get_index_data()
        except FileNotFoundError:
            self.logger.error('Не найден индекс-файл в репозитории')
            raise NoIndexFileOnServerError

    #
    # def get_remote_index_packages(self) -> dict:
    #     return self.get_remote_index().get('packages', {})

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

    #
    # def get_local_index_packages(self) -> dict:
    #     return self.get_local_index().get('packages', {})

    def get_local_index_hash(self) -> str:
        try:
            with open(self.local_index_file_hash) as fp:
                # return from_json(fp.read())
                return fp.read()
        except FileNotFoundError:
            return None
    #
    # def build_pack_list(self, remote=False):
    #     self._pack_list = self._get_pack_list(remote)

    def _get_pack_list(self, remote) -> PackList:
        pack_list = PackList()
        local_index_packs_cache = self.get_local_index().get('packages', {})
        if remote:
            remote_index_packages = self._get_remote_index().get('packages', {})
        else:
            remote_index_packages = None

        # заполняем данными из локального индекс-кэша
        for origin_pack_name in local_index_packs_cache:
            alias_pack_name = local_index_packs_cache[origin_pack_name].get('alias') or origin_pack_name
            status = PackStatus.NON

            if remote:
                if origin_pack_name in remote_index_packages:
                    # делаем сверку контрольных сумм пакетов
                    local_pack_hash = local_index_packs_cache[origin_pack_name]['phash']
                    remote_pack_hash = remote_index_packages[origin_pack_name]['phash']
                    if not local_pack_hash == remote_pack_hash:
                        status = PackStatus.UPD

                    # помечаем пакет на удаление, если алиасы отличаются - сменился на сервере
                    local_pack_alias = local_index_packs_cache[origin_pack_name]['alias']
                    remote_pack_alias = remote_index_packages[origin_pack_name]['alias']
                    if not local_pack_alias == remote_pack_alias:
                        status = PackStatus.DEL
                else:
                    # пакета нет в репозитории, но есть в локальном кэше
                    status = PackStatus.DEL

            pack_list[alias_pack_name] = PackData(
                origin=origin_pack_name,
                installed=False,
                status=status,
            )

        if remote:  #
            # заполняем данными из индекса с сервера
            for origin_pack_name in remote_index_packages:
                if origin_pack_name in local_index_packs_cache:
                    local_alias = local_index_packs_cache[origin_pack_name]['alias']
                    remote_alias = remote_index_packages[origin_pack_name]['alias']
                    if not remote_alias == local_alias:
                        alias_pack_name = remote_index_packages[origin_pack_name].get('alias') or origin_pack_name
                        pack_list[alias_pack_name] = PackData(
                            origin=origin_pack_name,
                            installed=False,
                            status=PackStatus.UPD,
                        )
                else:
                    alias_pack_name = remote_index_packages[origin_pack_name].get('alias') or origin_pack_name
                    pack_list[alias_pack_name] = PackData(
                        origin=origin_pack_name,
                        installed=False,
                        status=PackStatus.NEW,
                    )

        # обновляем статус установки имеющихся пакетов
        for origin_pack_name in self._installed_packages():
            _, pack_data = pack_list.get_by_origin(origin_pack_name)
            if pack_data:
                setattr(pack_data, 'installed', True)
            else:
                pack_list[origin_pack_name] = PackData(
                    origin=origin_pack_name,
                    installed=True,
                    status=PackStatus.DEL,
                )

        return pack_list

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
        """"""
        r_packages = self.remote_index.get('packages', {})  # get remote packages map
        l_packages = self.local_index.get('packages', {})  # get local packages map

        if action == Action.install:
            self.logger.info('Обработка данных на установку пакетов:')
            for package in seq:
                self.logger.info('\t"{}"'.format(package))
                self.claim_packet(package)
                files = r_packages[package]['files']

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
                if l_packages.get(package, None) is None:  # первый запуск
                    l_packages[package] = {'hash': '', 'files': {}, 'phash': ''}

                if self.full or not l_packages[package]['phash'] == r_packages[package]['phash']:
                    self.logger.info('\t"{}"'.format(package))
                    local_files = l_packages[package]['files']
                    remote_files = r_packages[package]['files']

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
                                if act == Action.update and os.path.exists(dst) and \
                                        local_files[file] == remote_files[file]:
                                    continue

                                hash = remote_files[file]

                                if not self.file_is_exist(package, file, hash):
                                    yield package, act, file, hash

        elif action == Action.delete:
            self.logger.info('Обработка данных на удаление пакетов:')
            for package in seq:
                self.logger.info('\t"{}"'.format(package))
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

                task = namedtuple('Task', ('packetname', 'action', 'src', 'dst', 'crc'))  # todo вынести перед циклом

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
        # main_queue = Queue(maxsize=self.config.threads * self.task_queue_k)

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

            for i in range(self.config.threads):
                dispatcher = get_dispatcher(self.config.repopath,
                                            encode=self.config.encode,
                                            ftpencode=self.config.ftpencode,
                                            logger=self.logger)
                worker = Worker(main_queue, exc_queue, stopper, dispatcher, logger=self.logger)
                worker.setName('{}'.format(worker))
                worker.setDaemon(True)
                workers.append(worker)

            try:
                for worker in workers:  # стартуем пчелок
                    worker.start()
                self.logger.info('Обработка очереди загрузки/удаление пакетов:')
                main_queue.join()  # ожидаем окончания обработки очереди
                stopper.set()
            except Exception:
                raise DownloadPacketError('Ошибка при загрузке пакетов из репозитория. Пакеты не будут установлены '
                                          'или обновлены')

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
            if package not in selected:  # возможно пакет остался с прошлой неудачной установки
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
                self.logger.info('\tустановлен - "{}"'.format(package))

    def update_links(self):
        self.logger.info('Обновление ярлыков на рабочем столе')
        for packet in self._installed_packages():
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
        link_path = os.path.join(self._desktop, title + '.lnk')
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
            alias = self.remote_index.get('packages', {})[packet].get('alias') or packet
            alias = alias.lstrip('"').rstrip('"')
        except:
            alias = packet
        try:
            execf = self.remote_index.get('packages', {})[packet].get('execf')
            execf_path = os.path.join(self.eiispath, packet, execf) if execf else None
        except:
            execf_path = None

        return alias, execf_path

    def _init_log(self):
        self.logger.debug('{}: repo: {}'.format(self, self.config.repopath))
        self.logger.debug('{}: eiis: {}'.format(self, self.eiispath))
        self.logger.debug('{}: buffer: {}'.format(self, self.buffer))
        self.logger.debug('{}: encode: {}'.format(self, self.config.encode))
        self.logger.debug('{}: tempdir: {}'.format(self, self.tempdir.name))
        self.logger.debug('{}: task_k: {}'.format(self, self.task_queue_k))
        self.logger.debug('{}: purge: {}'.format(self, self.config.purge))

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
                    self.logger.debug('Copy pack Error: {}'.format(err))
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

                    if task.packetname not in self.packages_started:  # для вывода информации о загрузке пакета
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
                        try:
                            fp = self.dispatcher.get_file(task.src)
                        except Exception as err:
                            self.exceptions.put('Ошибка загрузки файла {} пакета {}: {}'.format(
                                os.path.basename(task.src),
                                task.packetname,
                                err
                            ))
                            self.exceptions.put('Требуется ре-индексация репозитория')
                            self.queue.task_done()
                            break
                        else:
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
                                # fixme: при установленном максимальном размере, вставка в очередь блокирует процесс.
                                # перерсмотреть на возможность асинхронной работы
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
