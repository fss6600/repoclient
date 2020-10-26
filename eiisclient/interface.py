# -*- coding: utf-8 -*-
import logging
import os
import pathlib
import sys
import threading
from logging.handlers import RotatingFileHandler

import wx
import wx.dataview as dv

from eiisclient import (__version__, __email__, __division__, __author__,
                        PROFILE_INSTALL_PATH, DEFAULT_INSTALL_PATH,
                        WORK_DIR, DEFAULT_ENCODING, CONFIGFILE)
from eiisclient.structures import State
from eiisclient.exceptions import RepoIsBusy, NoUpdates
from eiisclient.manager import Manager
from eiisclient.functions import hash_calc, jsonify, write_data
from eiisclient.gui.MainFrame import fmMain, fmConfig

# colors
PCK_NEW = wx.Colour(210, 240, 250, 0)  # новый пакет - нет локально, есть в репозитории
PCK_UPD = wx.Colour(210, 250, 210, 0)  # обновленный пакет - есть локально, есть в репозитории
PCK_ABD = wx.Colour(250, 220, 210, 0)  # исиротевший пакет (abandoned) - есть локально, нет в репозитории
PCK_INS = wx.BLUE  # пакет помечен на установку
PCK_DEL = wx.RED  # пакет помечен на удаление
LOG_ERROR_CLR = wx.RED
LOG_DEBUG_CLR = wx.BLUE
LOG_WARNING_CLR = wx.Colour(204, 102, 0, 0)


class MainFrame(fmMain):
    def __init__(self, args):
        self.logger = get_logger(self.log_append, debug=args.debug, logfile=args.logfile)
        self.debug = args.debug  # type: bool
        self.logger.debug('Инициализация программы')
        super(MainFrame, self).__init__(None)

        self.checked = False
        self.pack_action_list = {
            State.UPD: (self.wxPackList.SetItemBackgroundColour, PCK_UPD),
            State.NON: (self.wxPackList.SetItemForegroundColour, wx.BLACK),
            State.NEW: (self.wxPackList.SetItemBackgroundColour, PCK_NEW),
            State.DEL: (self.wxPackList.SetItemBackgroundColour, PCK_ABD),
        }

        # инициализация интерфейса
        self.wxLogView.Clear()
        self.wxPackList.Clear()

        col_01 = dv.DataViewColumn('', dv.DataViewTextRenderer(), 0, align=0, width=250, flags=1)
        col_02 = dv.DataViewColumn('', dv.DataViewTextRenderer(), 1, align=0, width=450, flags=0)
        self.wxInfo.AppendColumn(col_01)
        self.wxInfo.AppendColumn(col_02)

        self.wxStatusBar.SetFieldsCount(3, [-1, 300, 250])
        self.wxStatusBar.SetStatusText('Обновление ЕИИС "Соцстрах". Версия: {}'.format(__version__), 2)

        self.manager = Manager(logger=self.logger)
        self.refresh_gui()
        self.processBar.SetValue(0)
        self.Show()

    def on_check(self, event):
        self.do_updates_check()

    def on_update(self, event):
        thread = threading.Thread(target=self.do_update)
        thread.setDaemon(True)
        thread.setName('Manager')
        thread.start()

    def on_pack_list_item_select( self, event ):
        pack_name = self.wxPackList.GetString(event.Selection)
        info = '{} [{}]'.format(pack_name, self.manager.pack_list[pack_name].origin)
        self.wxStatusBar.SetStatusText(info)

    def on_enter_log_info(self, event):
        self.wxLogView.SetFocus()

    def on_pack_list_enter(self, event):
        self.wxPackList.SetFocus()

    def on_pack_list_leave(self, event):
        self.wxStatusBar.SetStatusText('')
        try:
            selected = self.wxPackList.GetSelections()[0]
            self.wxPackList.Deselect(selected)
        except IndexError:
            pass

    def on_enter_view_info(self, event):
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

    def on_reset(self, event):
        self.manager.reset()
        self.btUpdate.Disable()
        self.menuService.Enable(id=self.menuUpdate.GetId(), enable=False)
        self.processBar.SetValue(0)
        self.refresh_gui()

    def on_btFull(self, event):
        if self.btFull.IsChecked():
            self.manager.set_full(True)
        else:
            self.manager.set_full(False)

    def on_menu_select_all(self, event):
        dlg = wx.MessageDialog(None, 'Вы уверены, что хотите установить все пакеты?',
                               'Выбор пакетов', wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.wxPackList.Freeze()
            for i in range(self.wxPackList.Count):
                self.wxPackList.Check(i)
                self._pack_list_toggle_item(i)
            self.wxPackList.Thaw()

    def on_menu_unselect_all(self, event):
        dlg = wx.MessageDialog(None, 'Вы уверены, что хотите удалить все пакеты?',
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
            self.logger.info('--\n')
            self.refresh_gui()

    def on_links_update(self, event):
        self.manager.update_links()
        self.logger.info('--\n')

    def on_help(self, event):
        import webbrowser
        try:
            docs_path = pathlib.Path(sys._MEIPASS).joinpath('docs')  # путь после компиляции
            url = docs_path.joinpath('index.html')
        except AttributeError:
            url = pathlib.Path.cwd().parent / 'docs' / 'build' / 'html' / 'index.html'  # путь при разработке
            self.logger.debug(url)

        try:
            webbrowser.open(url.as_uri(), new=1, autoraise=True)
            self.logger.info('Запущен интернет-браузер с документацией')
        except Exception as err:
            self.logger.error(err)
            if self.debug:
                self.logger.exception(err)

    def on_pack_list_item_toggled( self, event ):
        self._pack_list_toggle_item(event.Selection)

    def _pack_list_toggle_item(self, item_id):
        pack_name = self.wxPackList.GetString(item_id)
        pack_data = self.manager.pack_list[pack_name]
        if self.wxPackList.IsChecked(item_id):
            setattr(pack_data, 'checked', True)
            if pack_data.installed:
                self.wxPackList.SetItemForegroundColour(item_id, wx.BLACK)
            else:
                setattr(pack_data, 'status', State.NEW)
                self.wxPackList.SetItemForegroundColour(item_id, PCK_INS)
        else:
            setattr(pack_data, 'checked', False)
            if pack_data.installed:
                setattr(pack_data, 'status', State.DEL)
                self.wxPackList.SetItemForegroundColour(item_id, PCK_DEL)
            else:
                self.wxPackList.SetItemForegroundColour(item_id, wx.BLACK)

    ###
    def activate_interface(self):
        """активация элементов интерфейса"""
        self.logger.debug('активация элементов интерфейса')
        self.wxPackList.Enable()
        if self.checked:
            self.btUpdate.Enable()
            self.menuService.Enable(id=self.menuUpdate.GetId(), enable=True)
        self.btCheck.Enable()
        self.btRefresh.Enable()
        self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=True)
        self.menuService.Enable(id=self.menuConfig.GetId(), enable=True)
        self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=True)
        self.menuService.Enable(id=self.btFull.GetId(), enable=True)
        self.menuService.Enable(id=self.menuCheckUpdate.GetId(), enable=True)
        self.btFull.Check(False)
        self.on_btFull(None)
        #

    def deactivate_interface(self):
        """деактивация элементов интерфейса от ненужных нажатий"""
        self.logger.debug('деактивация элементов интерфейса')
        self.wxPackList.Disable()
        self.btUpdate.Disable()
        self.btCheck.Disable()
        self.btRefresh.Disable()
        self.menuFile.Enable(id=self.menuitemUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.menuConfig.GetId(), enable=False)
        self.menuService.Enable(id=self.menuitemLinksUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.btFull.GetId(), enable=False)
        self.menuService.Enable(id=self.menuCheckUpdate.GetId(), enable=False)
        self.menuService.Enable(id=self.menuUpdate.GetId(), enable=False)
        #

    # logic functions
    def refresh_gui(self):
        try:
            self.update_packet_list_view()
            self.update_info_view()
        except UnicodeDecodeError as err:
            self.logger.error('Ошибка кодировка: {}'.format(err))
        except Exception as err:
            self.logger.error('Ошибка: {}'.format(err))
            if self.debug:
                self.logger.exception(err)

    def do_updates_check(self):
        """Процесс проверки наличия обновлений"""
        try:
            self.deactivate_interface()
            self.manager.check_updates(self.processBar)
        except NoUpdates as e:
            self.checked = True
            self.logger.info(e)
        except RepoIsBusy as e:
            self.on_reset(None)
            self.logger.error(e)
        except Exception as e:
            self.logger.error('Ошибка при получении информации об обновлении: {}'.format(e))
            if self.debug:
                self.logger.exception(e)
        else:
            self.checked = True
        finally:
            self.activate_interface()
            self.refresh_gui()
            self.logger.info('--\n')

    def do_update(self):
        """Процесс обновления/установки/удаления пакетов"""
        try:
            self.deactivate_interface()
            self.manager.start_update(self.processBar)
        except InterruptedError:
            return
        except RepoIsBusy:
            self.on_reset(None)
        except Exception as e:
            self.logger.error(e)
            if self.debug:
                self.logger.exception(e)
            self.logger.info('Процесс завершен с ошибками')
        else:
            self.logger.info('Обновление завершено')
        finally:
            self.manager.reset(remote=True)
            self.refresh_gui()
            self.activate_interface()
            self.logger.info('--\n')

    def log_append(self, message, level=None):
        """"""
        if level == 'DEBUG':
            color = LOG_DEBUG_CLR
        elif level == 'WARNING':
            color = LOG_WARNING_CLR
        elif level == 'ERROR':
            color = LOG_ERROR_CLR
        else:
            color = wx.NullColour
        self.wxLogView.SetDefaultStyle(wx.TextAttr(color))
        self.wxLogView.AppendText(message)

    def update_packet_list_view(self):
        try:
            self.wxPackList.Freeze()
            self.wxPackList.Clear()

            for pack_name in sorted(self.manager.pack_list.keys()):
                pack_data = self.manager.pack_list[pack_name]
                idx = self.wxPackList.Count
                self.wxPackList.Append([pack_name])
                self.wxPackList.Check(idx, pack_data.checked)
                func, flag = self.pack_action_list[pack_data.status]
                func(idx, flag)
                if pack_data.status == State.DEL and not pack_data.checked:
                    self.wxPackList.SetItemForegroundColour(idx, PCK_DEL)
        finally:
            self.wxPackList.Thaw()

    def update_info_view(self):
        """"""
        self.wxInfo.Freeze()
        self.wxInfo.DeleteAllItems()
        for k, v in self.manager.info_list.items():
            self.wxInfo.AppendItem([k, '-' if v is None else str(v)])
        self.wxInfo.Thaw()


class ConfigFrame(fmConfig):
    """"""
    def __init__(self, mframe: MainFrame, *args, **kwargs):
        super(ConfigFrame, self).__init__(*args, **kwargs)
        self.config = mframe.manager.config
        self.mframe = mframe
        self.config_hash = hash_calc(self.config)
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
        self.wxFTPEncode.SetValue(self.config.ftpencode)
        self.sdApply.Label = 'Применить'
        self.sdCancel.Label = 'Отменить'
        self.sdCancel.SetFocus()

    def on_eiis_path_click(self, event):
        if self.wxInstallToUserProfile.GetValue():
            self.wxEiisInstallPath.SetPath(PROFILE_INSTALL_PATH)
        else:
            self.wxEiisInstallPath.SetPath(DEFAULT_INSTALL_PATH)

    def Apply(self, event):
        if not self.wxRepoPath.GetValue():
            wx.MessageBox('Укажите путь к репозиторию',
                          'Настройки', wx.ICON_EXCLAMATION, None)
            return

        self.config.clear()
        self.config.repopath = self.wxRepoPath.GetValue()
        self.config.install_to_profile = self.wxInstallToUserProfile.GetValue()
        self.config.threads = int(self.wxThreadsCount.Selection) + 1
        self.config.ftpencode = self.wxFTPEncode.GetValue().upper()

        #  write_data to file if changed
        if not hash_calc(self.config) == self.config_hash:
            if not self.config.install_to_profile == self.install_to_profile:
                try:
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
                except FileNotFoundError as err:
                    self.mframe.logger.debug(err)
            write_data(CONFIGFILE, jsonify(self.config))
            self.mframe.on_reset(None)
            self.mframe.logger.info('Настройки применены')
            self.mframe.logger.info('--\n')
        self.Destroy()

    def Cancel(self, event):
        self.Destroy()


def get_logger(func_log_out, debug=False, logfile=False):
    logger = logging.getLogger(__name__)
    level = logging.INFO
    formatter = logging.Formatter('%(message)s')
    if debug:
        level = logging.DEBUG
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    if logfile:
        logfile = os.path.join(WORK_DIR, 'messages.log')
        log_handler = RotatingFileHandler(logfile, maxBytes=1024 * 1024, encoding=DEFAULT_ENCODING)
        logger.addHandler(log_handler)
    logger.setLevel(level)
    handler = WxLogHandler(func_log_out)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class WxLogHandler(logging.StreamHandler):
    def __init__(self, func_log_out=None):
        super(WxLogHandler, self).__init__()
        self.func_log_out = func_log_out
        self.level = logging.DEBUG

    def emit(self, record):
        try:
            msg = ('{}\n'.format(self.format(record)), record.levelname)
            wx.CallAfter(self.func_log_out, *msg)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

