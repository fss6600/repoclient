# -*- coding: utf-8 -*-

"""Main module."""
import sys
from argparse import ArgumentParser

import wx

from eiisclient.interface import MainFrame


def get_args():
    """
    Возвращает данные командной строки

    :return: NameSpace
    """
    parser = ArgumentParser(prog='eiisclient.exe')
    parser.add_argument("-d", "--debug", dest='debug', action="store_true",
                        default=None, help="включить режим отладки")
    parser.add_argument("-l", "--log", dest='logfile', action="store_true",
                        default=None, help="записывать сообщения в рабочей директории")

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

    app = wx.App()
    MainFrame(args)
    app.MainLoop()


if __name__ == '__main__':
    sys.exit(main())
