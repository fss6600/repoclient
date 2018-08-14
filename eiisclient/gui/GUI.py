# -*- coding: utf-8 -*-
import hashlib
import logging
import os
import shutil
import sys
import threading
from time import sleep

import wx

from eiisclient.core.exceptions import CopyPackageError, PacketDeleteError
from eiisclient.gui import main
from eiisclient import __version__, __author__, __email__, __division__, CONFIGFILENAME
from eiisclient import DEFAULT_ENCODING, WORKDIR, DEFAULT_INSTALL_PATH
from eiisclient.core.utils import to_json, from_json, get_config_data, hash_calc
from eiisclient.core.manage import Manager, copy_package


def move_packages(src, dst):
    try:
        for packname in os.listdir(src):
            s = os.path.join(src, packname)
            d = os.path.join(dst, packname)
            copy_package(s, d)
    except Exception as err:
        raise CopyPackageError from err


class MainFrame(main.fmMain):

    def __init__(self):
        super(MainFrame, self).__init__(None)

        if not os.path.exists(WORKDIR):
            os.makedirs(WORKDIR, exist_ok=True)

        self.logger = self.get_logger()
        self.local_index = None
        self.new_index = None
        self.local_index_hash = None
        self.new_index_hash = None
        self.active_packet_list = None
        self.repopath = None
        self.eiispath = None
        self.manager = None

        self.init()
        self.wxLogView.Clear()
        self.Show()

    def on_enter_package_list( self, event ):
        self.wxPacketList.SetFocus()

    def on_enter_log_info( self, event ):
        self.wxLogView.SetFocus()

    def on_about(self, event):
        title = 'О программе'
        msg = "Обновление подсистем ЕИИС 'Соцстрах'"
        msg += '\n{}'.format(__division__)
        msg += "\n{} <{}>".format(__author__, __email__)
        msg += "\nВерсия: {}".format(__version__)

        dlg = wx.MessageDialog(self, msg, title)
        dlg.ShowModal()
        dlg.Destroy()

    def on_config(self, event):
        ConfigFrame(self, self).Show()

    def on_exit(self, event):
        ''''''
        # todo  добавить дополнителльную обработку перед завершением
        self.Close(True)

    def on_update( self, event ):
        thread = threading.Thread(target=self.run)
        thread.setDaemon(True)
        thread.setName('Manager')
        thread.start()

    def on_refresh( self, event ):
        self.update_packet_list()

    def on_btFull( self, event ):
        if self.btFull.IsChecked():
            self.manager.set_full(True)
        else:
            self.manager.set_full(False)

    def on_purge( self, event ):
        dlg = wx.MessageDialog(None, 'Вы уверены?',
                               'Очистка удаленных пакетов', wx.YES_NO | wx.ICON_QUESTION)
        ans = dlg.ShowModal()
        if ans == wx.ID_YES:
            self.logger.debug('Очистка от пакетов, помеченных как удаленные')
            try:

                self.manager.clean_removed()
            except PacketDeleteError as err:
                self.logger.error('Ошибка при очистке удаленных пакетов: {}'.format(err))
            else:
                self.logger.info('Очистка завершена')

    def on_links_update( self, event ):
        self.manager.update_links()

    def run(self):
        installed = self.manager.get_installed_packets()
        selected = self.wxPacketList.GetCheckedStrings()

        self.wxPacketList.Disable()
        self.btUpdate.Disable()
        self.btRefresh.Disable()
        self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.menuConfig.GetId(), enable=False)
        self.menuService.Enable(id=self.menuitemPurge.GetId(), enable=False)
        self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.btFull.GetId(), enable=False)

        try:
            self.manager.activate()
            self.log_append('Начинаем...\n')
            self.manager.start(installed, selected)
        except Exception as err:
            self.logger.error(err)

        finally:
            self.manager.deactivate()

            self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=True)
            self.menuService.Enable(id=self.menuConfig.GetId(), enable=True)
            self.menuService.Enable(id=self.menuitemPurge.GetId(), enable=True)
            self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=True)
            self.menuService.Enable(id=self.btFull.GetId(), enable=True)
            self.wxPacketList.Enable()
            self.btUpdate.Enable()
            self.btRefresh.Enable()
            self.btFull.Check(False)
            self.on_btFull(None)

            self.log_append('Закончили...\n')

    def init(self, full=False):
        """"""
        config = get_config_data(WORKDIR)

        self.threads = config.get('threads', 1)
        self.encode = config.get('encode', DEFAULT_ENCODING)
        self.ftpencode = config.get('ftpencode', self.encode)
        self.purge = config.get('purge', False)
        self.repopath = config.get('repopath', '')
        self.eiispath = config.get('eiispath', DEFAULT_INSTALL_PATH)

        if self.repopath:
            self.manager = Manager(self.repopath,
                                   eiispath=self.eiispath,
                                   logger=self.logger,
                                   encode=self.encode,
                                   ftpencode=self.ftpencode,
                                   purge=self.purge,
                                   threads=self.threads,
                                   full=full
                                   )
        else:
            self.manager = None

        self.update_packet_list()
        self.update_info_view()

    def _init_gui(self):
        self.update_packet_list()
        self.update_info_view()

    def log_append(self, data):
        self.wxLogView.AppendText(data)

    def update_packet_list(self):
        ''''''
        self.wxPacketList.Clear()

        if self.manager is None:
            self.logger.error('Не указан репозиторий. Проверьте настройки.')
            return

        local_index = self.manager.get_local_index()

        if not local_index:
            self.logger.debug('Не обнаружены данные локального индекса. Загрузка с сервера')
            self.manager.activate()
            local_index = self.manager.remote_index
            self.manager.deactivate()

        active_list = self.manager.get_installed_packets()
        index = local_index.keys()
        shared = set(active_list) & set(index)
        abandoned = set(active_list) ^ shared

        for item in abandoned:
            index.append('[!] {}'.format(item))

        self.wxPacketList.Set(sorted(index))

        active_list = ['[!] {}'.format(i) if i in abandoned else i for i in active_list]

        self.wxPacketList.SetCheckedStrings(active_list)  # проставить активные подсистемы

    def update_info_view(self):
        abandoned = [n for n in self.wxPacketList.GetCheckedStrings() if n.startswith('[!]')]
        if len(abandoned):
            self.wxInfoView.AppendToPage('<p style="color: red;">Внимание!</p>')
            self.wxInfoView.AppendToPage('<p style="color:red;">Следующие подсистемы отсутствуют в репозитории:</p>')
            self.wxInfoView.AppendToPage('<ul>')
            for name in abandoned:
                self.wxInfoView.AppendToPage('<li>{}</li>'.format(name))
            self.wxInfoView.AppendToPage('<ul>')

    def get_logger(self):
        logger = logging.getLogger(__name__)
        level = logging.INFO
        formatter = logging.Formatter('%(message)s')
        try:
            arg = sys.argv[1]
            if arg == '-d' or arg == '--debug':
                level = logging.DEBUG
                formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        except IndexError:
            pass
        logger.setLevel(level)
        handler = logging.StreamHandler(stream=Stream(self))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger


class ConfigFrame(main.fmConfig):

    def __init__(self, main_frame: MainFrame, *args, **kwargs):
        self.main_frame = main_frame
        super(ConfigFrame, self).__init__(*args, **kwargs)

        self.config = get_config_data(WORKDIR)
        self.config_hash = hash_calc(self.config)

        ##
        self.wxRepoPath.Value = self.config.get('repopath', '')  # путь к репозитоию

        self.eiis_path_user = os.path.join(os.path.expandvars('%APPDATA%'), r'ЕИИС ФСС РФ')
        config_install_path = self.config.get('eiispath', DEFAULT_INSTALL_PATH)
        if config_install_path == self.eiis_path_user:  # путь установки
            self.wxInstallToUserProfile.SetValue(True)
        else:
            self.wxInstallToUserProfile.SetValue(False)
        self.wxEiisInstallPath.SetPath(config_install_path)
        self.wxEiisInstallPath.Enable(False)

        self.wxThreadsCount.Select(self.config.get('threads', 1) - 1)
        self.wxPurgePackets.SetValue(self.config.get('purge', False))
        self.wxEncode.SetValue(self.config.get('encode', 'UTF-8'))
        self.wxFTPEncode.SetValue(self.config.get('ftpencode', 'UTF-8'))

        self.sdApply.Label = 'Применить'
        self.sdCancel.Label = 'Отменить'
        self.sdCancel.SetFocus()

    def on_eiis_path_click(self, event=None):
        if self.wxInstallToUserProfile.GetValue():
            path = self.eiis_path_user
        else:
            path = DEFAULT_INSTALL_PATH
        self.wxEiisInstallPath.SetPath(path)

    def Apply(self, event):
        self.config['repopath'] = self.wxRepoPath.GetValue()
        self.config['eiispath'] = self.wxEiisInstallPath.GetPath()
        self.config['threads'] = int(self.wxThreadsCount.Selection) + 1
        self.config['purge'] = self.wxPurgePackets.GetValue()
        self.config['encode'] = self.wxEncode.GetValue().upper()
        self.config['ftpencode'] = self.wxFTPEncode.GetValue().upper()

        #  write to file if changed
        if not hash_calc(self.config) == self.config_hash:
            full = False
            confile = os.path.join(WORKDIR, CONFIGFILENAME)
            with open(confile, 'w', encoding=DEFAULT_ENCODING) as fp:
                fp.write(to_json(self.config))

            if not self.config['eiispath'] == self.main_frame.eiispath:
                dlg = wx.MessageDialog(None, 'Скопировать существующие подсистемы по новому пути?',
                                       '', wx.YES_NO | wx.ICON_QUESTION)
                ans = dlg.ShowModal()

                if ans == wx.ID_YES:
                    try:
                        move_packages(self.main_frame.eiispath, self.config['eiispath'])
                    except CopyPackageError:
                        self.main_frame.logger.warning('Не удалось скопировать уже установленные подсистемы.')

                    try:
                        shutil.rmtree(self.main_frame.eiispath)
                    except Exception:
                        self.main_frame.logger.warning('Не удалось удалить установленные подсистемы по прежнему пути.')

                    full = True

            self.main_frame.init(full)  # reread config and set new manager
            self.main_frame.manager.update_links()

        self.Destroy()

    def Cancel(self, event):
        self.Destroy()


class Stream():
    def __init__(self, obj: MainFrame):
        self.obj = obj

    def write(self, record):
        self.obj.wxLogView.AppendText(record)
