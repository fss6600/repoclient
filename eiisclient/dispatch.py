# -*- coding: utf-8 -*-
import locale
import logging
import os
import re
import shutil
from ftplib import error_temp

from eiisclient import DEFAULT_ENCODING
from eiisclient.exceptions import DispatcherActivationError

BUSYMESSAGE = '__REGLAMENT__'


class BaseDispatcher(object):
    """"""

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
        self.down()

    def up(self):
        """"""
        pass

    def down(self):
        pass

    def check(self):
        pass

    @property
    def repopath(self):
        return self._repo

    def get_file(self, src: str, dst: str) -> str:
        """
        Загрузка файла из репозитория
        :param src: полный путь к файлу-источнику
        :param dst: полный путь к файлу-назначению
        :return: полный путь назначения
        """
        raise NotImplementedError

    def repo_is_busy(self):
        """"""
        raise NotImplementedError

    def _init_log(self):
        self.logger.debug('{}: encode: {}'.format(self, self.encode))
        self.logger.debug('{}: tmpdir: {}'.format(self, self._tempdir.name))
        self.logger.debug('{}: repo: {}'.format(self, self.repopath))


class FileDispatcher(BaseDispatcher):
    """Local repo диспетчер"""

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

    def up(self):
        self.check()

    def check(self):
        try:
            os.stat(self._repo)
        except Exception as e:
            raise DispatcherActivationError('Ошибка активации диспетчера: {}'.format(e))

    def repo_is_busy(self):
        return BUSYMESSAGE in os.listdir(self.repopath)


class SMBDispatcher(FileDispatcher):
    """SMB диспетчер"""

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
        self._ftp = None
        self._parse_url_data(repo)

    def __repr__(self):
        return 'FTP Dispatcher  <{}> on <{}{}>'.format(id(self), self.hostname, self.repopath)

    def up(self):
        self._ftp = self._get_connection()

    def down(self):
        if self._ftp is not None:
            try:
                self._ftp.quit()
                self._ftp = None
            except:
                pass

    def check(self):
        """"""
        try:
            self._ftp.sendcmd('NOOP')
        except ConnectionAbortedError:
            self.up()
        except error_temp as err:
            if err.args[0].startswith('42'):  # ошибка управляющего соединения
                self.up()
            else:
                raise DispatcherActivationError from err

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

    @staticmethod
    def _sanitize_path(path):
        """"""
        return '{}'.format(path).replace('\\', '/')

    def get_file(self, src: str, dst: str) -> str:
        src_path = self._sanitize_path(os.path.join(self.repopath, src))

        self.check()
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)

        with open(dst, 'wb') as fp:
            try:
                self._ftp.retrbinary('RETR {}'.format(src_path), callback=fp.write)
            except Exception as err:
                raise IOError(err)
        return dst

    def repo_is_busy(self):
        return BUSYMESSAGE in (fname for fname, _ in self._ftp.mlsd(self.repopath))


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
            return None


def get_dispatcher(repo, *args, **kwargs):
    return Dispatcher(repo, *args, **kwargs)
