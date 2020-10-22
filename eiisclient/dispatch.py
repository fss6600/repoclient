# -*- coding: utf-8 -*-
#
import gzip
import logging
import os
import re
import shutil
import stat
import time
import weakref
from datetime import datetime
import locale
from collections import Iterator

from eiisclient import DEFAULT_ENCODING
from eiisclient.exceptions import DispatcherActivationError, NoIndexFileOnServerError, CopyPackageError
from eiisclient.utils import change_write_mod, unjsonify, read_file

BUSYMESSAGE = '__REGLAMENT__'


class BaseDispatcher(object):
    """"""
    index_file_name = 'Index.gz'
    index_hash_file_name = 'Index.gz.sha1'

    def __init__(self, *args, **kwargs):
        self._repo = None
        self._tempdir = kwargs.get('tempdir')
        self.logger = kwargs.get('logger')
        self.encode = kwargs.get('encode', DEFAULT_ENCODING)
        # ликвидация ошибки locale error ru-RU при формировании даты индекс-файла на ftp-сервере
        locale.setlocale(locale.LC_ALL, '')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def repopath(self):
        return self._repo

    @staticmethod
    def read(file_path: str):
        return read_file(file_path)

    def get_file(self, src: str, dst: str) -> str:
        """
        Загрузка файла из репозитория
        :param src: полный путь к файлу-источнику
        :param dst: полный путь к файлу-назначению
        :return: полный путь назначения
        """
        raise NotImplementedError

    def repo_is_busy(self):
        raise NotImplementedError

    def copytree(self, src: str, dst: str):
        """
        Копирование директории
        :param src: полный путь директории-исходника
        :param dst: полный путь директории-назначения
        :return:
        """
        for top, _, files in os.walk(src, topdown=False):
            for file in files:
                s = os.path.join(top, file)
                d = os.path.join(os.path.dirname(dst), os.path.relpath(s, os.path.dirname(src)))
                try:
                    self.logger.debug('[1] copy: {}  ->  {}'.format(s, d))
                    dname = os.path.dirname(d)
                    if not os.path.exists(dname):
                        os.makedirs(dname, exist_ok=True)
                    shutil.copyfile(s, d)
                except PermissionError:
                    try:
                        self._onerror(os.remove, dst, None)
                        shutil.copyfile(src, dst)
                    except Exception as err:
                        self.logger.debug('Chmod error: {}'.format(err))
                        raise
                    self.logger.debug('[2] copy: {}  ->  {}'.format(s, d))
                    shutil.copyfile(s, d)
                except Exception as err:
                    raise

    # def copy_file(self, src: str, dst: str, move=False):
    #     """
    #     Копирование/Перемещение файла
    #
    #     :param src: полный путь к файлу источника
    #     :param dst: полный путь к файлу назначения
    #     :param move: удалить файл после копирования
    #     :return:
    #     """
    #     dirname = os.path.dirname(dst)
    #     if not os.path.exists(dirname):
    #         os.makedirs(dirname, exist_ok=True)
    #
    #     try:
    #         shutil.copyfile(src, dst)
    #     except PermissionError:
    #         try:
    #             self._onerror(os.remove, dst, None)
    #             shutil.copyfile(src, dst)
    #         except Exception as err:
    #             raise IOError(err)
    #     if move:
    #         self.remove(src)

    def remove(self, path: str, onerror=False):
        """
        Удаление локального файла

        :param path: полный путь к файлу
        :param onerror: True выбрасывает исключение, False замалчивает исключение
        :return:
        """
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except PermissionError:
            try:
                self._onerror(os.remove, path, None)
            except Exception as err:
                self.logger.error('Ошибка удаления файла `{}`'.format(path))
                if self.logger.level == logging.DEBUG:
                    self.logger.exception(err)
                if onerror:
                    raise

    def rmtree(self, path, ignore_errors=False):
        shutil.rmtree(path, ignore_errors=ignore_errors, onerror=self._onerror)

    # def packet_files(self, path: str) -> Iterator:
    #     """
    #     Генератор списка файлов в указанной папке
    #
    #     :path: полный путь к директории
    #     :return: tuple(fpath, rpath)
    #         fpath: полный путь к файлу
    #         rpath: относительный путь файлу
    #     """
    #     for (root, _, filenames) in os.walk(path):
    #         for fname in filenames:
    #             fpath = os.path.join(root, fname)
    #             rpath = os.path.relpath(fpath, path)
    #             yield fpath, rpath

    def rmdir(self, path: str):
        """
        Рекурсивное удаление директории

        :param path: полный путь к директории
        :return:
        """
        shutil.rmtree(path, onerror=self._onerror)

    def write(self, path: str, data: str):
        """
        Запись данных в файл

        :param path: полный путь к файлу
        :param data: данные в текстовом виде
        :return:
        """
        with open(path, 'w', encoding=self.encode) as fp:
            fp.write(data)

    # def remote_index_hash(self) -> str:
    #     """
    #     :return: Хэш-сумма индекса репозитория
    #     """
    #     pass
    #
    # def remote_index(self) -> dict:
    #     """
    #     :return: Данные индекса репозитория
    #     """
    #     pass

    # def index_create_date(self) -> datetime:  # todo считывать из индекса::meta datastamp
    #     pass

    def _init_log(self):
        self.logger.debug('{}: encode: {}'.format(self, self.encode))
        self.logger.debug('{}: tmpdir: {}'.format(self, self._tempdir.name))
        self.logger.debug('{}: repo: {}'.format(self, self.repopath))

    def close(self):
        pass

    @staticmethod
    def _onerror(func, path, _):
        """
        Вспомогательная функция для смены прав доступа к файлу при удалении, изменении

        :param func: объект функции для выполнения после смены прав
        :param path: полный путь к файлу
        :return:
        """
        os.chmod(path, stat.S_IWUSR)
        os.chmod(path, stat.S_IWRITE)
        time.sleep(0.3)
        func(path)


class FileDispatcher(BaseDispatcher):
    """"""

    def __init__(self, repo, *args, **kwargs):
        """"""
        super(FileDispatcher, self).__init__(*args, **kwargs)
        self._repo = repo
        if self.logger.level == logging.DEBUG:
            self._init_log()

    def __repr__(self):
        return '<File Dispatcher-{}>'.format(id(self))

    def get_file(self, src: str, dst: str) -> str:
        src = os.path.normpath(os.path.join(self._repo, src))
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        shutil.copyfile(src, dst)
        return dst

    def repo_is_busy(self):
        return BUSYMESSAGE in os.listdir(self.repopath)

    # @property
    # def index_create_date(self) -> datetime:  # todo убрать - использовать метод Manager'a
    #     timestamp = os.path.getmtime(os.path.join(self.repopath, self.index_file_name))
    #     return datetime.fromtimestamp(timestamp)


class SMBDispatcher(FileDispatcher):
    def __repr__(self):
        return '<SMB Dispatcher-{}>'.format(id(self))


class FTPDispatcher(BaseDispatcher):
    """FTP диспетчер"""

    def __init__(self, repo, *args, **kwargs):
        super(FTPDispatcher, self).__init__(*args, **kwargs)

        self.ftpencode = kwargs.get('ftpencode', self.encode)
        self.hostname = None
        self.username = None
        self.password = None
        self._repo = None

        self._parse_url_data(repo)
        self.ftp = self._get_connection()
        self._finalizer = weakref.finalize(self, self.close)
        self.index_file_path = os.path.join(self.repopath, self.index_file_name)

    def __repr__(self):
        return 'FTP Dispatcher  <{}> on <{}{}>'.format(id(self), self.hostname, self.repopath)

    def _parse_url_data(self, repo_string):
        """"""
        from urllib.parse import urlparse
        data = urlparse(repo_string)
        self.hostname = data.hostname
        self.username = data.username
        self.password = data.password
        self._repo = data.path or '/'

    def _get_connection(self):
        from ftplib import FTP
        ftp = FTP()
        ftp.encoding = self.ftpencode
        try:
            ftp.connect(self.hostname)
            ftp.login(self.username, self.password)
        except Exception as err:
            raise DispatcherActivationError from err
        return ftp

    def _check_ftp_connection(self):
        from ftplib import error_temp
        try:
            self.ftp.sendcmd('NOOP')
        except error_temp as err:
            if err and err.args[0].startswith('421'):
                self.ftp = self._get_connection()
            else:
                raise DispatcherActivationError from err

    @staticmethod
    def _sanitize_path(path):
        return '{}'.format(path).replace('\\', '/')

    def close(self):
        if self.ftp is not None:
            try:
                self.ftp.quit()
            except Exception:
                pass
            self._finalizer.detach()

    def get_file(self, src: str, dst: str) -> str:
        src_path = self._sanitize_path(os.path.join(self.repopath, src))

        self._check_ftp_connection()

        with open(dst, 'wb') as fp:
            try:
                self.ftp.retrbinary('RETR {}'.format(src_path), callback=fp.write)
            except Exception as err:
                raise IOError(err)
        return dst

    def repo_is_busy(self):
        """Проверка на блокировку репозитория"""
        return BUSYMESSAGE in (fname for fname, _ in self.ftp.mlsd(self.repopath))

    # @property
    # def index_create_date(self) -> datetime:
    #     mdate_as_string = self.ftp.sendcmd('MDTM %s' % self.index_file_path).split()[1]
    #     create_date = datetime.strptime(mdate_as_string, '%Y%m%d%H%M%S')
    #     return create_date


class Dispatcher(object):
    """"""

    def __new__(cls, *args, **kwargs):
        value = args[0].strip('\'').strip('"')

        if re.match(r'[Ff][Tt][Pp]://([\w.-]+:\w+@)?.*', value):
            return FTPDispatcher(*args, **kwargs)
        elif re.match(r'[A-Za-z]:\\(((\w+)(\\?))+)?', value):
            return FileDispatcher(*args, **kwargs)
        elif re.match(r'\\\\[\w.-]+\\\w+((\\)?(\w+)(\\)?)+', value):
            return SMBDispatcher(*args, **kwargs)
        else:
            raise ValueError('Не определен тип репозитория: <{}>'.format(value))


def get_dispatcher(repo, *args, **kwargs):
    return Dispatcher(repo, *args, **kwargs)
