# -*- coding: utf-8 -*-
# Module name: eiisrepo.py
# Copyright © 2018, Michael Petroff <adm_fil_02@ro66.fss.ru>


"""
Репозиторий подсистем ЕИИС 'Соцстрах'

Индексация директории с подсистемами ЕИИС Соцстрах для организации общего репозитория для обновления подсистем на
рабочих местах с локальным доступом или по SMB.
"""

import glob
import gzip
import hashlib
import json
import logging
import os
import sys
import time
from _socket import gethostbyname, gethostname
from collections import defaultdict
from datetime import datetime
from eiisclient import DEFAULT_ENCODING as DEFAULT_ENCODE


def get_null_logger():
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    return logger


class _Dispatcher(object):
    """
    Класс для непосредственной работы с файлами репозитория. Используется классом Manager

    Основные функции:
        init
        read
        write_data
        clean
        write_hash_sum
    """
    gzcompression = 9  # уровень сжатия файла индекса
    dateformat = '%Y%m%d%H%M%S'
    indexfile = 'Index.gz'
    pidfile = '__UPDATE_IN_PROCESS__'

    def __init__(self, repo, **kwargs):
        self.logger = kwargs.get('logger')
        self.encoding = kwargs.get('encoding') or DEFAULT_ENCODE
        self.repo = repo
        self.pidinfo = '{} {} {}'.format(os.getlogin(), gethostname(), gethostbyname(gethostname()))
        self.pidfile = self.joinpath(repo, self.pidfile)
        self.indexfile = self.joinpath(repo, self.indexfile)
        self.hashfilename = '{}.sha1'.format(self.indexfile)
        self.indexfilebkp = '{}.bkp'.format(self.indexfile)

    def __repr__(self):
        return 'Dispatcher on {}'.format(self.repo)

    def __iter__(self):
        return self.list_packages()

    @staticmethod
    def _fhashcalc(fname):
        """ Вычисление SHA1 контрольной суммы файлового объекта

        :param fname путь к файлу
        :return string hexdigest
        """
        sha1 = hashlib.sha1()
        block = 128 * 256  # 4096 for NTFS

        with open(fname, 'rb') as fp:
            for chunk in iter(lambda: fp.read(block), b''):
                sha1.update(chunk)

        return sha1.hexdigest()

    def _packet_hash_calc(self, files):
        '''Вычисление контрольной суммы пакета'''
        hashsum = hashlib.sha1()
        for file in files:
            hashsum.update(files[file].encode(self.encoding))

        return hashsum.hexdigest()

    def _gzip_write(self, gzip_fname, data):
        """Сжатие данных и запись в gzip-файл."""
        if not gzip_fname.endswith('gz'):
            gzip_fname += 'gz'

        with gzip.open(gzip_fname, mode='wt', compresslevel=self.gzcompression, encoding=self.encoding) as fp:
            fp.write_data(data)

    def _gzip_read(self, gzip_fname):
        """Чтение данных из gzip архива"""
        if not gzip_fname.endswith('gz'):
            gzip_fname += 'gz'

        with gzip.open(gzip_fname, mode='rt', encoding=self.encoding) as fp:
            return fp.read()

    @staticmethod
    def _to_json(data):
        """Форматирование данных в _read_json_file формат

        :param data: dict
        :return: json
        """
        return json.JSONEncoder(ensure_ascii=False, indent=4).encode(data)

    @staticmethod
    def _from_json(data):
        """Преобразование данных из json

        :param data: JSON-format
        :return:
        """
        return json.JSONDecoder().decode(data)

    @staticmethod
    def joinpath(path, *paths):
        """Конкатенация путей с нормализацией слэшэй"""
        return os.path.normpath(os.path.join(path, *paths))

    def init(self):
        self.logger.info('инициализация репозитория')

        if os.path.exists(self.pidfile):
            with open(self.pidfile) as fp:
                msg = 'уже запущен другой процесс: {}'.format(fp.read())
                self.logger.error(msg)
            return sys.exit(1)

        try:
            with open(self.pidfile, 'w') as pid:
                pid.write(self.pidinfo)
        except Exception as err:
            self.logger.error('ошибка: {}'.format(err))
            sys.exit(1)

        if os.path.exists(self.indexfile):
            tries = 5
            self.logger.debug('архивирование индекс-файла')
            while tries:
                try:
                    os.rename(self.indexfile, self.indexfilebkp)
                except IOError:
                    time.sleep(5)  # пауза между попытками
                    tries -= 1
                    self.logger.debug('ошибка записи архива. осталось попыток - {}'.format(tries))
                else:
                    return
            self.clean()
            self.logger.debug('Не удалось создать резервную копию индекс-файла')
            raise IOError('Не удалось создать резервную копию индекс-файла')

    def list_packages(self):
        self.logger.debug('построение списка пакетов подсистем')

        for pkg in glob.glob(r'{}\*'.format(self.repo)):
            if os.path.isdir(pkg):
                _, name = os.path.split(pkg)
                yield name

    def walkpackage(self, package):
        path = os.path.normpath(os.path.join(self.repo, package))
        for root, _, files in os.walk(path):
            for fn in files:
                fp = os.path.join(root, fn)
                fname = os.path.relpath(fp, path)
                # fsize = os.path.getsize(fp)
                # fdate = time.strftime(self.dateformat, time.gmtime(os.path.getmtime(fp)))
                fhash = self._fhashcalc(fp)
                # yield {'fname': fname, 'fsize': fsize, 'fdate': fdate, 'fhash': fhash}
                # print({fname: fhash})
                self.logger.debug('{} - {}={}'.format(package, fname, fhash))
                yield {fname: fhash}

    def read(self):
        return self._from_json(self._gzip_read(self.indexfile))

    def write_data(self, data):
        self.logger.debug('запись индекс-файла')
        json_data = self._to_json(data)
        return self._gzip_write(self.indexfile, json_data)

    def clean(self):
        for fn in (self.pidfile, self.indexfilebkp):
            try:
                os.unlink(fn)
            except (TypeError, FileNotFoundError):
                pass
            else:
                self.logger.debug('удален {}'.format(fn))

    def write_hash_sum(self):
        ''''''
        hashsum = self._fhashcalc(self.indexfile)

        self.logger.debug('вычисление контрольной суммы индекс-файла')

        with open(self.hashfilename, 'w') as fp:
            fp.write(hashsum)


class Manager(object):
    """Индексирование репозитория ЕИИС "Соцстрах" """

    def __init__(self, repo, excludes=None, aliases=None, logger=None, encoding=None):
        '''
        :param repo: - полный путь к репозиторию
        :param excludes: - список подсистем исключаемых из индексации
        :param aliases: - словарь синонимов для названий подсистем; используется при создании ссылок на подсистемы,
        в случае, если подсистема имеет английское или плохо воспринмаемое название
        :param logger: - объект логгера для логгирование процесса
        :param encoding: - кодировка символов
        '''
        self.repo = repo
        self.excludes = excludes or []
        self.aliases = aliases or {}
        self.indexdata = defaultdict(dict)
        self.logger = logger or get_null_logger()
        self.fd = _Dispatcher(repo, logger=self.logger, encoding=encoding)

    def index(self) -> None:
        '''
        Основная функция индексации репозитория.

        При старте индексации создается файл-флаг __UPDATE_IN_PROCESS__ в корне репозитория, для информирования
        клиентов о процессе индексации. После установки флага файл-индекс (если существует) переименовывается в
        Index.gz.bkp. При возникновении ошибки чтения-записи при переименовании файла, процесс повторяется до 5-ти раз
        с интервалом в 5 секунд.
        Производится обход папок с подсистемами, за исключением указанных в списке excludes, с вычислением размера,
        даты создания, контрольной суммы. При наличии синонима в словаре aliases, синоним подсистемы добавляется в
        индекс. Данные записываются в файл-индекс, вычисляется контрольная сумма файла-индекса, с записью в одноименный
        файл с добавлением расширения .sha1.
        По окончанию индексации удаляются бэкап-файл и флаг.
        :return: None
        '''
        self.logger.info('репозиторий {} - начинаем индексацию'.format(self.repo))

        self.fd.init()

        for package in self.fd:
            if package in self.excludes:
                self.logger.info('{} - проигнорирован'.format(package))
                continue

            files = {}
            for fdata in self.fd.walkpackage(package):
                # fdata['alias'] = self.aliases.get(package, None)  # добавление ключа с алиасом
                files.update(fdata)
            self.indexdata[package]['files'] = files
            self.indexdata[package]['alias'] = self.aliases.get(package, None)
            self.indexdata[package]['phash'] = self.fd._packet_hash_calc(files)

            self.logger.info('{} - обработан'.format(package))

        self.fd.write(self.indexdata)
        self.fd.write_hash_sum()
        self.fd.clean()

        self.logger.info('индексация завершена')

    def get_index(self) -> dict:
        '''
        Возвращает словарь с данными индекс-файла
        :return: dict
        '''
        return self.fd.read()

    def get_info(self):
        data = {}
        if os.path.exists(self.fd.indexfile):
            data['Размер файла'] = os.path.getsize(self.fd.indexfile)
            data['Дата изменения'] = datetime.fromtimestamp(os.path.getmtime(self.fd.indexfile)).strftime(
                '%d-%m-%Y %H:%M:%S')
            data['Контрольная сумма'] = open(self.fd.hashfilename).read()
            data['Проиндексировано'] = len(self.get_index().keys())

        return data
