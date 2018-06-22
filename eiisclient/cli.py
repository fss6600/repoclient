# -*- coding: utf-8 -*-

"""Main module."""
import sys

import wx
from eiisclient.gui import GUI


def main():
    ''''''
    app = wx.App()
    GUI.MainFrame()

    app.MainLoop()


if __name__ == '__main__':
    sys.exit(main())
