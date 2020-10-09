# -*- coding: utf-8 -*-
import os
import pathlib
import sys
import threading

import wx
import wx.dataview as dv

from eiisclient import (CONFIG_FILE_NAME, DEFAULT_ENCODING, DEFAULT_FTP_ENCODING, DEFAULT_INSTALL_PATH,
                        PROFILE_INSTALL_PATH, WORK_DIR, __author__, __division__, __email__,
                        __version__)
from eiisclient.core.exceptions import DispatcherActivationError, PacketDeleteError
from eiisclient.core.utils import ConfigDict, get_config_data, hash_calc, to_json
from eiisclient.gui import *
from eiisclient.gui.MainFrame import fmMain, fmConfig


class MainFrame(fmMain):
    def __init__(self, args):
        self.logger = get_logger(self.log_append, debug=args.debug, logfile=args.logfile)
        self.logger.debug('Инициализация программы')
        super(MainFrame, self).__init__(None)

        if not os.path.exists(WORK_DIR):
            os.makedirs(WORK_DIR, exist_ok=True)

        # инициализация параметров
        self.config = ConfigDict()
        self.config.repopath = None
        self.config.threads = 1
        self.config.purge = False
        self.config.encode = DEFAULT_ENCODING
        self.config.ftpencode = DEFAULT_FTP_ENCODING
        self.config.install_to_profile = False
        # обновление параметров из файла настроек
        self.config.update(get_config_data(WORK_DIR))

        self.manager = get_manager(self.config, self.logger)
        self.pack_list = self.get_pack_list()

        # инициализация интерфейса
        self.wxLogView.Clear()
        self.wxPackList.Clear()

        col_01 = dv.DataViewColumn('', dv.DataViewTextRenderer(), 0, align=0, width=250, flags=1)
        col_02 = dv.DataViewColumn('', dv.DataViewTextRenderer(), 1, align=0, width=450, flags=0)
        self.wxInfo.AppendColumn(col_01)
        self.wxInfo.AppendColumn(col_02)

        self.wxStatusBar.SetFieldsCount(3, [100, 180])
        self.wxStatusBar.SetStatusText('Версия: {}'.format(__version__))
        self.wxStatusBar.SetStatusText('Обновление ЕИИС "Соцстрах"', 1)

        self.checked = False
        self.refresh_gui()

        self.Show()

    def refresh_gui(self):
        try:
            self.update_packet_list_view()
            self.update_info_view()
        except UnicodeDecodeError as err:
            self.logger.error('Ошибка кодировка: {}'.format(err))
        except DispatcherActivationError as err:
            self.logger.error('Ошибка активации диспетчера: {}'.format(err))
        except Exception as err:
            self.logger.error('Ошибка: {}'.format(err))

    # event functions
    def on_enter_view_info(self, event):
        self.wxInfo.SetFocus()

    def on_pack_list_item_activated( self, event ):
        print(event.Index)
        if self.wxPackList.IsItemChecked(event.Index):
            self.wxPackList.CheckItem(event.Index, False)
        else:
            self.wxPackList.CheckItem(event.Index, True)

    def on_pack_list_item_select( self, event ):
        pack_name = self.wxPackList.GetString(event.Selection)
        info = '{} [{}]'.format(pack_name, self.pack_list[pack_name].origin)
        self.wxStatusBar.SetStatusText(info, 2)

    def on_pack_list_item_deselect( self, event ):
        self.wxStatusBar.SetStatusText('', 2)

    def on_enter_log_info(self, event):
        self.wxLogView.SetFocus()

    def on_pack_list_enter(self, event):
        self.wxPackList.SetFocus()

    def on_pack_list_leave(self, event):
        """"""
        self.wxStatusBar.SetStatusText('', 2)
        try:
            selected = self.wxPackList.GetSelections()[0]
            self.wxPackList.Deselect(selected)
        except IndexError:
            pass

    def on_info_enter(self, event):
        self.wxInfo.SetFocus()

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
        self.Close(True)

    def on_check(self, event):
        """Проверка наличия обновлений"""
        # check for updates
        self.checked = True
        self.refresh_gui()

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
            self.wxPackList.Freeze()
            for i in range(self.wxPackList.Count):
                self.wxPackList.Check(i)
                self._pack_list_toggle_item(i)
                # self.wxPackList.SetCheckedItems(range(self.wxPackList.Count))
            self.wxPackList.Thaw()

    def on_menu_unselect_all(self, event):
        dlg = wx.MessageDialog(None, 'Вы уверены, что хотите УДАЛИТЬ ВСЕ ПАКЕТЫ?',
                               'Выбор пакетов', wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.wxPackList.Freeze()
            for i in range(self.wxPackList.Count):
                self.wxPackList.Check(i, False)
                self._pack_list_toggle_item(i)
            self.wxPackList.Thaw()

    def on_clean_buffer(self, event):
        res = self.manager.clean_buffer()
        if res:
            self.logger.info('Буфер очищен')
            self.refresh_gui()

    def on_links_update(self, event):
        self.manager.update_links()

    def on_help(self, event):
        import webbrowser
        try:
            docs_path = pathlib.Path(sys._MEIPASS).joinpath('docs')
            url = docs_path.joinpath('index.html').as_uri()
            webbrowser.open(url, new=1, autoraise=True)
            self.logger.info('Запущен интернет-браузер с документацией')
        except Exception as err:
            self.logger.error(err)

    def _pack_list_toggle_item(self, item_id):
        pack_name = self.wxPackList.GetString(item_id)
        installed = self.pack_list[pack_name].installed
        if self.wxPackList.IsChecked(item_id):
            if installed:
                self.wxPackList.SetItemForegroundColour(item_id, wx.BLACK)
            else:
                self.wxPackList.SetItemForegroundColour(item_id, PCK_INS)
        else:
            if installed:
                self.wxPackList.SetItemForegroundColour(item_id, PCK_DEL)
            else:
                self.wxPackList.SetItemForegroundColour(item_id, wx.BLACK)

    def on_pack_list_item_toggled( self, event ):
        self._pack_list_toggle_item(event.Selection)

    ###
    def _activate_interface(self):
        """активация элементов интерфейса"""
        self.logger.debug('активация элементов интерфейса')
        self.wxPackList.Enable()
        self.btUpdate.Enable()
        self.btCheck.Enable()
        self.btRefresh.Enable()
        self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=True)
        self.menuService.Enable(id=self.menuConfig.GetId(), enable=True)
        self.menuService.Enable(id=self.menuitemPurge.GetId(), enable=True)
        self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=True)
        self.menuService.Enable(id=self.btFull.GetId(), enable=True)
        self.btFull.Check(False)
        self.on_btFull(None)
        #

    def _deactivate_interface(self):
        """деактивация элементов интерфейса от ненужных нажатий"""
        self.logger.debug('деактивация элементов интерфейса')
        self.wxPackList.Disable()
        self.btUpdate.Disable()
        self.btCheck.Disable()
        self.btRefresh.Disable()
        self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.menuConfig.GetId(), enable=False)
        self.menuService.Enable(id=self.menuitemPurge.GetId(), enable=False)
        self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.btFull.GetId(), enable=False)
        #

    # logic functions
    def run(self):
        try:
            self._deactivate_interface()
            self.manager.activate()
            self.manager.start(selected=self.get_selected_packages())
        except Exception as err:
            self.logger.error(err)
            self.refresh_gui()
        else:
            self.logger.info('Обновление завершено\n')
            # self.logger.info(100 * '-')
            self.refresh_gui()
        finally:
            self.manager.deactivate()
            self._activate_interface()

    def log_append(self, message, level=None):
        """"""
        if level == 'DEBUG':
            color = wx.BLUE
        elif level == 'WARNING':
            color = wx.GREEN
        elif level == 'ERROR':
            color = wx.RED
        else:
            color = wx.NullColour
        self.wxLogView.SetDefaultStyle(wx.TextAttr(color))
        self.wxLogView.AppendText(message)

    def update_packet_list_view(self):
        act_list = {
            UPD: (self.wxPackList.SetItemBackgroundColour, PCK_UPD),
            NON: (self.wxPackList.SetItemForegroundColour, wx.BLACK),
            NEW: (self.wxPackList.SetItemBackgroundColour, PCK_NEW),
            DEL: (self.wxPackList.SetItemBackgroundColour, PCK_ABD),
        }

        try:
            self.wxPackList.Freeze()
            self.wxPackList.Clear()

            for pack_name in sorted(self.pack_list.keys()):
                pack_data = self.pack_list[pack_name]
                idx = self.wxPackList.Count
                self.wxPackList.Append([pack_name])
                st = pack_data.installed
                self.wxPackList.Check(idx, pack_data.installed)
                func, flag = act_list[pack_data.status]
                func(idx, flag)
        except Exception as err:
            self.logger.exception(err)
        finally:
            self.wxPackList.Thaw()

    def update_info_view(self):
        """"""
        info = self.wxInfo
        info.Freeze()
        info.DeleteAllItems()

        data = self.manager.get_info(self.checked)
        for k, v in data.items():
            info.AppendItem([k, '-' if v is None else str(v)])

        self.wxInfo.Thaw()

    def get_selected_packages(self):
        return self.wxPackList.GetCheckedStrings()

    def get_pack_list(self, remote_index=None) -> PackList:
        pack_list = PackList()
        local_index_packs_cache = self.manager.get_local_index_packages()
        installed_packs = self.manager.get_installed_packages()

        # заполняем данными из индекс-кэша
        for origin_pack_name in local_index_packs_cache:
            alias_pack_name = local_index_packs_cache[origin_pack_name].get('alias') or origin_pack_name
            pack_list[alias_pack_name] = PackData(
                origin=origin_pack_name,
                installed=False,
                status=NON,
            )

        # обновляем статус установки имеющихся пакетов
        for origin_pack_name in installed_packs:
            _, pack_data = pack_list.get_by_origin(origin_pack_name)
            if pack_data:
                setattr(pack_data, 'installed', True)
            else:
                pack_list[origin_pack_name] = PackData(
                    origin=origin_pack_name,
                    installed=True,
                    status=DEL,
                )
        if remote_index:  #
            pass
        return pack_list


class ConfigFrame(fmConfig):
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

        self.wxThreadsCount.Select(self.config.threads - 1)
        self.wxPurgePackets.SetValue(self.config.purge)
        # значение кодировки файлов временно заблокировано до перехода на UTF-8
        # self.wxEncode.SetValue(self.config.get('encode', 'UTF-8'))
        self.wxEncode.SetValue(self.config.encode)
        # self.wxEncode.SetValue('CP1251')
        # self.wxEncode.Enable(False)
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
        self.config.encode = self.wxEncode.GetValue().upper()
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
