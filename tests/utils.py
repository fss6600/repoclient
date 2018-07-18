import logging
import os
import string

import random
import sys
from os.path import join
from tempfile import TemporaryDirectory as TempDir

symbols = string.digits + string.ascii_lowercase
packages_count = random.randint(5, 15)
symbols_count = random.randint(8, 16)
encode = 'utf-8'

#  examles data
FILEFORDELETE = 'file_must_be_delete'
PACKAGES = {
    'Бухгалтерия':
        [('compkeep.exe', 20480),
         ('compkeep.ini', 3072),
         ('F4_2006_21.dbf', 57344),
         (FILEFORDELETE, 4096),
         ('template\\0504089.xls', 71680),
         ('template\\AccRotor.frf', 4096)],
    'RapRep':
        [('RapRep.exe', 1328128),
         ('history.txt', 1024),
         ('RapRepu.chm', 44032)],
    }

NEW_DATA = {
    'Бухгалтерия':
        [('compkeep.exe', 21548),
         ('compkeep.ini', 3087),
         ('F4_2006_21.dbf', 57344),
         ('F4_2006_22.dbf', 57344),
         ('template\\0504089.xls', 71680),
         ('template\\0504090.xls', 54897),
         ('template\\AccRotor.frf', 4096)],
    }


def _get_name():
    w = ''
    for i in range(symbols_count):
        w += random.choice(symbols)
    return w.capitalize()


#  рандомное создание файлов и папок для тестового репозитория
def _create_files(fpath, fcount):
    for file in range(fcount):
        fn = join(fpath, _get_name())
        with open(fn, 'wb') as fp:
            data = random._urandom(random.randint(128, 1024 * 1024))
            fp.write(data)


def _create_folders(fpath, fcount):
    for f in range(fcount):
        fpath = join(fpath, _get_name())
        os.mkdir(fpath)
        fcount = random.randint(2, 10)
        _create_files(fpath, fcount)


def _create_example_data(repo_path, data):
    for folder in data.keys():
        os.makedirs(join(repo_path, folder), exist_ok=True)

        for fdata in data.get(folder):
            name, size = fdata
            f = join(repo_path, folder, os.path.split(name)[0])
            if not os.path.exists(f):
                os.makedirs(f, exist_ok=True)

            with open(join(repo_path, folder, name), 'wb') as fp:
                fp.write(random._urandom(size))


def get_temp_dir(prefix='eiisrepo_'):
    return TempDir(prefix=prefix, dir=os.path.expandvars('%TEMP%'))


def create_test_repo(repo_path, create_random=True, packages=None):
    if create_random:
        for package in range(packages_count):
            pack_path = join(repo_path, _get_name())
            os.mkdir(pack_path)

            fcount = random.randint(3, 15)
            _create_files(pack_path, fcount)

            folders_count = random.randint(0, 2)
            _create_folders(pack_path, folders_count)

    #  добавление конкретных пакетов (подсистем) с конкретными именами файлов
    _create_example_data(repo_path, packages if packages else PACKAGES)


def update_index_file(repo_path):
    _create_example_data(repo_path, NEW_DATA)
    os.unlink(join(repo_path, 'Бухгалтерия', FILEFORDELETE))


if __name__ == '__main__':
    logger = logging.Logger('test')
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.info('test log message')
