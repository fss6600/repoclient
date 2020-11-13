# -*- coding: utf-8 -*-
import gzip
import hashlib
import json
import os
import shutil
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
    except UnicodeDecodeError:
        with open(file_path, encoding='CP1251') as fp:
            return fp.read()
    except FileNotFoundError:
        return None


def write_data(path: str, data: str):
    """
    Запись данных в файл

    :param path: полный путь к файлу
    :param data: данные в текстовом виде
    :return:
    """
    with open(path, mode='w', encoding=DEFAULT_ENCODING) as fp:
        fp.write(data)


def gzread(path: str, encode=DEFAULT_ENCODING) -> str:
    """
    Чтение данных из gzip архива

    :param path: полный путь к файлу
    :param encode: кодировка файла
    :return: json данные
    """
    with gzip.open(path, mode='rt', encoding=encode) as gf:
        return gf.read()


def copytree(src: str, dst: str):
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
                dname = os.path.dirname(d)
                if not os.path.exists(dname):
                    os.makedirs(dname, exist_ok=True)
                shutil.copyfile(s, d)
            except PermissionError:
                try:
                    onerror(os.remove, d, None)
                    shutil.copyfile(s, d)
                except Exception:
                    raise
            except Exception:
                raise


def rmtree(path, ignore_errors=False):
    shutil.rmtree(path, ignore_errors=ignore_errors, onerror=onerror)


def remove(path: str, raise_=False):
    """
    Удаление локального файла

    :param path: полный путь к файлу
    :param raise_: True выбрасывает исключение, False замалчивает исключение
    :return:
    """
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except PermissionError:
        try:
            onerror(os.remove, path, None)
        except:
            if raise_:
                raise


def onerror(func, path, _):
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
