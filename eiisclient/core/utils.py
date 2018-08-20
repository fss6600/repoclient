import gzip
import hashlib
import json
import os
import stat
import time
from tempfile import TemporaryDirectory

from eiisclient import DEFAULT_ENCODING

TIMETOSLEEP = 0.1


def to_json(data):
    """Форматирование данных в json формат

    :param data: dict
    :return: json
    """
    return json.JSONEncoder(ensure_ascii=False, indent=4).encode(data)


def from_json(data):
    """Преобразование данных из json

    :param data: JSON-format
    :return:
    """
    return json.JSONDecoder().decode(data)


def gzip_read(gzfile, encode=DEFAULT_ENCODING):  # pragma: no cover
    """Чтение данных из gzip архива"""
    with gzip.open(gzfile, mode='rt', encoding=encode) as gf:
        return gf.read()


def get_temp_dir(prefix=None):  # pragma: no cover
    prefix = prefix or ''
    return TemporaryDirectory(prefix=prefix, dir=os.path.expandvars('%TEMP%'))


def file_hash_calc(fpath):  # pragma: no cover
    """ Вычисление SHA1 контрольной суммы файлового объекта

    :param fpath путь к файлу
    :return string hexdigest
    """
    sha1 = hashlib.sha1()
    block = 128 * 256  # 4096 for NTFS

    try:
        with open(fpath, 'rb') as fp:
            for chunk in iter(lambda: fp.read(block), b''):
                sha1.update(chunk)
    except FileNotFoundError:
        return None
    else:
        return sha1.hexdigest()


def hash_calc(data):  # pragma: no cover
    sha1 = hashlib.sha1()
    sha1.update(to_json(data).encode(DEFAULT_ENCODING))
    return sha1.hexdigest()


def get_config_data(workdir, encode=DEFAULT_ENCODING):
    cfile = os.path.join(workdir, 'config.json')
    try:
        with open(cfile, encoding=encode) as fp:
            config = from_json(fp.read())
    except FileNotFoundError:
        config = {}

    return config


def chwmod(fpath):
    if not os.access(fpath, os.W_OK):
        os.chmod(fpath, stat.S_IWUSR)
        time.sleep(TIMETOSLEEP)
