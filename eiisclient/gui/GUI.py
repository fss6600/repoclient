# -*- coding: utf-8 -*-
import logging
import os
import sys
import threading

import wx

from eiisclient import (CONFIGFILENAME, DEFAULT_ENCODING, DEFAULT_INSTALL_PATH, WORKDIR, __author__, __division__,
                        __email__, __version__)
from eiisclient.core.exceptions import DispatcherActivationError, PacketDeleteError
from eiisclient.core.manage import Manager
from eiisclient.core.utils import get_config_data, hash_calc, to_json
from eiisclient.gui import main


class MainFrame(main.fmMain):
    def __init__(self):
        super(MainFrame, self).__init__(None)

        if not os.path.exists(WORKDIR):
            os.makedirs(WORKDIR, exist_ok=True)

        self.logger = self.get_logger()
        self.wxLogView.Clear()
        self.Show()

        self.local_index = None
        self.new_index = None
        self.local_index_hash = None
        self.new_index_hash = None
        self.active_packet_list = None
        self.repopath = None
        self.eiispath = None
        self.manager = None
        self.last_update_date = None

        self.logger.debug('Инициализация программы.')
        self.init()

    def init(self, full=False):
        """"""
        config = get_config_data(WORKDIR)

        self.threads = config.get('threads', 1)
        self.encode = config.get('encode', DEFAULT_ENCODING)
        self.ftpencode = config.get('ftpencode', self.encode)
        self.purge = config.get('purge', False)
        self.repopath = config.get('repopath', '')
        self.eiispath = config.get('eiispath', DEFAULT_INSTALL_PATH)

        try:
            self.manager = Manager(self.repopath,
                                   eiispath=self.eiispath,
                                   logger=self.logger,
                                   encode=self.encode,
                                   ftpencode=self.ftpencode,
                                   purge=self.purge,
                                   threads=self.threads,
                                   full=full
                                   )
        except Exception as err:
            self.logger.error('Ошибка инициализации менеджера: {}'.format(err))
            self.manager = None
        else:
            self.logger.debug('Менеджер инициализирован: {}'.format(self.manager))
            self._init_gui()

    def _init_gui(self):
        try:
            self.update_packet_list()
            self.update_info_view()
        except UnicodeDecodeError:
            self.logger.error('Указана неверная кодировка сервера: {}'.format(self.manager.ftpencode))
        except DispatcherActivationError as err:
            self.logger.error('Ошибка активации диспетчера: {}'.format(err))
        except Exception as err:
            self.logger.error('Ошибка: {}'.format(err))

    # event functions
    def on_enter_view_info(self, event):
        self.wxInfoView.SetFocus()

    def on_enter_log_info(self, event):
        self.wxLogView.SetFocus()

    def on_enter_package_list(self, event):
        self.wxPacketList.SetFocus()

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
        self.Close(True)

    def on_update(self, event):
        thread = threading.Thread(target=self.run)
        thread.setDaemon(True)
        thread.setName('Manager')
        thread.start()

    def on_refresh(self, event):
        self._init_gui()

    def on_btFull(self, event):
        if self.btFull.IsChecked():
            self.manager.set_full(True)
        else:
            self.manager.set_full(False)

    def on_purge(self, event):
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

    def on_menu_select_all(self, event):
        dlg = wx.MessageDialog(None, 'Вы уверены, что хотите УСТАНОВИТЬ ВСЕ ПАКЕТЫ?',
                               'Выбор пакетов', wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.wxPacketList.Freeze()
            self.wxPacketList.SetCheckedItems(range(self.wxPacketList.Count))
            self.wxPacketList.Thaw()

    def on_menu_unselect_all(self, event):
        dlg = wx.MessageDialog(None, 'Вы уверены, что хотите УДАЛИТЬ ВСЕ ПАКЕТЫ?',
                               'Выбор пакетов', wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.wxPacketList.Freeze()
            for item in range(self.wxPacketList.Count):
                self.wxPacketList.Check(item, False)
            self.wxPacketList.Thaw()

    def on_clean_buffer(self, event):
        res = self.manager.clean_buffer()
        if res:
            self.logger.info('Буфер очищен')

    def on_links_update(self, event):
        self.manager.update_links()

    # logic functions
    def run(self):
        installed = self.manager.get_installed_packages()
        selected = self.get_selected_packages()

        # деактивация элементов интерфейса от ненужных нажатий
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
            self.logger.info('Начинаем...')
            self.manager.start(installed, selected)
        except Exception as err:
            self.logger.error(err)

        finally:
            self._init_gui()
            self.manager.deactivate()

            # возврат элементов в изначальное состояние
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

            self.logger.info('Закончили...')
            self.logger.info(50 * '-')

    def log_append(self, message, level=None):

        if level == 'DEBUG':
            color = wx.BLUE
        elif level == 'WARNING':
            color = wx.RED
        elif level == 'ERROR':
            color = wx.RED
        else:
            color = wx.NullColour

        self.wxLogView.SetDefaultStyle(wx.TextAttr(color))
        self.wxLogView.AppendText(message)

    def update_packet_list(self):
        """"""
        try:
            self.wxPacketList.Freeze()
            self.wxPacketList.Clear()

            local_index = self.manager.get_local_index()

            if not local_index:
                self.logger.info('Загрузка индекса')
                self.manager.activate()
                local_index = self.manager.remote_index
                self.manager.deactivate()

            active_list = self.manager.get_installed_packages()
            index = list(local_index.keys())
            shared = set(active_list) & set(index)
            abandoned = set(active_list) ^ shared

            for item in abandoned:
                index.append('[!] {}'.format(item))

            self.wxPacketList.Set(sorted(index))

            active_list = ['[!] {}'.format(i) if i in abandoned else i for i in active_list]

            self.wxPacketList.SetCheckedStrings(active_list)  # проставить активные подсистемы

        finally:
            self.wxPacketList.Thaw()

    def update_info_view(self):
        self.wxInfoView.Freeze()
        self.wxInfoView.SetPage('')
        self.wxInfoView.AppendToPage('<h5 align="center">Программа обновления подсистем ЕИИС "Соцстрах" </h5><hr>')

        if self.manager is None:
            self.wxInfoView.AppendToPage('<p style="color: red;">Программа не проинициализирована.</p>')
        else:
            info = self.manager.get_info()

            self.wxInfoView.AppendToPage('<table><tbody>')

            for key, value in sorted(info.items()):
                self.wxInfoView.AppendToPage(
                    '<tr><td width="200">{}</td><td width="400">{}</td></tr>'.format(key, value))

            self.wxInfoView.AppendToPage('</tbody></table>')

            abandoned = [n for n in self.wxPacketList.GetCheckedStrings() if n.startswith('[!]')]
            if len(abandoned):
                self.wxInfoView.AppendToPage('<p style="color:red;">Внимание!</p>')
                self.wxInfoView.AppendToPage(
                    '<p style="color:red;">Следующие подсистемы имеются на Вашем ПК, но отсутствуют в репозитории:</p>')
                self.wxInfoView.AppendToPage('<ul>')
                for name in abandoned:
                    self.wxInfoView.AppendToPage('<li>{}</li>'.format(name))
                self.wxInfoView.AppendToPage('<ul>')

        self.wxInfoView.Thaw()

    def get_selected_packages(self):
        return self.wxPacketList.GetCheckedStrings()

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
        handler = WxLogHandler(self)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger


class WxLogHandler(logging.StreamHandler):
    def __init__(self, obj=None):
        super(WxLogHandler, self).__init__()
        self.obj = obj
        self.level = logging.DEBUG

    def emit(self, record):
        try:
            msg = ('{}\n'.format(self.format(record)), record.levelname)
            wx.CallAfter(self.obj.log_append, *msg)

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class ConfigFrame(main.fmConfig):
    """"""
    def __init__(self, main_frame: MainFrame, *args, **kwargs):
        self.main_frame = main_frame
        super(ConfigFrame, self).__init__(*args, **kwargs)

        self.config = get_config_data(WORKDIR)
        self.config_hash = hash_calc(self.config)

        ##
        self.wxRepoPath.Value = self.config.get('repopath',
                                                'ftp://10.66.2.131')  # fixme: значение пути сервера репозитория - временно

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
        ## значение кодировки файлов временно заблокировано до перехода на UTF-8
        # self.wxEncode.SetValue(self.config.get('encode', 'UTF-8'))
        self.wxEncode.SetValue('CP1251')
        self.wxEncode.Enable(False)

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
        if self.wxRepoPath.GetValue() == '':
            wx.MessageBox('Укажите путь к репозиторию',
                          'Настройки', wx.ICON_EXCLAMATION, None)
            return

        self.config['repopath'] = self.wxRepoPath.GetValue()
        self.config['eiispath'] = self.wxEiisInstallPath.GetPath()
        self.config['threads'] = int(self.wxThreadsCount.Selection) + 1
        self.config['purge'] = self.wxPurgePackets.GetValue()
        self.config['encode'] = self.wxEncode.GetValue().upper()
        self.config['ftpencode'] = self.wxFTPEncode.GetValue().upper()

        #  write to file if changed
        if not hash_calc(self.config) == self.config_hash:
            full = False

            if not self.config['eiispath'] == self.main_frame.eiispath:

                packages = os.listdir(self.main_frame.eiispath)
                new_eiis_path = self.config['eiispath']
                if packages:
                    dlg = wx.MessageDialog(None, 'Скопировать существующие подсистемы по новому пути?',
                                           'Копирование пакетов', wx.YES_NO | wx.ICON_QUESTION)

                    if dlg.ShowModal() == wx.ID_YES:
                        for package in packages:
                            src = os.path.join(self.main_frame.eiispath, package)
                            dst = os.path.join(new_eiis_path, package)
                            try:
                                self.main_frame.manager.move_package(src, dst)
                            except Exception as err:
                                self.main_frame.logger.warning('Не удалось переместить пакет {} в {}: {}'.format(
                                    package, new_eiis_path, err))
                                self.main_frame.logger.warning(
                                    'Не достаточно прав доступа или не закрыты файлы подсистемы')

                full = True

            confile = os.path.join(WORKDIR, CONFIGFILENAME)
            with open(confile, 'w', encoding=DEFAULT_ENCODING) as fp:
                fp.write(to_json(self.config))

            self.main_frame.init(full)  # reread config and set new manager

        self.Destroy()

    def Cancel(self, event):
        self.Destroy()
