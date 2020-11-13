# -*- coding: utf-8 -*-
from __future__ import print_function

import logging
import os
import threading
import weakref
from collections import OrderedDict, namedtuple
from collections.abc import Iterable, Iterator
from datetime import datetime
from queue import Empty, Queue
from tempfile import TemporaryDirectory

import pythoncom
import winshell

from eiisclient import (DEFAULT_ENCODING, DEFAULT_FTP_ENCODING, WORK_DIR, PROFILE_INSTALL_PATH, DEFAULT_INSTALL_PATH,
                        CONFIGFILE)
from eiisclient.dispatch import BaseDispatcher, get_dispatcher
from eiisclient.exceptions import (LinkUpdateError, NoUpdates, RepoIsBusy, PacketInstallError, LinkDisabled, LinkNoData,
                                   IndexFixError, NoIndexFileOnServerError, HashMismatchError, DispatcherNotActivated)
from eiisclient.functions import (file_hash_calc, unjsonify, jsonify, read_file, gzread, write_data, remove, rmtree,
                                  copytree)
from eiisclient.structures import (PackList, ConfigDict, State, PackData, Task)

THREADS = 3
QUEUEMAXSIZE = 50
LOCAL_INDEX_FILE = os.path.normpath(os.path.join(WORK_DIR, 'index.json'))
LOCAL_INDEX_FILE_HASH = '{}.sha1'.format(LOCAL_INDEX_FILE)
INDEX_FILE_NAME = 'Index.gz'
INDEX_HASH_FILE_NAME = 'Index.gz.sha1'
LINKSDIRNAME = 'ЕИИС Соцстрах'


def get_stdout_logger() -> logging.Logger:
    return logging.Logger(__name__)


def get_config() -> ConfigDict:
    return ConfigDict(
        repopath='',
        repopathlist=[],
        threads=THREADS,
        encode=DEFAULT_ENCODING,
        ftpencode=DEFAULT_FTP_ENCODING,
        install_to_profile=False,
        links_in_dir=False,
    )


def read_config() -> dict:
    """
    Возвращает данные конфигурационного файла или пустой словарь

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
        self.checked = False
        self.logger = logger or get_stdout_logger()
        self.disp = None  # type: BaseDispatcher
        self.config = get_config()
        if not os.path.exists(WORK_DIR):
            os.makedirs(WORK_DIR, exist_ok=True)
        # обновление параметров из файла настроек
        self.config.update(read_config())
        #
        self._local_index = None  # type: dict
        self._remote_index = None  # type: dict
        self._tempdir = self._get_temp_dir()
        self._buffer = os.path.join(WORK_DIR, 'buffer')
        self._task_queue_k = kwargs.get('kqueue', 2)  # коэффициент размера основной очереди загрузки
        self._desktop = winshell.desktop()
        self._finalize = weakref.finalize(self, self._clean)
        self._full = False
        self.init_dispatcher()

        if self.logger.level == logging.DEBUG:
            self.debug = True
            self.logger.debug('{}: repo: {}'.format(self, self.config.repopath))
            self.logger.debug('{}: eiis: {}'.format(self, self.eiispath))
            self.logger.debug('{}: buffer: {}'.format(self, self._buffer))
            self.logger.debug('{}: encode: {}'.format(self, self.config.encode))
            self.logger.debug('{}: tempdir: {}'.format(self, self._tempdir.name))
            self.logger.debug('{}: task_k: {}'.format(self, self._task_queue_k))

        self._pack_list = self._get_pack_list(remote=False)  # type: PackList # - перечень пакетов со статусами
        self._info_list = self._get_info_list(remote=False)  # type: dict # - информация о репозитории, пакетах,..

        self._progressBarStep = 10

    def __repr__(self):
        return '<Manager: {}>'.format(id(self))

    @property
    def eiispath(self) -> str:
        return PROFILE_INSTALL_PATH if self.config.install_to_profile else DEFAULT_INSTALL_PATH

    @property
    def pack_list(self):
        return self._pack_list

    @property
    def info_list(self):
        return self._info_list

    def check_updates(self, processBar):
        processBar.SetRange(100)
        processBar.SetValue(0)

        self._local_index = None
        self._pack_list = self._get_pack_list(remote=False)

        self._check_disp()

        with self.disp:
            self.disp.up()
            if self.disp.repo_is_busy():
                processBar.SetValue(100)
                raise RepoIsBusy

            remove(os.path.join(self._tempdir.name, INDEX_HASH_FILE_NAME))  # чистим хэш
            if not self.repo_updated:
                self._info_list = self._get_info_list(remote=True)
                processBar.SetValue(100)
                self.checked = True
                raise NoUpdates

            self._remote_index = None
            remove(os.path.join(self._tempdir.name, INDEX_FILE_NAME))
            self.logger.info('Чтение данных репозитория')
            try:
                self.logger.debug('check_updates: активация диспетчера')
                self._remote_index = None
                self._local_index = None
                self._pack_list = self._get_pack_list(remote=True)
                processBar.SetValue(30)
                self._info_list = self._get_info_list(remote=True)
                processBar.SetValue(70)
            finally:
                self.logger.debug('check_updates: деактивация диспетчера')
                if not processBar.GetValue() == processBar.GetRange():
                    processBar.SetValue(processBar.GetRange())
            self.checked = True

    def start_update(self, processBar):
        """
        Процедура обновления пакетов

        :return:
        """
        self._check_disp()

        processBar.SetValue(0)
        with self.disp:
            self.disp.up()
            self.logger.info('Формирование списка пакетов')
            action_list = {}
            for pack, data in self._pack_list.items():
                action = self._pack_list.get_action(pack)
                if (self._full and data.checked) or action == State.UPD or action == State.NEW:
                    action_list.setdefault('update', []).append((pack, data))
                elif action == State.DEL:
                    action_list.setdefault('delete', []).append((pack, data))
            if self.debug:
                self.logger.debug(action_list)

            packs_handle = action_list.get('update', [])
            packs_delete = action_list.get('delete', [])

            packets_size = self._calc_packets_size(packs_handle)
            packs_handle_count = len(packs_handle) or 1
            packs_handle_delete = len(packs_delete)
            self._progressBarStep = (packets_size / packs_handle_count) / 10 if packets_size else 10
            progress_bar_range = self._progressBarStep + \
                                 packets_size + \
                                 packs_handle_count * self._progressBarStep + \
                                 packs_handle_delete * self._progressBarStep
            processBar.SetRange(int(progress_bar_range))

            # 2 удаление пакетов
            if packs_delete:
                self.delete_packages(packs_delete, processBar)

            if self.disp.repo_is_busy():
                raise RepoIsBusy

            if not self.checked:
                self._pack_list = self._get_pack_list(remote=True)
                self._info_list = self._get_info_list(remote=True)
                self.logger.error('Требуется проверка наличия обновлений')
                self.logger.info('--\n')
                return

            # 1 обновление/удаление пакетов
            if packs_handle:
                self.logger.debug('start_update: активация диспетчера')
                # Step 1: формирование задач для обработки файлов пакетов из репозитория
                tasks = self.get_task(packs_handle)
                # Step 2: обработка файлов пакета (загрузка или удаление)
                self.handle_tasks(tasks, processBar)

                # Step 3: перемещение скачанных пакетов из буфера в папку установки
                if not self.buffer_is_empty():
                    # перенос файлов пакетов из буфера в папку назначения
                    self.flush_buffer(packs_handle, processBar)
            else:
                self.logger.info('Нет пакетов для установки или обновления')

            # 3 фиксация данных индекса репозитория
            try:
                write_data(LOCAL_INDEX_FILE, jsonify(self.remote_index))
                write_data(LOCAL_INDEX_FILE_HASH, self.remote_index_hash)
                self.logger.debug('start_update: индекс зафиксирован локально')
            except Exception as err:
                raise IndexFixError('Ошибка фиксации данных индекса репозитория') from err
            else:
                processBar.SetValue(processBar.GetValue() + self._progressBarStep)
                if not processBar.GetValue() == processBar.GetRange():
                    processBar.SetValue(processBar.GetRange())

                self._pack_list = self._get_pack_list(remote=True)
                self._info_list = self._get_info_list(remote=True)

    def reset(self, remote=False):
        self.checked = False
        self._tempdir = self._get_temp_dir()
        self._local_index = None
        self._pack_list = self._get_pack_list(remote)
        self._info_list = self._get_info_list(remote)

    @property
    def repo_updated(self) -> bool:
        """Проверка на наличие обновлений"""
        remote_index_hash = self.remote_index_hash
        local_index_hash = self.local_index_hash
        return not local_index_hash == remote_index_hash

    def buffer_content(self) -> list:
        if os.path.exists(self._buffer):
            return [pack for pack in os.listdir(self._buffer) if os.path.isdir(os.path.join(self._buffer, pack))]
        return []

    def buffer_count(self) -> int:
        return len(self.buffer_content())

    def buffer_is_empty(self) -> bool:
        return self.buffer_count() == 0

    def init_dispatcher(self):
        self.disp = get_dispatcher(self.config.repopath, logger=self.logger, encode=self.config.encode,
                                   ftpencode=self.config.ftpencode, tempdir=self._tempdir)

    def _check_disp(self):
        if self.disp is None:
            if not self.config.repopath:
                raise DispatcherNotActivated('Не указан путь к репозиторию')
            self.init_dispatcher()

    def _get_info_list(self, remote: bool) -> dict:
        repo_updated = None
        local_index_last_change = None
        packets_in_repo = len(self.local_index_packages)
        if os.path.exists(LOCAL_INDEX_FILE):
            local_index_last_change = os.path.getmtime(LOCAL_INDEX_FILE)
            local_index_last_change = datetime.fromtimestamp(local_index_last_change).strftime(
                '%d-%m-%Y %H:%M:%S')
        index_last_change = None

        if remote:
            repo_updated = self.repo_updated
            index_last_change = self.remote_index_create_date if repo_updated else local_index_last_change
            if index_last_change:
                packets_in_repo = len(self.remote_index_packages) if repo_updated else packets_in_repo

        info = OrderedDict()
        info.setdefault('Дата последнего обновления', local_index_last_change)
        info.setdefault('Дата обновления на сервере', index_last_change)
        info.setdefault('Наличие обновлений',
                        {True: 'имеются обновления', False: 'нет обновлений', None: '-'}[repo_updated])
        info.setdefault('Пакетов в репозитории', packets_in_repo)
        info.setdefault('Установлено подсистем', len(list(self.installed_packages())))

        buf_content = self.buffer_content()
        buf_count = len(buf_content)
        if buf_count:
            text = ('Пакеты в буфере', '{} (`{}`)'.format(buf_count, '`, `'.join(p for p in buf_content)))
        else:
            text = ('Пакеты в буфере', '{}'.format(buf_count))
        info.setdefault(*text)
        info.setdefault('Путь - подсистемы', self.eiispath)
        info.setdefault('Путь - репозиторий', self.config.repopath)
        if self.debug:
            info.setdefault('Temporary dir', self._tempdir.name)

        return info

    def installed_packages(self) -> Iterator:
        """
        Список установленных пакетов

        Возвращает кортеж с подсистемами, найденными в папке установки на локальной машине.
        Пакеты с подсистемами, названия которых заканчиваются на .removed - считаются удаленными и не
        попадают в список.
        """
        if os.path.exists(self.eiispath):
            return (d for d in os.listdir(self.eiispath) if os.path.isdir(os.path.join(self.eiispath, d)))
        else:
            return iter([])

    def delete_packages(self, packages: list, processBar):
        self.logger.info('Удаление пакетов:')
        for pack, pack_data in packages:
            fp = os.path.join(self.eiispath, pack_data.origin)
            try:
                rmtree(fp)
            except Exception as err:
                self.logger.error('Ошибка удаления пакета {}: {}'.format(pack, err))
            else:
                self.logger.info('\t`{}`'.format(pack))

            # удаление ярлыка подсистемы
            try:
                self._remove_shortcut(pack, in_dir=self.config.links_in_dir)
                self.logger.debug('delete_packages: удален ярлык для {}'.format(pack))
            except LinkUpdateError:
                self.logger.error('ошибка удаления ярлыка для {}'.format(pack))

            processBar.SetValue(processBar.GetValue() + self._progressBarStep)

    def set_full(self, value=False):
        self._full = value

    @property
    def remote_index(self):
        if not self._remote_index:
            fp = os.path.join(self._tempdir.name, INDEX_FILE_NAME)
            if not os.path.exists(fp):
                try:
                    self.disp.get_file(INDEX_FILE_NAME, fp)
                except FileNotFoundError:
                    raise NoIndexFileOnServerError
                except (RepoIsBusy, AttributeError):
                    self._remote_index = {}
                else:
                    self._remote_index = unjsonify(gzread(fp, encode=DEFAULT_ENCODING))
        return self._remote_index

    @property
    def remote_index_packages(self) -> dict:
        return self.remote_index.get('packages', {})

    @property
    def remote_index_meta(self) -> dict:
        return self.remote_index.get('meta', {})

    @property
    def remote_index_hash(self):
        fp = os.path.join(self._tempdir.name, INDEX_HASH_FILE_NAME)
        if not os.path.exists(fp):
            try:
                self.disp.get_file(INDEX_HASH_FILE_NAME, fp)
            except AttributeError:  # диспетчер не активирован
                raise DispatcherNotActivated('диспетчер не активирован')
            except FileNotFoundError:
                raise NoIndexFileOnServerError('Не найден файл хэш-суммы индекса')
        return read_file(fp)

    @property
    def remote_index_create_date(self):
        stamp = self.remote_index_meta.get('stamp')
        return datetime.fromtimestamp(float(stamp)).strftime('%d-%m-%Y %H:%M:%S') if stamp else None

    @property
    def local_index(self) -> dict:
        if not self._local_index:
            data = read_file(LOCAL_INDEX_FILE)
            self._local_index = unjsonify(data) if data else {}
        return self._local_index

    @property
    def local_index_packages(self) -> dict:
        return self.local_index.get('packages', {})

    @property
    def local_index_meta(self) -> dict:
        return self.local_index.get('meta', {})

    @property
    def local_index_hash(self) -> str:
        return read_file(LOCAL_INDEX_FILE_HASH)

    def _get_pack_list(self, remote) -> PackList:
        pack_list = PackList()
        remote_index_packages = None
        local_index_packages = self.local_index_packages
        if remote:
            remote_index_packages = self.remote_index_packages

        # заполняем данными из локального индекс-кэша
        for origin_pack_name in local_index_packages:
            alias_pack_name = local_index_packages[origin_pack_name].get('alias') or origin_pack_name
            status = State.NON

            if remote:
                if origin_pack_name in remote_index_packages:
                    # делаем сверку контрольных сумм пакетов
                    local_pack_hash = local_index_packages[origin_pack_name]['phash']
                    remote_pack_hash = remote_index_packages[origin_pack_name]['phash']
                    if not local_pack_hash == remote_pack_hash:
                        status = State.UPD

                    local_pack_alias = local_index_packages[origin_pack_name]['alias']
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
                if origin_pack_name not in local_index_packages:
                    alias_pack_name = remote_index_packages[origin_pack_name].get('alias') or origin_pack_name
                    pack_list[alias_pack_name] = PackData(
                        origin=origin_pack_name,
                        installed=False,
                        checked=False,
                        status=State.NEW,
                    )

        # обновляем статус установки имеющихся пакетов
        for origin_pack_name in self.installed_packages():
            _, pack_data = pack_list.get_by_origin(origin_pack_name)
            if pack_data:
                setattr(pack_data, 'installed', True)
                setattr(pack_data, 'checked', True)
                if pack_data.origin not in local_index_packages and pack_data.checked:
                    setattr(pack_data, 'status', State.UPD)  # установлен - обновляем
            else:
                pack_list[origin_pack_name] = PackData(
                    origin=origin_pack_name,
                    installed=True,
                    checked=True,
                    status=State.DEL,
                )

        return pack_list

    def get_task(self, pack_list) -> Iterator:
        """
        Формирование задачи для установки/обновления или удаления файлов пакета
        :param pack_list: список пакетов
        :return: Iterator: namedtuple('Task', ('packetname action src dst hash'))
        """
        self.logger.info('Формирование списка файлов пакетов для обработки')
        self.logger.debug('get_task: подготовка словарей с данными о пакетах')
        r_packages = self.remote_index_packages  # get remote packages map
        l_packages = self.local_index_packages  # get local packages map
        self.logger.info('Загрузка файлов:')

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
                        task, task_id = self._build_task(pack_data.origin, rfile, State.NEW, hash)
                        yield task
                        self.logger.debug('get_task: сформирована задача на загрузку: <{}> {}'.format(task_id, task))
                    elif self._full or not local_list_map[lfile] == remote_list_map[
                        rfile]:  # загружаем при несоответствии хэшей
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

    def _build_task(self, package, file, action, hash=None) -> (namedtuple, int):
        if action == State.DEL:
            src = os.path.join(self.eiispath, package, file)  # путь файла для удаления
            dst = None
        else:
            src = os.path.join(self.disp.repopath, package, file)  # путь файла-источника для получения
            dst = os.path.realpath(os.path.join(self._buffer, package, file))
        task = Task(package, action, src, dst, hash)
        return task, id(task)

    def handle_tasks(self, tasks, processBar):
        """Получить новые файлы из репозитория или удалить локально старые"""
        main_queue = Queue(maxsize=QUEUEMAXSIZE)
        exc_queue = Queue()
        size_queue = Queue()
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
            worker = Worker(main_queue, stopper, dispatcher, logger=self.logger, exc_queue=exc_queue,
                            size_queue=size_queue)
            worker.setName('{}'.format(worker))
            worker.setDaemon(True)
            workers.append(worker)

        self.logger.debug('handle_tasks: стартуем `пчелок`')
        for worker in workers:  # стартуем пчелок
            worker.start()
            self.logger.debug('handle_tasks: worker {} запущен'.format(worker))

        self.logger.debug('handle_tasks: обработка очереди задач:')

        try:
            while True:
                if stopper.is_set():  # worker дернул стоп-кран
                    raise InterruptedError

                if size_queue.qsize() > 0:
                    size = size_queue.get_nowait()
                    processBar.SetValue(processBar.GetValue() + size)

                if not main_queue.full():
                    task = next(tasks)
                    task_id = id(task)
                    self.logger.debug('handle_tasks: получена задача <{}>'.format(task_id))
                    main_queue.put(task)
                    self.logger.debug('handle_tasks: задача <{}> помещена в очередь'.format(task_id))

        except StopIteration:
            self.logger.debug('все задачи помещены в очередь, ожидание окончания очереди')
            main_queue.join()  # ожидаем окончания обработки очереди
            self.logger.debug('проверка активности пчелок и ожидание завершения работы')
            for worker in workers:
                if worker.isAlive():
                    worker.join()
            try:
                for i in range(size_queue.qsize()):
                    size = size_queue.get_nowait()
                    processBar.SetValue(processBar.GetValue() + size)
            except Empty:
                pass

        finally:
            if exc_queue.qsize():
                self.logger.debug('выгрузка исключений из очереди')
                exc = None
                for _ in range(exc_queue.qsize()):
                    exc = exc_queue.get()  # type: Exception
                    self.logger.error(exc)
                if exc:
                    raise exc

        self.logger.debug('handle_tasks: очередь обработана')
        # end up

    def flush_buffer(self, packs: Iterable, processBar):
        """
        Перемещение пакетов из буфера в папку установки
        :param packs: Список пакетов на обработку
        :return:
        """
        self.logger.info('Установка пакетов')
        remote_packages = self.remote_index_packages
        for package in self.buffer_content():
            if package not in (data.origin for _, data in packs):  # пакет остался с прошлой неудачной установки
                self.logger.warning('- `{}` есть в буфере, но нет в списке '
                                    'устанавливаемых пакетов - пропуск'.format(package))
                continue

            src = os.path.join(self._buffer, package)
            dst = os.path.join(self.eiispath, package)

            title = remote_packages[package]['alias'] or package
            try:
                self.move_package(src, dst)
                execf = os.path.join(self.eiispath, package, remote_packages[package]['execf'])
                self._create_shortcut(title, execf, in_dir=self.config.links_in_dir)
            except PermissionError as err:
                raise PacketInstallError('Недостаточно прав на установку пакета '
                                         '{} в {}'.format(package, self.eiispath)) from err
            except LinkUpdateError as err:
                self.logger.error('Не удалось создать ярлык для `{}`'.format(title))
                if self.debug:
                    self.logger.exception(err)
            except Exception as err:
                raise PacketInstallError('Ошибка при установке пакета `{}`'.format(package)) from err
            else:
                self.logger.debug('install_packets: `{}` перемещен из буфера в {}'.format(package, dst))

            processBar.SetValue(processBar.GetValue() + self._progressBarStep)

    def update_links(self):
        self.logger.info('Обновление ярлыков на рабочем столе')
        in_dir =  self.config.links_in_dir

        if in_dir:
            os.makedirs(os.path.join(self._desktop, LINKSDIRNAME), exist_ok=True)

        for packet in self.installed_packages():
            if in_dir:
                self._remove_shortcut(packet)  # remove from desktop

            try:
                title, exe_file_path = self._get_link_data(packet)
                self._create_shortcut(title, exe_file_path, in_dir=in_dir)
            except (LinkDisabled, LinkNoData) as err:
                self.logger.error('Ярлык не создан {}'.format(err))
            except LinkUpdateError as err:
                self.logger.error('Ошибка создания ярлыка: {}'.format(err))

        if not in_dir:
            rmtree(os.path.join(self._desktop, LINKSDIRNAME))

    def _create_shortcut(self, title, exe_file_path, in_dir=False):
        """
        Создание ярлыка запуска подсистемы

        :param
        """
        if not exe_file_path:
            raise LinkNoData(
                '- недостаточно данных для создания ярлыка для {}. Проверьте реестр подсистем'.format(title))

        workdir = os.path.dirname(exe_file_path)
        path = os.path.join(self._desktop, LINKSDIRNAME) if in_dir else self._desktop
        lnpath = os.path.join(path, '{}.lnk'.format(title))

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

    def _remove_shortcut(self, pack, in_dir=False):
        title, _ = self._get_link_data(pack)
        path = os.path.join(self._desktop, LINKSDIRNAME) if in_dir else self._desktop
        link_path = os.path.join(path, title + '.lnk')
        try:
            remove(link_path)
            self.logger.debug('удален ярлык: {}'.format(link_path))
        except FileNotFoundError:
            pass

    def _clean(self):
        self._tempdir.cleanup()

    def clean_buffer(self) -> bool:
        try:
            rmtree(self._buffer)
        except FileNotFoundError:
            return True
        except Exception as err:
            self.logger.error('Ошибка учистки буфера')
            if self.debug:
                self.logger.exception(err)
            return False
        self._info_list = self._get_info_list(remote=False)
        return True

    def _get_link_data(self, packet) -> tuple:
        try:
            alias = self.remote_index_packages[packet].get('alias') or packet
            alias = alias.lstrip('"').rstrip('"')
        except:
            alias = packet
        try:
            execf = self.remote_index_packages[packet].get('execf')
            execf_path = os.path.join(self.eiispath, packet, execf) if execf else None
        except:
            execf_path = None

        return alias, execf_path

    def move_package(self, src, dst):
        self.logger.debug('move_package: перенос пакета {} -> {}'.format(src, dst))
        copytree(src, dst)
        rmtree(src)

    def _get_temp_dir(self):
        tmpdir = getattr(self, '_tempdir', None)
        if tmpdir:
            self._tempdir.cleanup()
        return TemporaryDirectory(prefix='tmp_mngr_', dir=os.path.expandvars('%TEMP%'))

    def _calc_packets_size(self, packs_handle: list) -> int:
        r_packs = self.remote_index_packages
        size = 0
        for _, data in packs_handle:
            size += r_packs[data.origin]['size']
        return size


class Worker(threading.Thread):
    max_repeat = 3

    def __init__(self, queue: Queue, stopper: threading.Event, dispatcher: BaseDispatcher,
                 logger=None, *args, **kwargs):
        self.queue = queue
        self.exc_queue = kwargs.pop('exc_queue')  # type: Queue
        self.size_queue = kwargs.pop('size_queue')  # type: Queue
        self.dispatcher = dispatcher
        self.logger = logger or get_stdout_logger()
        self.stopper = stopper
        super(Worker, self).__init__(*args, **kwargs)
        self.dispatcher.up()

    def __repr__(self):
        return 'WRK{}'.format(id(self))

    def run(self):
        try:
            while True:
                if self.stopper.is_set():
                    self.logger.debug('worker {}: {}'.format(self, 'Обнаружен стоп-флаг'))
                    return

                if self.dispatcher.repo_is_busy():
                    self.stopper.set()
                    self.exc_queue.put(RepoIsBusy)
                    return

                task = self.queue.get(timeout=1)

                # start real work
                task_id = id(task)
                self.logger.debug('worker {}: получена задача <{}>'.format(self, task_id))

                # удаление
                if task.action == State.DEL:
                    remove(task.src, raise_=True)
                    self.queue.task_done()
                    continue

                # загрузка
                if os.path.exists(task.dst) and os.path.isfile(task.dst) and file_hash_calc(task.dst) == task.hash:
                    self.logger.debug('worker {}: <{}> обнаружен загруженный файл в буфере {}, пропуск'.format(
                        self, task_id, task.dst))
                    self.size_queue.put(os.path.getsize(task.dst))
                    self.queue.task_done()
                    continue

                fault_count = 0
                while True:
                    self.dispatcher.get_file(task.src, task.dst)
                    self.logger.debug('worker {}: <{}> файл {} загружен в буфер'.format(self, task_id, task.dst))

                    hash_sum = file_hash_calc(task.dst)
                    if fault_count == 0:
                        self.size_queue.put(os.path.getsize(task.dst))

                    if not hash_sum == task.hash:
                        fault_count += 1
                        self.logger.debug('worker {}: <{}> HASH MISMATCH {} != {} [{}]'.format(
                            self, task_id, hash_sum, task.hash, fault_count))
                        if fault_count >= self.max_repeat:
                            self.logger.debug('worker {}: <{}> исчерпан лимит загрузок файла'.format(self, task_id))
                            raise HashMismatchError('Неверная контрольная сумма файла `{}` из пакета `{}`'.format(
                                os.path.basename(task.src), task.packetname))
                        else:
                            remove(task.dst, raise_=True)
                            self.logger.debug('worker {}: {} удален'.format(self, task.dst))
                            continue
                    break

                self.queue.task_done()
                self.logger.debug('worker {}: задача <{}> выполнена'.format(self, task_id))

        except Empty:
            self.logger.debug('worker {}: очередь пустая, выхожу'.format(self))
            return
        except HashMismatchError as err:
            self.logger.error('Расхождение контрольных сумм файла данных индекса.'
                              'Требуется индексация репозитория.')
            if self.logger.level == logging.DEBUG:
                self.logger.exception(err)
            self.stopper.set()
            self.exc_queue.put(err)
            self.queue.task_done()
        except Exception as err:
            self.logger.debug('worker {}: {}'.format(self, err))
            if self.logger.level == logging.DEBUG:
                self.logger.exception(err)
            self.stopper.set()
            self.exc_queue.put(err)
            self.queue.task_done()

        finally:
            self.logger.debug('worker {}: работу завершил'.format(self))
            self.dispatcher.down()
