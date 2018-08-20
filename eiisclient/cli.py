# -*- coding: utf-8 -*-

"""Main module."""
import datetime
import logging
import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from logging.handlers import RotatingFileHandler

import wx

from eiisclient import CONFIGFILENAME, DEFAULT_ENCODING, DEFAULT_INSTALL_PATH, SELECTEDFILENAME, WORKDIR, __version__
from eiisclient.core.exceptions import DispatcherActivationError, NoUpdates, RepoIsBusy
from eiisclient.core.manage import Manager
from eiisclient.core.utils import get_config_data, to_json
from eiisclient.gui import GUI

DESC = r"""
---------------------------------------------------
команды (необязательно):
init - создает или перезаписывает данные конфигурации, указанные в параметрах
info - выводит информацию по установленным пакетам подсистем, дату последнего обновления
clean - удаляет пакеты подсистем, помеченные как удаленные

параметры:
repopath - полный путь к репозиторию:
    X:\path\to\eiisrepo
    \\path\to\eiisrepo
    ftp://[user:name@]ftpserver/path/to/eiisrepo
    
eiispath - полный путь для установки подсистем:
    X:\path\to\eiispath

Для более полной информации см. README.html файл
---------------------------------------------------"""

USAGE = '%(prog)s [-h] [-d] [-l] [--version] [--nogui] [--purge] [--threads=N] ' \
        '[--eiispath=EIISPATH] [--encode=ENCODE] --repopath=REPO [command]'


def get_args():
    """"""
    program_name = 'eiiscli.exe'
    commands = ('init', 'info', 'clean')

    parser = ArgumentParser(prog=program_name,
                            formatter_class=RawDescriptionHelpFormatter,
                            usage=USAGE,
                            description=DESC)

    parser.add_argument("command", nargs='?', help='|'.join(commands))
    parser.add_argument("-d", "--debug", dest='debug', action="store_true",
                        default=None, help="включить режим отладки")
    parser.add_argument("-l", "--log", dest='log', action="store_true",
                        default=None, help="записывать сообщения в рабочей директории")
    parser.add_argument("--nogui", dest='nogui', action='store_true',
                        default=None, help="режим без графического интерфейса")
    parser.add_argument("--purge", dest='purge', action='store_true',
                        default=None, help="удаление подсистем с диска")
    parser.add_argument("--threads", dest='threads', type=int, metavar='N',
                        default=None, help="количество потоков для загрузки")
    parser.add_argument("--eiispath", dest='eiispath', type=str,
                        default=None, help="полный путь установки подсистем")
    parser.add_argument("--repopath", dest='repopath', type=str,
                        default=None, help="полный путь к репозиторию")
    parser.add_argument("--encode", dest='encode', type=str,
                        default=None, help="кодировка вывода сообщений")
    parser.add_argument("--ftpencode", dest='ftpencode', type=str,
                        default=None, help="кодировка ftp сервера")
    parser.add_argument("--version", action='version', version='{}: {}'.format(program_name, __version__),
                        help="версия программы")

    try:
        args = parser.parse_args()
    except Exception:
        raise SystemExit(parser.format_usage())
    else:
        return args


def main():  # pragma: no cover
    """"""
    try:
        args = get_args()
    except SystemExit as err:
        return err

    if not args.nogui:  # GUI
        app = wx.App()
        GUI.MainFrame()
        app.MainLoop()

    else:  # CLI
        logger = logging.Logger(__name__)
        if args.debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        if args.log:
            logfile = os.path.join(WORKDIR, 'messages.log')
            log_handler = RotatingFileHandler(logfile, maxBytes=1024 * 1024, encoding=args.encode or DEFAULT_ENCODING)
            logger.addHandler(log_handler)

        con_formatter = logging.Formatter('%(message)s')
        con_handler = logging.StreamHandler(sys.stdout)
        con_handler.setFormatter(con_formatter)
        logger.addHandler(con_handler)

        config = get_config_data(WORKDIR)
        repopath = args.repopath or config.get('repopath', None)

        if not repopath:
            return 'Не указан репозиторий'

        eiis_path = args.eiispath or config.get('eiispath', DEFAULT_INSTALL_PATH)
        threads = args.threads or config.get('threads', 1)
        encode = args.encode or config.get('encode', DEFAULT_ENCODING)
        ftpencode = args.ftpencode or config.get('ftpencode', encode)
        purge = args.purge or config.get('purge', False)

        if args.command == 'init':
            if not os.path.exists(WORKDIR):
                os.makedirs(WORKDIR, exist_ok=True)

            confile = os.path.join(WORKDIR, CONFIGFILENAME)
            confdata = {
                'repopath': repopath,
                'eiispath': eiis_path,
                'threads': threads,
                'encode': encode,
                'purge': purge,
                'ftpencode': ftpencode
                }
            with open(confile, 'w', encoding=DEFAULT_ENCODING) as fp:
                fp.write(to_json(confdata))

            selected_file_name = os.path.join(WORKDIR, SELECTEDFILENAME)
            if not os.path.exists(selected_file_name):
                with open(selected_file_name, 'wb') as fp:
                    fp.write('# Данный файл используется только при работе из консоли\n'.encode(encode))
                    fp.write('# Добавьте наименования пакетов для установки подсистемы по одному на строку\n\n'.encode(encode))
            return ('Инициализация прошла успешно')

        manager = Manager(repopath, logger=logger, eiispath=eiis_path, encode=encode,
                          ftpencode=ftpencode, threads=threads, purge=purge)

        if args.command == 'info':
            try:
                info = manager.get_info()
                for key in sorted(info.keys()):
                    print('{:25}{}'.format(key, info.get(key)))
            except RepoIsBusy as err:
                logger.error(err)
            except DispatcherActivationError as err:
                logger.error('ошибка активации диспетчера репозитория: {}'.format(err))
            except Exception as err:
                logger.error('Ошибка: {}'.format(err))
            return

        if args.command == 'clean':
            try:
                manager.clean_removed()
            except Exception as err:
                res = 'Ошибка при очистке "удаленных" пакетов: {}'.format(err)
            else:
                res = 'Успешно очищено от удаленных'
            return res

        installed = manager.get_installed_packages()
        selected = manager.get_selected_packages()

        begin_time = datetime.datetime.utcnow()
        try:
            manager.start(installed, selected)
        except NoUpdates as err:
            logger.info(err)
            return
        except Exception as err:
            logger.error(err)
            # raise
            return 2
        else:
            pass
        finally:
            end_time = datetime.datetime.utcnow()
            during_time = end_time - begin_time
            logger.debug('Завершено за {}'.format(during_time))


if __name__ == '__main__':
    sys.exit(main())
