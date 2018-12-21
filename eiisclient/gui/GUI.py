# -*- coding: utf-8 -*-
import logging
import os
import sys
import threading

import wx

from eiisclient import (CONFIG_FILE_NAME, DEFAULT_ENCODING, DEFAULT_FTP_ENCODING, DEFAULT_FTP_SERVER,
                        DEFAULT_INSTALL_PATH, PROFILE_INSTALL_PATH, WORK_DIR, __author__, __division__, __email__,
                        __version__)
from eiisclient.core.exceptions import DispatcherActivationError, PacketDeleteError
from eiisclient.core.manage import Manager
from eiisclient.core.utils import ConfigDict, get_config_data, hash_calc, to_json
from eiisclient.gui import main


class MainFrame(main.fmMain):
    def __init__(self):
        super(MainFrame, self).__init__(None)
        self.logger = self.get_logger()
        self.logger.info('Инициализация программы')
        self.logger.info('-' * 100)
        self.logger.info('ЗАКРОЙТЕ ОТКРЫТЫЕ ПОДСИСТЕМЫ ПЕРЕД НАЧАЛОМ ОБНОВЛЕНИЯ!')
        self.logger.info('-' * 100)

        if not os.path.exists(WORK_DIR):
            os.makedirs(WORK_DIR, exist_ok=True)

        self.config = ConfigDict()
        self.manager = None

        # инициализация параметров
        self.config.repopath = DEFAULT_FTP_SERVER  # настройка для филиалал №2 - will remove
        self.config.threads = 1
        self.config.purge = False
        self.config.encode = DEFAULT_ENCODING
        self.config.ftpencode = DEFAULT_FTP_ENCODING
        self.config.install_to_profile = False
        # обновление параметров из файла
        self.config.update(get_config_data(WORK_DIR))

        self.init_manager()
        self.wxPacketList.Clear()
        self.wxLogView.Clear()

        if not hasattr(self.config, 'repopath'):
            self.logger.error('Программа не инициализирована. Проверьте настройки:')
            self.logger.error('\t- не указан путь к репозиторию')
        else:
            self.refresh_gui()

        self.Show()

    def init_manager(self, full=False):
        try:
            self.manager = Manager(self.config, logger=self.logger, full=full)
        except Exception as err:
            self.logger.error('Ошибка инициализации менеджера: {}'.format(err))
            self.manager = None
        else:
            self.logger.debug('Менеджер инициализирован: {}'.format(self.manager))

    def refresh_gui(self):
        try:
            self.update_packet_list()
            self.update_info_view()
        except UnicodeDecodeError:
            self.logger.error('Указана неверная кодировка сервера: {}'.format(self.config.ftpencode))
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
        self.refresh_gui()

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
                self.refresh_gui()

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
            self.refresh_gui()

    def on_links_update(self, event):
        self.manager.update_links()

    # logic functions
    def run(self):
        try:
            self.manager.activate()
            self.logger.info('[Начинаем обновление]')
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
            #
            self.manager.start(installed, selected)
        except Exception as err:
            self.logger.error(err)
        else:
            self.logger.info('[Обновление завершено]')
            self.logger.info(100 * '-')
            self.refresh_gui()
        finally:
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
                self.logger.info('Локальный индекс-файл отсутствует. Загрузка с сервера')
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

        except DispatcherActivationError as err:
            self.logger.error('Ошибка активации диспетчера: {}'.format(err))
            self.logger.error('Не удалось загрузить индекс-файл')
        finally:
            self.wxPacketList.Thaw()

    def update_info_view(self):
        try:
            self.wxInfoView.Freeze()
            self.wxInfoView.SetPage('')
            self.wxInfoView.AppendToPage(
                '<h5 align="center">Программа обновления подсистем <em>ЕИИС "Соцстрах"</em></h5><hr>')

            info = self.manager.get_info()

            self.wxInfoView.AppendToPage('<table>')

            for key, value in sorted(info.items()):
                self.wxInfoView.AppendToPage(
                    '<tr>'
                    '<td>{}</td>'
                    '<td>: <strong>{}</strong></td>'
                    '</tr>'.format(key, value))

            self.wxInfoView.AppendToPage('</table>')

            abandoned = [n for n in self.wxPacketList.GetCheckedStrings() if n.startswith('[!]')]
            if len(abandoned):
                self.wxInfoView.AppendToPage('<p style="color:red;">Внимание!</p>')
                self.wxInfoView.AppendToPage(
                    '<p style="color:red;">Следующие подсистемы имеются на Вашем ПК, но отсутствуют в репозитории:</p>')
                self.wxInfoView.AppendToPage('<ul>')
                for name in abandoned:
                    self.wxInfoView.AppendToPage('<li>{}</li>'.format(name))
                self.wxInfoView.AppendToPage('<ul>')

            removed = self.manager.get_removed_packages()
            if len(removed):
                self.wxInfoView.AppendToPage('<hr><p>Подсистемы, помеченные как <em>удаленные</em>:</p>')
                self.wxInfoView.AppendToPage('<ul>')
                for package in removed:
                    self.wxInfoView.AppendToPage('<li><b>{}</b></li>'.format(package.split('.')[0]))
                self.wxInfoView.AppendToPage('</ul><hr>')

        finally:
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

    def __init__(self, mframe: MainFrame, *args, **kwargs):
        super(ConfigFrame, self).__init__(*args, **kwargs)
        self.config = mframe.config
        self.mframe = mframe
        self.config_hash = hash_calc(self.config)
        # fix eiis install path states
        self.install_to_profile = self.config.install_to_profile
        self.eiis_path = PROFILE_INSTALL_PATH if self.install_to_profile else DEFAULT_INSTALL_PATH

        self.wxRepoPath.Value = self.config.repopath or ''
        self.wxInstallToUserProfile.SetValue(self.config.install_to_profile)
        if self.config.install_to_profile:  # путь установки
            self.wxEiisInstallPath.SetPath(PROFILE_INSTALL_PATH)
        else:
            self.wxEiisInstallPath.SetPath(DEFAULT_INSTALL_PATH)
        self.wxEiisInstallPath.Enable(False)

        self.wxThreadsCount.Select(self.config.threads)
        self.wxPurgePackets.SetValue(self.config.purge)
        # значение кодировки файлов временно заблокировано до перехода на UTF-8
        # self.wxEncode.SetValue(self.config.get('encode', 'UTF-8'))
        self.wxEncode.SetValue('CP1251')
        self.wxEncode.Enable(False)
        self.wxFTPEncode.SetValue(self.config.ftpencode)

        self.sdApply.Label = 'Применить'
        self.sdCancel.Label = 'Отменить'
        self.sdCancel.SetFocus()

    def on_eiis_path_click(self, event=None):
        if self.wxInstallToUserProfile.GetValue():
            self.wxEiisInstallPath.SetPath(PROFILE_INSTALL_PATH)
        else:
            self.wxEiisInstallPath.SetPath(DEFAULT_INSTALL_PATH)

    def Apply(self, event):
        if not self.wxRepoPath.GetValue():
            wx.MessageBox('Укажите путь к репозиторию',
                          'Настройки', wx.ICON_EXCLAMATION, None)
            return

        self.config.repopath = self.wxRepoPath.GetValue()
        # self.config.eiispath = self.wxEiisInstallPath.GetPath()
        self.config.install_to_profile = self.wxInstallToUserProfile.GetValue()
        self.config.threads = int(self.wxThreadsCount.Selection) + 1
        self.config.purge = self.wxPurgePackets.GetValue()
        # self.config.encode = self.wxEncode.GetValue().upper()
        self.config.ftpencode = self.wxFTPEncode.GetValue().upper()

        #  write to file if changed
        if not hash_calc(self.config) == self.config_hash:
            full = False

            if not self.config.install_to_profile == self.install_to_profile:

                packages = os.listdir(self.eiis_path)
                if packages:
                    dlg = wx.MessageDialog(None, 'Скопировать существующие подсистемы по новому пути?',
                                           'Копирование пакетов', wx.YES_NO | wx.ICON_QUESTION)

                    if dlg.ShowModal() == wx.ID_YES:
                        new_eiis_path = PROFILE_INSTALL_PATH if self.config.install_to_profile else DEFAULT_INSTALL_PATH
                        for package in packages:
                            src = os.path.join(self.eiis_path, package)
                            dst = os.path.join(new_eiis_path, package)
                            try:
                                self.mframe.manager.move_package(src, dst)
                            except Exception as err:
                                self.mframe.logger.warning('Не удалось переместить пакет {} в {}: {}'.format(
                                    package, new_eiis_path, err))
                                self.mframe.logger.warning(
                                    'Не достаточно прав доступа или не закрыты файлы подсистемы')

                full = True  # флаг смены пути для менеджера

            confile = os.path.join(WORK_DIR, CONFIG_FILE_NAME)
            with open(confile, 'w', encoding=DEFAULT_ENCODING) as fp:
                fp.write(to_json(self.config))

            self.mframe.init_manager(full)  # set new manager
            self.mframe.refresh_gui()  # update gui
            self.mframe.logger.info('Настройки применены')
            self.mframe.logger.info('-' * 100)

        self.Destroy()

    def Cancel(self, event):
        self.Destroy()
