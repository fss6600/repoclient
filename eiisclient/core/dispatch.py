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

BUSYMESSAGE = '__UPDATE_IN_PROCESS__'


class BaseDispatcher(object):
    ''''''
    index_file_name = 'Index.gz'
    index_hash_file_name = 'Index.gz.sha1'

    def __init__(self, *args, **kwargs):
        self.logger = kwargs.get('logger')
        self.encode = kwargs.get('encode', DEFAULT_ENCODING)
        self.tempdir = kwargs.get('tempdir', None) or get_temp_dir(prefix='disp_')

    @property
    def repopath(self):
        return None

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
        '''Перемещение локального файла'''
        raise NotImplementedError

    def remove(self, fpath):
        '''Удаление локального файла'''
        raise NotImplementedError

    def walk_dir(self, dirpath):
        """
        Генератор списка файлов в указанной папке
        :param dirpath:
        :return:
        """
        raise NotImplementedError

    def remove_dir(self, path):
        """"""
        self._clean_dir(path, onerror=True)
        shutil.rmtree(path)
        # try:
        #     shutil.rmtree(path)
        # except OSError as err:
        #     self.logger.debug('** ошибка удаления папки  {} - {}'.format(path, err))

    remove_eiis = remove_dir  # todo: убрать

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


class FileDispatcher(BaseDispatcher):
    ''''''
    def __init__(self, repo, *args, **kwargs):
        """"""
        super(FileDispatcher, self).__init__(*args, **kwargs)
        self.repo = repo
        if self.logger.level == logging.DEBUG:
            self._init_log()

    @property
    def repopath(self):
        return self.repo

    def __repr__(self):
        return '<File Dispatcher-{}>'.format(id(self))

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

    def get_file(self, src, dst=None):
        """

        :return:
        """
        fname = os.path.basename(src)
        if dst is None:
            dst =  os.path.join(self.tempdir.name, fname)
        elif not dst.endswith(fname):
            dst = os.path.join(dst, fname)

        try:
            shutil.copyfile(src, dst)
        except IOError:
            raise  # todo добавить свое исключение или обработку, запись в лог

        return dst

    def repo_is_busy(self):
        return BUSYMESSAGE in os.listdir(self.repo)

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

    def move(self, src, dst):
        # try:
        #     shutil.move(src, dst)
        # except FileNotFoundError:
        #     dirname = os.path.dirname(dst)
        #     os.makedirs(dirname, exist_ok=True)
        #     shutil.move(src, dst)
        dirname = os.path.dirname(dst)
        if not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

        try:
            shutil.copyfile(src, dst)
        except PermissionError:
            #  err to log
            try:
                import stat
                if not os.access(dst, os.W_OK):
                    os.chmod(dst, stat.S_IWUSR)
                    # time.sleep(0.2)
                os.unlink(dst)
                time.sleep(0.2)
                shutil.copyfile(src, dst)
            except Exception:
                raise IOError
        else:
            os.unlink(src)

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

    def _init_log(self):
        super(FileDispatcher, self)._init_log()
        self.logger.debug('{}: repo: {}'.format(self, self.repo))


class SMBDispatcher(FileDispatcher):
    ''''''
    def __repr__(self):
        return '<SMB Dispatcher-{}>'.format(id(self))


class FTPDispatcher(BaseDispatcher):
    """FTP диспетчер"""
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError

    def __init__(self, repo, encode=DEFAULT_ENCODING, ftpencode=DEFAULT_ENCODING):
        super(FTPDispatcher, self).__init__(None, encode)
        ftpcon = self._get_url_data(repo)
        self.hostname = ftpcon.get('host')
        self.username = ftpcon.get('user')
        self.password = ftpcon.get('pass')
        self.repo = ftpcon.get('path')
        self.ftpencode = ftpencode
        del ftpcon
        self.ftp = self.ftp_init()

    def __repr__(self):
        return 'FTP Dispatcher  <{}> on <{}{}>'.format(id(self), self.hostname, self.repo)

    @property
    def repopath(self):
        return self.repo

    def _get_url_data(self, repo_string):
        """"""
        from urllib.parse import urlparse
        data = urlparse(repo_string)
        return {
            'host': data.hostname,
            'user': data.username,
            'pass': data.password,
            'path': data.path or '/'
            }

    def ftp_init(self):
        from ftplib import FTP
        ftp = FTP()
        ftp.encoding = self.ftpencode
        try:
            ftp.connect(self.hostname)
            ftp.login(self.username, self.password)
        except Exception as err:
            raise  # todo exception

        return ftp

    def get_file(self, src, dst=None):
        """"""
        fname = os.path.basename(src)

        if dst is None:
            dst = os.path.join(self.tempdir.name, fname)
        elif not dst.endswith(fname):
            dst = os.path.join(dst, fname)

        src_path = self._sanitize_path(os.path.join(self.repo, src))
        dst_path = os.path.join(dst, fname)

        with open(dst_path, 'wb') as fp:
            try:
                self.ftp.retrbinary('RETR %s' % src_path, callback=fp.write)
            except Exception as err:  # todo пересмотреть исключения
                raise IOError(err)

        return dst_path

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
            self.finalizer.detach()

    # def check(self):
    #     from ftplib import error_temp
    #     try:
    #         self.ftp.sendcmd('TYPE I')
    #     except error_temp as err:
    #         if err and err.args[0].startswith('421'):
    #             self.close()
    #             self.init()
    #         else:
    #             raise err

    def repo_is_busy(self):
        """Проверка на блокировку репозитория"""
        return BUSYMESSAGE in (fname for fname, _ in self.ftp.mlsd(self.repo))

    # def stat(self, fpath):
    #     """
    #
    #     :param fpath:
    #     :return:
    #     """
    #     rdir, rfile = os.path.split(fpath)
    #
    #     for fname, fstatdata in self.ftp.mlsd(rdir):
    #         if fname == rfile:
    #             return {'size': fstatdata['size'], 'mtime': fstatdata['modify']}


class Dispatcher(object):
    """"""

    def __new__(cls, *args, **kwargs):
        value = args[0].strip('\'').strip('"')

        if re.match(r'[FfTtPp]+://\w+:\w+@.*', value):
            return FTPDispatcher(*args, **kwargs)
        elif re.match(r'[A-Za-z]:\\(((\w+)(\\?))+)?', value):
            return FileDispatcher(*args, **kwargs)
        elif re.match(r'\\\\\w+\\\w+((\\)?(\w+)(\\)?)+', value):
            return SMBDispatcher(*args, **kwargs)
        else:
            raise ValueError('Не определен тип репозитория: <{}>'.format(value))


def get_dispatcher(repo, *args, **kwargs):
    return Dispatcher(repo, *args, **kwargs)
