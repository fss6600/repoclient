# -*- coding: utf-8 -*-

"""Main module."""
import sys

import wx

from eiisclient.utils import get_args
from eiisclient.interface import MainFrame


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
