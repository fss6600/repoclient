# -*- coding: utf-8 -*-
import hashlib
import json
import os
import stat
import time



from eiisclient import DEFAULT_ENCODING

SLEEP = 0.1


def jsonify(data):
    """Форматирование данных в json формат

    :param data: dict
    :return: json
    """
    return json.JSONEncoder(ensure_ascii=False, indent=4).encode(data)


def unjsonify(data):
    """Преобразование данных из json

    :param data: JSON-format
    :return:
    """
    return json.JSONDecoder().decode(data)


def file_hash_calc(fpath):  # pragma: no cover
    """
    Вычисление SHA1 контрольной суммы файлового объекта

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


def hash_calc(data: object) -> str:  # pragma: no cover
    """
    Возвращает хэш-сумму объекта данных

    :param data: объект данных
    :return: хэш сумма объекта
    """
    sha1 = hashlib.sha1()
    sha1.update(jsonify(data).encode(DEFAULT_ENCODING))
    return sha1.hexdigest()


def change_write_mod(fp, sleep=SLEEP):
    """Установка прав записи на файл владельцу"""
    if not os.access(fp, os.W_OK):
        os.chmod(fp, stat.S_IWUSR)
        time.sleep(sleep)


def read_file(file_path: str, encoding=DEFAULT_ENCODING):
    """
    Чтение содержимого файла

    :param file_path: полный путь к файлу
    :return: str or None
    """
    try:
        with open(file_path, encoding=encoding) as fp:
            return fp.read()
    except FileNotFoundError:
        return None
