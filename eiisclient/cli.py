# -*- coding: utf-8 -*-

"""Main module."""
import os
import sys

import wx
from eiisclient import __version__
from gui import GUI


class ConfigFrame(GUI.FrameConfig):

    def __init__(self, *args, **kwargs):
        super(ConfigFrame, self).__init__(*args, **kwargs)
        self.sdApply.Label = 'Применить'
        self.sdCancel.Label = 'Отменить'
        self.WorkDir.Label = os.path.normpath(os.path.join(os.path.expandvars('%APPDATA%'),
                                                           'Обновление ЕИИС Соцстрах'))

    def Cancel( self, event ):
        self.Hide()
        del self


class MainFrame(GUI.FrameMain):

    def __init__(self):
        super(MainFrame, self).__init__(None)

    def on_about( self, event ):
        msg = "Обновление подсистем ЕИИС 'Соцстрах'.\nВерсия: {}".format(__version__)
        title = 'О программе'
        dlg = wx.MessageDialog(self, msg, title)
        dlg.ShowModal()
        dlg.Destroy()

    def on_config( self, event ):
        self.fmConfig = ConfigFrame(self)
        self.fmConfig.Show()

    def on_exit( self, event ):
        ''''''
        #todo  добавить дополнителльную обработку перед завершением
        self.Close(True)


if __name__ == '__main__':
    ''''''
    app = wx.App()
    frame = MainFrame()
    frame.Show()

    app.MainLoop()
