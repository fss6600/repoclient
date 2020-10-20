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
from time import sleep
from tempfile import TemporaryDirectory

import pythoncom
import winshell

from eiisclient import (DEFAULT_ENCODING, DEFAULT_FTP_ENCODING, WORK_DIR, PROFILE_INSTALL_PATH,
                        DEFAULT_INSTALL_PATH, CONFIGFILE)
from eiisclient.dispatch import BaseDispatcher, get_dispatcher
from eiisclient.exceptions import (DispatcherActivationError, DownloadPacketError, LinkUpdateError, NoUpdates,
                                   PacketDeleteError, RepoIsBusy, PacketInstallError, LinkDisabled, LinkNoData)
from eiisclient.utils import (file_hash_calc, unjsonify, jsonify, change_write_mod, read_file)
from eiisclient.structures import (PackList, ConfigDict, State, PackData, Task)

THREADS = 3


def get_stdout_logger() -> logging.Logger:
    return logging.Logger(__name__)


def get_config() -> ConfigDict:
    return ConfigDict(
        repopath=None,
        threads = THREADS,
        encode = DEFAULT_ENCODING,
        ftpencode = DEFAULT_FTP_ENCODING,
        install_to_profile = False,
    )


def read_config(encode: str=DEFAULT_ENCODING) -> dict:
    """
    Возвращает данные конфигурационного файла или пустой словарь

    :param workdir: полный путь к конфиг-файлу
    :param encode: кодировка файла
    :return: словарь с даннымим или пустой
    """
    try:
        with open(CONFIGFILE, encoding=DEFAULT_ENCODING) as cf:
            return unjsonify(cf.read())
    except FileNotFoundError:
        return {}


class Manager:
    """
    Основной обработчик пакетов на клиенте.
    """
    def __init__(self, logger=None, **kwargs):
        # инициализация параметров
        self.debug = False
        self.logger = logger or get_stdout_logger()
        self.config = get_config()
        if not os.path.exists(WORK_DIR):
            os.mkdir(WORK_DIR, exist_ok=True)
        # обновление параметров из файла настроек
        self.config.update(read_config())
        #

        self._local_index_file = os.path.join(WORK_DIR, 'index.json')
        self._local_index_file_hash = '{}.sha1'.format(self._local_index_file)
        self._eiispath = PROFILE_INSTALL_PATH if self.config.install_to_profile else DEFAULT_INSTALL_PATH
        self._tempdir = self._get_temp_dir()
        self._buffer = os.path.join(WORK_DIR, 'buffer')
        self._task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки
        self._pack_list = self._get_pack_list(False)  # dict - перечень пакетов со статусами
        self._info_list = self._get_info_list(False)  # dict - информация о репозитории, установленных пакетах,..
        self._desktop = winshell.desktop()
        self._finalize = weakref.finalize(self, self._clean)
        self._disp = None
        self._full = False

        if self.logger.level == logging.DEBUG:
            self.debug = True
            self.logger.debug('{}: repo: {}'.format(self, self.config.repopath))
            self.logger.debug('{}: eiis: {}'.format(self, self.eiispath))
            self.logger.debug('{}: buffer: {}'.format(self, self._buffer))
            self.logger.debug('{}: encode: {}'.format(self, self.config.encode))
            self.logger.debug('{}: tempdir: {}'.format(self, self._tempdir.name))
            self.logger.debug('{}: task_k: {}'.format(self, self._task_queue_k))

    def __repr__(self):
        return '<Manager: {}>'.format(id(self))

    @property
    def local_index_file(self):
        return self._local_index_file

    @property
    def local_index_file_hash(self):
        return self._local_index_file_hash

    @property
    def eiispath(self) -> str:
        return self._eiispath

    @property
    def pack_list(self):
        return self._pack_list

    @property
    def info_list(self):
        return self._info_list

    def check_updates(self):
        self.logger.info('Чтение данных репозитория\n')
        try:
            self.logger.debug('check_updates: активация диспетчера')
            self._tempdir = self._get_temp_dir()
            self._dispatcher_run()
            if self._disp.repo_is_busy():
                raise RepoIsBusy

            if not self.repo_updated:
                raise NoUpdates

            self._pack_list = self._get_pack_list(remote=True)
            self._info_list = self._get_info_list(remote=True)

        finally:
            self.logger.debug('check_updates: деактивация диспетчера')
            self._dispatcher_stop()

    def start_update(self):
        """
        Процедура обновления пакетов

        :return:
        """
        try:
            self._dispatcher_run()
            if self._disp.repo_is_busy():
                raise RepoIsBusy

            # 1 обновление/удаление пакетов
            self.logger.info('Формирование списка пакетов')
            action_list = {}
            for pack, data in self._pack_list.items():
                action = self._pack_list.get_action(pack)
                if action == State.UPD or action == State.NEW:
                    action_list.setdefault('update', []).append((pack, data))
                elif action == State.DEL:
                    action_list.setdefault('delete', []).append((pack, data))
            if self.debug:
                self.logger.debug(action_list)

            packs = action_list.get('update', [])
            if packs:
                self.logger.debug('start_update: активация диспетчера')
                # Step 1: формирование задач для обработки файлов пакетов из репозитория
                tasks = self.get_task(packs)
                # Step 2: обработка файлов пакета (загрузка или удаление)
                if self.debug:
                    ts_start = datetime.now()
                self.handle_tasks(tasks)
                if self.debug:
                    self.logger.debug('start_update: обработка выполнена за {}'.format(datetime.now() - ts_start))
                # Step 3: перемещение скачанных пакетов из буфера в папку установки
                if not self.buffer_is_empty():
                    # перенос файлов пакетов из буфера в папку назначения
                    self.flush_buffer(packs)
            else:
                self.logger.info('Нет пакетов для установки или обновления')

            # 2 удаление пакетов
            packs = action_list.get('delete', [])
            if packs:
                self.logger.info('Удаление пакетов:')
                self.delete_packages(packs)

            # 3 обновление ярлыков на рабочем столе
            # self.logger.info('Обновление ярлыков')
            # self.update_links(pack_list)
        except InterruptedError:
            pass
        except Exception as err:
            raise
        else:
            pass
            # with open(self.local_index_file, 'w') as fp_index, open(self.local_index_file_hash, 'w') as fp_hash:
            #     fp_index.write(jsonify(self.remote_index))
            #     fp_hash.write(self.remote_index_hash)
        finally:
            self._dispatcher_stop()

    def reset(self):
        self._pack_list = self._get_pack_list(False)  # dict - перечень пакетов со статусами
        self._info_list = self._get_info_list(False)

    @property
    def repo_updated(self) -> bool:
        """Проверка на наличие обновлений"""
        remote_index_hash = self.get_remote_index_hash()
        local_index_hash = self.get_local_index_hash()
        return not local_index_hash == remote_index_hash

    def buffer_content(self) -> list:
        if os.path.exists(self._buffer):
            return [pack for pack in os.listdir(self._buffer) if os.path.isdir(os.path.join(self._buffer, pack))]
        return []

    def buffer_count(self) -> int:
        return len(self.buffer_content())

    def buffer_is_empty(self) -> bool:
        return self.buffer_count() == 0

    def _dispatcher_run(self):
        """
        Активация диспетчера для работы с файлами
        :return:
        """
        try:
            self._disp = get_dispatcher(self.config.repopath, logger=self.logger, encode=self.config.encode,
                                        ftpencode=self.config.ftpencode, tempdir=self._tempdir)
        except ConnectionError as err:
            self.logger.error('Ошибка активации диспетчера для репозитория {}'.format(self.config.repopath))
            self.logger.error('Сервер недоступен или введен неправильный путь к репозиторию')
            raise DispatcherActivationError from err

    def _dispatcher_stop(self):
        """
        Деактивация диспетчера
        :return:
        """
        if self._disp:
            self._disp.close()
            self._disp = None

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
            remote_index_last_change = self._disp.index_create_date.strftime('%d-%m-%Y %H:%M:%S')
            packets_in_repo = len(self.get_remote_index().get('packages', {}))
            repo_updated = 'имеются обновления' if self.repo_updated else 'нет обновлений'

        info = OrderedDict()
        info.setdefault('Дата последнего обновления', local_index_last_change)
        info.setdefault('Дата обновления на сервере', remote_index_last_change)
        info.setdefault('Наличие обновлений', repo_updated)
        info.setdefault('Пакетов в репозитории', packets_in_repo)
        info.setdefault('Установлено подсистем', len(list(self._installed_packages())))
        info.setdefault('Пакетов в буфере', self.buffer_count())
        info.setdefault('Путь - подсистемы', self.eiispath)
        info.setdefault('Путь - репозиторий', self.config.repopath)

        return info

    # +
    def _installed_packages(self) -> Iterator:
        """
        Список установленных пакетов

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список.
        """
        if os.path.exists(self.eiispath):
            return (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
        else:
            return iter()

    def delete_packages(self, packages: list):
        self.logger.info('Удаление пакетов')
        for pack, pack_data in packages:
            fp = os.path.join(self.eiispath, pack_data.origin)
            try:
                self._remove_dir(fp)  # todo вынести в диспетчер
            except Exception as err:
                self.logger.error('Ошибка удаления пакета {}: {}'.format(pack, err))
            else:
                self.logger.info('\t`{}`'.format(pack))

            # удаление ярлыка подсистемы
            try:
                self.remove_shortcut(pack)
                self.logger.debug('delete_packages: удален ярлык для {}'.format(pack))
            except LinkUpdateError:
                self.logger.error('ошибка удаления ярлыка для {}'.format(packe))

    def set_full(self, value=False):
        self._full = value

    def get_remote_index(self) -> dict:
        try:
            return self._disp.remote_index()
        except FileNotFoundError:
            self.logger.error('Не найден индекс-файл в репозитории')
            raise NoIndexFileOnServerError

    #
    # def get_remote_index_packages(self) -> dict:
    #     return self.get_remote_index().get('packages', {})

    def get_remote_index_hash(self) -> str:
        return self._disp.remote_index_hash()

    def get_remote_index_create_date(self):
        return self._disp.index_create_date

    def get_local_index(self) -> dict:
        data = read_file(self.local_index_file)
        return unjsonify(data) if data else {}

    #
    # def get_local_index_packages(self) -> dict:
    #     return self.get_local_index().get('packages', {})

    def get_local_index_hash(self) -> str:
        return read_file(self.local_index_file_hash)

    # +
    def _get_pack_list(self, remote) -> PackList:
        pack_list = PackList()
        local_index_packs_cache = self.get_local_index().get('packages', {})
        if remote:
            remote_index_packages = self.get_remote_index().get('packages', {})
        else:
            remote_index_packages = None

        # заполняем данными из локального индекс-кэша
        for origin_pack_name in local_index_packs_cache:
            alias_pack_name = local_index_packs_cache[origin_pack_name].get('alias') or origin_pack_name
            status = State.NON

            if remote:
                if origin_pack_name in remote_index_packages:
                    # делаем сверку контрольных сумм пакетов
                    local_pack_hash = local_index_packs_cache[origin_pack_name]['phash']
                    remote_pack_hash = remote_index_packages[origin_pack_name]['phash']
                    if not local_pack_hash == remote_pack_hash:
                        status = State.UPD

                    # помечаем пакет на удаление, если алиасы отличаются - сменился на сервере !!!! - пересмотреть
                    local_pack_alias = local_index_packs_cache[origin_pack_name]['alias']
                    remote_pack_alias = remote_index_packages[origin_pack_name]['alias']
                    if not local_pack_alias == remote_pack_alias:
                        alias_pack_name = remote_pack_alias or origin_pack_name
                        status = State.UPD
                else:
                    # пакета нет в репозитории, но есть в локальном кэше
                    status = State.DEL

            pack_list[alias_pack_name] = PackData(
                origin=origin_pack_name,
                installed=False,
                checked=False,
                status=status,
            )

        if remote:  #
            # заполняем данными из индекса с сервера
            for origin_pack_name in remote_index_packages:
                if origin_pack_name not in local_index_packs_cache:
                    alias_pack_name = remote_index_packages[origin_pack_name].get('alias') or origin_pack_name
                    pack_list[alias_pack_name] = PackData(
                        origin=origin_pack_name,
                        installed=False,
                        checked=False,
                        status=State.NEW,
                    )

        # обновляем статус установки имеющихся пакетов
        for origin_pack_name in self._installed_packages():
            _, pack_data = pack_list.get_by_origin(origin_pack_name)
            if pack_data:
                setattr(pack_data, 'installed', True)
                setattr(pack_data, 'checked', True)
            else:
                pack_list[origin_pack_name] = PackData(
                    origin=origin_pack_name,
                    installed=True,
                    checked=True,
                    status=State.DEL,
                )

        return pack_list
    # +
    def get_task(self, pack_list) -> Iterator:
        """
        Формирование задачи для установки/обновления или удаления файлов пакета
        :param pack_alias: псевдоним пакета
        :param pack_origin: имя пакета
        :return: Iterator: namedtuple('Task', ('packetname action src dst hash'))
        """
        self.logger.info('Формирование списка файлов пакетов для обработки')
        self.logger.debug('get_task: подготовка словарей с данными о пакетах')
        r_packages = self.get_remote_index().get('packages', {})  # get remote packages map
        l_packages = self.get_local_index().get('packages', {})  # get local packages map

        for pack_alias, pack_data in pack_list:
            self.logger.info('\t`{}`'.format(pack_alias))
            local_list_map = l_packages.get(pack_data.origin, {}).get('files', {})
            remote_list_map = r_packages.get(pack_data.origin, {}).get('files', {})
            self.logger.debug('get_task: получены словари с данными файлов пакета')

            local_list = sorted(local_list_map.keys())  # sorted local package's files list
            remote_list = sorted(remote_list_map.keys())  # sorted remote packages's files list
            self.logger.debug('get_task: получены сортированные списки файлов пакета для обхода')

            l_index = r_index = 0  # counters for files lists
            l_max_index = len(local_list) - 1  # max index for list
            r_max_index = len(remote_list) - 1
            self.logger.debug('get_task: инициализация индексов списков')

            # обход по спискам файлов, сравнение имен и хэш=значений
            while True:
                if l_index > l_max_index and r_index > r_max_index:
                    self.logger.debug('get_task: прошли до конца обоих списков')
                    break

                if l_index > l_max_index:
                    self.logger.debug('get_task: прошли local список, но есть файл в remote - загружаем')
                    rfile = remote_list[r_index]
                    hash = remote_list_map[rfile]
                    task, task_id = self._build_task(pack_data.origin, rfile, State.NEW, hash)
                    yield task
                    self.logger.debug('get_task: сформирована задача на загрузку: <{}> {}'.format(task_id, task))
                    r_index += 1  # увеличиваем счетчик (индекс)
                    self.logger.debug('get_task: remote индекс: {}'.format(r_index))
                    continue

                # прошли remote список, оставшиеся в local - удаляем
                if r_index > r_max_index:
                    self.logger.debug('get_task: прошли remote список, оставшиеся в local - удаляем')
                    lfile = local_list[l_index]
                    task, task_id = self._build_task(pack_data.origin, lfile, State.DEL)
                    yield task
                    self.logger.debug('get_task: сформирована задача на удаление: <{}> {}'.format(task_id, task))
                    l_index += 1
                    self.logger.debug('get_task: local индекс: {}'.format(l_index))
                    continue

                # проход по спискам
                lfile = local_list[l_index]
                rfile = remote_list[r_index]
                hash = remote_list_map[rfile]
                if lfile == rfile:  # сравниваем имена файлов
                    # сравниваем хэши файлов
                    self.logger.debug('get_task: обработка файлов r`{}` - l`{}`'.format(rfile, lfile))
                    if pack_data.status == State.NEW:
                        self.logger.debug('get_task: установка пакета')
                        task, task_id = self._build_task(pack_data.origin, rfile, State.NEW, hash)
                        yield task
                        self.logger.debug('get_task: сформирована задача на загрузку: <{}> {}'.format(task_id, task))
                    elif not local_list_map[lfile] == remote_list_map[rfile]:  # загружаем при несоответствии хэшей
                        # self.logger.debug('get_task: хэши не равны')
                        task, task_id = self._build_task(pack_data.origin, rfile, State.UPD, hash)
                        yield task
                        self.logger.debug('get_task: сформирована задача на загрузку: <{}> {}'.format(task_id, task))
                    else:
                        self.logger.debug('get_task: нет изменений')
                    r_index += 1  # увеличиваем счетчик (индекс)
                    l_index += 1
                    self.logger.debug('get_task: local индекс: {} | remote индекс: {}'.format(l_index, r_index))

                elif rfile < lfile:  # есть в remote, нет в local - загружаем
                    self.logger.debug('есть в remote, нет в local - загружаем')
                    task, task_id = self._build_task(pack_data.origin, rfile, State.NEW, hash)
                    yield task
                    self.logger.debug('get_task: сформирована задача на загрузку: <{}> {}'.format(task_id, task))
                    r_index += 1
                    self.logger.debug('get_task: remote индекс: {}'.format(r_index))
                elif rfile > lfile:  # есть в local, нет в remote - удаляем
                    self.logger.debug('есть в local, нет в remote - удаляем')
                    task, task_id = self._build_task(pack_data.origin, lfile, State.DEL)
                    yield task
                    self.logger.debug('get_task: сформирована задача на удаление: <{}> {}'.format(task_id, task))
                    l_index += 1
                    self.logger.debug('get_task: local индекс: {}'.format(l_index))
                else:
                    raise IndexError('Что-то пошло не так с индексами, при проходе списков файлов на обработку')
    # +
    def _build_task(self, package, file, action, hash=None) -> (namedtuple, int):
        if action == State.DEL:
            src = os.path.join(self.eiispath, package, file)  # путь файла для удаления
            dst = None
        else:
            src = os.path.join(self._disp.repopath, package, file)  # путь файла-источника для получения
            dst = os.path.realpath(os.path.join(self._buffer, package, file))
            task = Task(package, action, src, dst, hash)
        return task, id(task)
    # +
    def handle_tasks(self, tasks):
        """Получить новые файлы из репозитория или удалить локально старые"""
        main_queue = Queue(maxsize=self.config.threads * self._task_queue_k)
        stopper = threading.Event()
        workers = []
        self.logger.debug('handle_tasks: подготовка `пчелок`')
        for i in range(self.config.threads):
            dispatcher = get_dispatcher(self.config.repopath,
                                        encode=self.config.encode,
                                        ftpencode=self.config.ftpencode,
                                        logger=self.logger,
                                        tempdir=self._tempdir)
            self.logger.debug('handle_tasks: диспетчер `{}` готов'.format(dispatcher))
            worker = Worker(main_queue, stopper, dispatcher, logger=self.logger)
            worker.setName('{}'.format(worker))
            worker.setDaemon(True)
            workers.append(worker)

        self.logger.debug('handle_tasks: стартуем `пчелок`')
        for worker in workers:  # стартуем пчелок
            worker.start()
            self.logger.debug('handle_tasks: worker {} запущен'.format(worker))

        self.logger.debug('handle_tasks: обработка очереди задач:')
        self.logger.info('Обработка файлов')
        for task in tasks:
            if stopper.is_set():  # worker дернул стоп-кран
                raise InterruptedError
            task_id = id(task)
            self.logger.debug('handle_tasks: получена задача <{}>'.format(task_id))
            main_queue.put(task)
            self.logger.debug('handle_tasks: задача <{}> помещена в очередь'.format(task_id))

        main_queue.join()  # ожидаем окончания обработки очереди
        self.logger.debug('handle_tasks: очередь обработана')

        stopper.set()
        self.logger.debug('handle_tasks: сигнал завершения `пчелкам`')
        # end up
    # +
    def flush_buffer(self, packs: Iterable):
        """
        Перемещение пакетов из буфера в папку установки
        :param packs: Список пакетов на обработку
        :return:
        """
        self.logger.info('Установка пакетов')
        for package in self.buffer_content():
            if package not in (data.origin for _, data in packs):  # возможно пакет остался с прошлой неудачной установки
                self.logger.warn('install_packets: {} есть в буфере, но нет в списке устанавливаемых пакетов - пропуск'.format(package))
                continue

            src = os.path.join(self._buffer, package)
            dst = os.path.join(self.eiispath, package)

            try:
                self._move_package(src, dst)
            except PermissionError:
                raise PacketInstallError('Недостаточно прав на установку пакета {} в {}'.format(package, self.eiispath))
            except Exception as err:
                raise PacketInstallError('Ошибка при установке пакета {}: {}'.format(package, err))
            else:
                self.logger.debug('install_packets: `{}` перемещен из буфера в {}'.format(package, dst))
        self._clean_buffer()

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

    def remove_shortcut(self, pack):  # TODO Диспетчером!
        title, _ = self._get_link_data(pack)
        link_path = os.path.join(self._desktop, title + '.lnk')
        try:
            os.unlink(link_path)
        except PermissionError:
            change_write_mod(link_path)
            os.unlink(link_path)
        except FileNotFoundError:
            pass

    def _clean(self):
        self._tempdir.cleanup()
    # +
    def _clean_buffer(self) -> bool:
        try:
            self._disp.rmdir(self._buffer)
        except Exception as err:
            self.logger.error('Ошибка учистки буфера')
            if self.debug:
                self.logger.exception(err)
            return False
        return True

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

    def _remove_dir(self, fpath):# TODO Диспетчером!
        """Удаление директории с файлами"""
        for top, _, files in os.walk(fpath, topdown=False):
            for file in files:
                fp = os.path.join(top, file)
                try:
                    self.logger.debug('[1] удаление {}'.format(fp))
                    os.unlink(fp)
                except PermissionError:
                    self.logger.debug('[2] удаление {}'.format(fp))
                    change_write_mod(fp)
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
                change_write_mod(top)
                self.logger.debug('[2] удаление {}'.format(top))
                os.rmdir(top)
            except FileNotFoundError:
                self.logger.debug('удаление {} - не найден'.format(top))
                pass

    def _copy_package(self, src, dst):  # TODO Диспетчером!
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
                        self.logger.debug('copy_package: Make dir error: {}'.format(err))
                        raise
                    self.logger.debug('создана папка {}'.format(dname))
                    self.logger.debug('[2] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except PermissionError:
                    try:
                        change_write_mod(d)
                    except Exception as err:
                        self.logger.debug('Chmod error: {}'.format(err))
                        raise
                    self.logger.debug('[3] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except Exception as err:
                    self.logger.debug('Copy pack Error: {}'.format(err))
                    raise

    def _move_package(self, src, dst):
        self.logger.debug('move_package: перенос пакета {} -> {}'.format(src, dst))
        self._copy_package(src, dst)  # TODO Диспетчером!
        self._remove_dir(src)  # TODO Диспетчером!

    def _get_temp_dir(self):
        tmpdir = getattr(self, '_tempdir', None)
        if tmpdir:
            self._tempdir.cleanup()
        return TemporaryDirectory(prefix='tmp_mngr_', dir=os.path.expandvars('%TEMP%'))

# +
class Worker(threading.Thread):
    max_repeat = 3
    def __init__(self, queue: Queue, stopper: threading.Event, dispatcher: BaseDispatcher,
                 logger=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.queue = queue
        self.dispatcher = dispatcher
        self.logger = logger or get_stdout_logger()
        self.stopper = stopper

    def __repr__(self):
        return 'WRK{}'.format(id(self))
    # +
    def run(self):
        try:
            while True:
                if self.stopper.is_set():
                    raise InterruptedError('Обнаружен стоп-флаг')

                if self.dispatcher.repo_is_busy():
                    raise StopIteration('Репозиторий заблокирован')

                try:
                    task = self.queue.get(timeout=2)
                except Empty:
                    sleep(.5)
                    continue

                # start real work
                task_id = id(task)
                self.logger.debug('worker {}: получена задача <{}>'.format(self, task_id))

                # удаление
                if task.action == State.DEL:
                    self.dispatcher.remove(task.src, onerror=True)  # todo перенести в диспетчер
                    self.queue.task_done()
                    continue

                # загрузка
                if os.path.exists(task.dst) and os.path.isfile(task.dst) and file_hash_calc(task.dst) == task.hash:
                    self.logger.debug('worker {}: <{}> обнаружен загруженный файл в буфере {}, пропуск'.format(
                        self, task_id, task.dst))
                    self.queue.task_done()
                    continue

                fault_count = 0
                while True:
                    self.dispatcher.get_file(task.src, task.dst)
                    self.logger.debug('worker {}: <{}> файл {} загружен в буфер'.format(self, task_id, task.dst))

                    hash_sum = file_hash_calc(task.dst)

                    if not hash_sum == task.hash:
                        fault_count += 1
                        self.logger.debug('worker {}: <{}> HASH MISMATCH {} != {} [{}]'.format(
                                self, task_id, hash_sum, task.hash, fault_count))
                        if fault_count >= self.max_repeat:
                            self.logger.debug('worker {}: <{}> исчерпан лимит загрузок файла'.format(self, task_id))
                            raise DownloadPacketError('Неверная контрольная сумма файла "{}" из пакета "{}"'.format(
                                os.path.basename(task.src), task.packetname))
                        else:
                            self.dispatcher.remove(task.dst, onerror=True)
                            self.logger.debug('worker {}: {} удален'.format(self, task.dst))
                            continue
                    break

                self.queue.task_done()
                self.logger.debug('worker {}: задача <{}> выполнена'.format(self, task_id))

        except InterruptedError as err: # stopper is set
            self.logger.debug('worker {}: {}'.format(self, err))
        except StopIteration as err: # repo is blocked
            self.logger.debug('worker {}: {}'.format(self, err))
            self.logger.error(err)
            self.stopper.set()
        except DownloadPacketError as err:
            if self.logger.level == logging.DEBUG:
                self.logger.exception(err)
            self.logger.error('Расхождение контрольных сумм файла с данными индекса в репозитории.'
                              'Требуется индексация.')
            self.stopper.set()
            self.queue.task_done()
        except Exception as err:
            self.logger.debug('worker {}: {}'.format(self, err))
            if self.logger.level == logging.DEBUG:
                self.logger.exception(err)
            self.stopper.set()
            self.queue.task_done()

        finally:
            self.logger.debug('worker {}: работу завершил'.format(self))
            self.dispatcher.close()

    # def remove_file(self, fpath):
    #     try:
    #         os.unlink(fpath)
    #     except FileNotFoundError:
    #         pass
    #     except (PermissionError) as err:
    #         self.logger.debug('ошибка при удалении файла: {}: {}'.format(fpath, err))
    #         change_write_mod(fpath)
    #         try:
    #             os.unlink(fpath)
    #         except Exception:
    #             self.logger.debug('ошибка {}: файл {} не удален'.format(err, fpath))
