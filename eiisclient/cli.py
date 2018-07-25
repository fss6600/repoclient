# -*- coding: utf-8 -*-

"""Main module."""
import logging
import os
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from logging.handlers import RotatingFileHandler

import wx

from eiisclient import DEFAULT_ENCODING, DEFAULT_INSTALL_PATH, WORKDIR, __version__
from eiisclient.core.exceptions import DispatcherActivationError, RepoIsBusy
from eiisclient.core.manage import Manager
from eiisclient.core.utils import get_config_data
from eiisclient.gui import GUI

DESC = r"""
---------------------------------------------------
команды (необязательно):
init - создает или перезаписывает данные конфигурации, указанные в параметрах
info - выводит информацию по установленным пакетам подсистем, дату последнего обновления

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
        '[--eiispath=EIISPATH] [--encode=ENCODE] --repo=REPO [command]'


def get_args():
    ''''''
    programname = 'eiiscli.exe'
    commands = ('init', 'info')

    parser = ArgumentParser(prog=programname,
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
    parser.add_argument("--repo", dest='repo', type=str,
                        default=None, help="полный путь к репозиторию")
    parser.add_argument("--encode", dest='encode', type=str,
                        default=None, help="кодировка вывода сообщений")
    parser.add_argument("--version", action='version', version='{}: {}'.format(programname, __version__),
                        help="версия программы")

    try:
        args = parser.parse_args()
    except Exception:
        raise SystemExit(parser.format_usage())
    else:
        return args


def main():  # pragma: no cover
    ''''''
    try:
        args = get_args()
    except SystemExit as err:
        return err

    logger = logging.Logger(__name__)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if args.log:
        logfile = os.path.join(WORKDIR, 'messages.log')
        log_handler = RotatingFileHandler(logfile, maxBytes=1024 * 1024, encoding=args.encode or DEFAULT_ENCODING)
        logger.addHandler(log_handler)

    if args.nogui:
        con_formatter = logging.Formatter('%(message)s')
        con_handler = logging.StreamHandler(sys.stdout)
        con_handler.setFormatter(con_formatter)
        logger.addHandler(con_handler)

    config = get_config_data(WORKDIR)
    repo = args.repo or config.get('repo', '')
    if not repo:
        return 'Не указан репозиторий'

    eiispath = args.eiispath or config.get('eiispath', DEFAULT_INSTALL_PATH)
    threads = args.threads or config.get('threads', 1)
    encode = args.encode or config.get('encode', DEFAULT_ENCODING)
    purge = args.purge or config.get('purge', False)

    manager = Manager(repo, workdir=WORKDIR, logger=logger, eiispath=eiispath, encode=encode,
                      threads=threads, purge=purge)

    if args.command == 'info':  # todo
        try:
            manager.get_info_as_text()
        except RepoIsBusy as err:
            logger.error(err)
        except DispatcherActivationError as err:
            logger.error('ошибка активации диспетчера репозитория: {}'.format(err))
        except Exception as err:
            logger.error('Ошибка: {}'.format(err))
        return

    if args.command == 'init':
        raise NotImplementedError

    if args.nogui:
        installed = manager.get_installed_packets()
        selected = manager.get_selected_packets()

        try:
            manager.start(installed, selected)
        except Exception as err:
            logger.error(err)
            return 2
        else:
            manager.get_info_as_text()

    else:
        app = wx.App()
        GUI.MainFrame(manager=manager)
        app.MainLoop()


if __name__ == '__main__':
    sys.exit(main())
