# -*- coding: utf-8 -*-
#
import logging
import os
import re
import shutil
import stat
import time
import weakref

from eiisclient import DEFAULT_ENCODING
from eiisclient.core.utils import from_json, get_temp_dir, gzip_read

BUSYMESSAGE = '__REGLAMENT__'


class BaseDispatcher(object):
    ''''''
    index_file_name = 'Index.gz'
    index_hash_file_name = 'Index.gz.sha1'

    def __init__(self, *args, **kwargs):
        self.repo = None
        self.logger = kwargs.get('logger')
        self.encode = kwargs.get('encode', DEFAULT_ENCODING)
        self.tempdir = get_temp_dir(prefix='disp_')

    @property
    def repopath(self):
        return self.repo

    def _clean_dir(self, dirpath, onerror=False):
        for fp, _ in self.walk_dir(dirpath):
            try:
                os.remove(fp)
            except PermissionError as err:
                self.logger.debug(err)
                try:
                    if not os.access(fp, os.W_OK):
                        os.chmod(fp, stat.S_IWUSR)
                        time.sleep(0.3)
                        os.unlink(fp)
                except PermissionError as err:
                    self.logger.debug(err)
                    self.logger.error('** ошибка доступа - не удалось удалить файл {}'.format(fp))
                    if onerror:
                        raise

    def get_file(self, src, dst=None):
        '''Загрузка файла из репозитория во временную директорию'''
        raise NotImplementedError

    def repo_is_busy(self):
        '''Проверка на состояние регламента репозитория'''
        raise NotImplementedError

    def move(self, src, dst):
        dirname = os.path.dirname(dst)

        if not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

        try:
            shutil.copyfile(src, dst)
        except PermissionError:
            try:
                import stat
                if not os.access(dst, os.W_OK):
                    os.chmod(dst, stat.S_IWUSR)
                    time.sleep(0.3)
                os.unlink(dst)
                time.sleep(0.3)
                shutil.copyfile(src, dst)
            except Exception as err:
                raise IOError(err)
        else:
            os.unlink(src)

    def remove(self, fpath, onerror=False):
        """Удаление локального файла"""
        try:
            os.unlink(fpath)
        except FileNotFoundError:
            pass
        except Exception as err:
            self.logger.error('** ошибка удаления файла "{}"'.format(fpath))
            self.logger.debug(err)
            if onerror:
                raise

    def walk_dir(self, dirpath):
        """ Генератор списка файлов в указанной папке

            Возвращает:
            fpath: список полных путей файлов
            rpath: относительных путей файлов
        """
        for (root, _, filenames) in os.walk(dirpath):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                rpath = os.path.relpath(fpath, dirpath)
                yield fpath, rpath

    def remove_dir(self, path):
        """"""
        self._clean_dir(path, onerror=True)
        shutil.rmtree(path)

    def write(self, fpath, data):
        """

        :param fpath:
        :param data:
        :return:
        """
        with open(fpath, 'w') as fp:
            fp.write(data)

    def get_index_hash(self):
        pass

    def get_index_data(self):
        pass

    def _init_log(self):
        self.logger.debug('{}: encode: {}'.format(self, self.encode))
        self.logger.debug('{}: tmpdir: {}'.format(self, self.tempdir.name))
        self.logger.debug('{}: repo: {}'.format(self, self.repo))

    def close(self):
        pass


class FileDispatcher(BaseDispatcher):
    ''''''

    def __init__(self, repo, *args, **kwargs):
        """"""
        super(FileDispatcher, self).__init__(*args, **kwargs)
        self.repo = repo
        if self.logger.level == logging.DEBUG:
            self._init_log()

    def __repr__(self):
        return '<File Dispatcher-{}>'.format(id(self))

    def get_file(self, src, dst=None):
        """

        :return:
        """
        fname = os.path.basename(src)
        if dst is None:
            dst = os.path.join(self.tempdir.name, fname)
        elif not dst.endswith(fname):
            dst = os.path.join(dst, fname)

        shutil.copyfile(src, dst)

        return dst

    def repo_is_busy(self):
        return BUSYMESSAGE in os.listdir(self.repo)

    def get_index_hash(self):
        index_hash_file_path = os.path.join(self.repopath, self.index_hash_file_name)
        try:
            with open(index_hash_file_path) as fp:
                return fp.read()
        except FileNotFoundError:
            return ''

    def get_index_data(self):
        index_file_path = os.path.join(self.repopath, self.index_file_name)
        return from_json(gzip_read(index_file_path, encode=self.encode))


class SMBDispatcher(FileDispatcher):
    ''''''

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
        self.repo = None
        self._parse_url_data(repo)
        self.ftp = self._ftp_init()
        self._finalizer = weakref.finalize(self, self.close)

    def __repr__(self):
        return 'FTP Dispatcher  <{}> on <{}{}>'.format(id(self), self.hostname, self.repo)

    def _parse_url_data(self, repo_string):
        """"""
        from urllib.parse import urlparse
        data = urlparse(repo_string)
        self.hostname = data.hostname
        self.username = data.username
        self.password = data.password
        self.repo = data.path or '/'

    def _ftp_init(self):
        from ftplib import FTP
        ftp = FTP()
        ftp.encoding = self.ftpencode
        try:
            ftp.connect(self.hostname)
            ftp.login(self.username, self.password)
        except Exception as err:
            raise ConnectionError from err

        return ftp

    def _check_connection(self):
        from ftplib import error_temp
        try:
            self.ftp.sendcmd('NOOP')
        except error_temp as err:
            if err and err.args[0].startswith('421'):
                self.ftp = self._ftp_init()
            else:
                raise ConnectionError from err

    def _sanitize_path(self, path):
        """ Заменяет \ на / в пути """
        return '{}'.format(path).replace('\\', '/')

    def close(self):
        self.tempdir.cleanup()
        if self.ftp is not None:
            try:
                self.ftp.quit()
            except Exception:
                pass
            self._finalizer.detach()

    def get_file(self, src, dst=None):
        """"""
        fname = os.path.basename(src)

        if dst is None:
            dst_path = os.path.join(self.tempdir.name, fname)
        elif not dst.endswith(fname):  # если указана папка
            dst_path = os.path.join(dst, fname)
        else:
            dst_path = dst

        src_path = self._sanitize_path(os.path.join(self.repo, src))

        self._check_connection()

        with open(dst_path, 'wb') as fp:
            try:
                self.ftp.retrbinary('RETR {}'.format(src_path), callback=fp.write)
            except Exception as err:
                raise IOError(err)

        return dst_path

    def repo_is_busy(self):
        """Проверка на блокировку репозитория"""
        return BUSYMESSAGE in (fname for fname, _ in self.ftp.mlsd(self.repo))

    def get_index_hash(self):
        index_hash_file_path = os.path.join(self.repopath, self.index_hash_file_name)
        fp = self.get_file(index_hash_file_path)
        try:
            with open(fp) as fp:
                return fp.read()
        except FileNotFoundError:
            return ''

    def get_index_data(self):
        index_file_path = os.path.join(self.repopath, self.index_file_name)
        fp = self.get_file(index_file_path)
        return from_json(gzip_read(fp, encode=self.encode))


class Dispatcher(object):
    """"""

    def __new__(cls, *args, **kwargs):
        value = args[0].strip('\'').strip('"')

        if re.match(r'[Ff][Tt][Pp]://(\w+:\w+@)?.*', value):
            return FTPDispatcher(*args, **kwargs)
        elif re.match(r'[A-Za-z]:\\(((\w+)(\\?))+)?', value):
            return FileDispatcher(*args, **kwargs)
        elif re.match(r'\\\\\w+\\\w+((\\)?(\w+)(\\)?)+', value):
            return SMBDispatcher(*args, **kwargs)
        else:
            raise ValueError('Не определен тип репозитория: <{}>'.format(value))


def get_dispatcher(repo, *args, **kwargs):
    return Dispatcher(repo, *args, **kwargs)
