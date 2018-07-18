# -*- coding: utf-8 -*-
import os
import wx

from eiisclient.gui import main
from eiisclient import __version__, __author__, __email__, __division__
from eiisclient import DEFAULT_ENCODING, WORKDIR, DEFAULT_INSTALL_PATH
from eiisclient.core.utils import to_json, from_json
from eiisclient.core.manage import Manager







class ConfigFrame(main.fmConfig):

    def __init__(self, *args, **kwargs):
        self.main_frame = kwargs.pop('main_frame')
        super(ConfigFrame, self).__init__(*args, **kwargs)

        self.config = get_config_data()

        self.sdApply.Label = 'Применить'
        self.sdCancel.Label = 'Отменить'

        self.wxEiisInstallPath.SetPath(self.config.get('eiispath', DEFAULT_INSTALL_PATH))
        self.wxEiisInstallPath.Enable(False)

        self.wxRepoPath.Value = self.config.get('repopath', '')
        self.wxThreadsCount.Select(self.config.get('threads_count', 1) - 1)
        self.wxPurgePackets.SetValue(self.config.get('purge_packets', False))

        self.sdCancel.SetFocus()

    def Apply( self, event ):
        self.config['repopath'] = self.wxRepoPath.GetValue()
        self.config['eiispath'] = self.wxEiisInstallPath.GetPath()
        self.config['threads_count'] = int(self.wxThreadsCount.Selection) + 1
        self.config['purge_packets'] = self.wxPurgePackets.GetValue()

        #  write to file
        with open(CONFIGFILE, 'w', encoding=DEFAULT_ENCODING) as fp:
            fp.write(to_json(self.config))
        if self.main_frame is not None:
            self.main_frame.log_append('from config')
        self.Destroy()

    def Cancel(self, event):
        self.Destroy()


class MainFrame(main.fmMain):

    def __init__(self, manager):
        super(MainFrame, self).__init__(None)
        self.manager = manager

        if not os.path.exists(WORKDIR):
            os.makedirs(WORKDIR, exist_ok=True)

        self.logger = None  # todo set logger here

        self.local_index = None
        self.new_index = None
        self.local_index_hash = None
        self.new_index_hash = None
        self.active_packet_list = None
        self.repopath = None
        self.eiispath = None

        #  init

        #
        self.wxLogView.Clear()
        # self.wxStatusBar.SetFieldsCount(2)
        # self.wxStatusBar.SetStatusText('Версия: {}'.format(__version__), 1)
        self.Show()
        self.init()

    #  обработка событий
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
        self.log_append('configurator before open')
        res = ConfigFrame(self, main_frame=self).Show()
        self.log_append('configurator after open')
        self.log_append(res)


    def on_exit(self, event):
        ''''''
        # todo  добавить дополнителльную обработку перед завершением
        self.Close(True)

    def on_update(self, event):
        self.init()
        active_list = self.wxPacketList.GetCheckedStrings()
        # res = self.manager.start(active_list)

        # self.log_append(self.config.get('eiispath', DEFAULT_INSTALL_PATH))

    #
    def init(self):
        ''''''
        self._init_config()
        self.manager = Manager(self.repopath, self.logger)
        self._init_gui()

        self.log_append(str(self.manager))


    def _init_gui(self):
        self.update_packet_list()
        self.update_info_view()
        self.wxGauge.Value = 0

    def _init_config(self):
        config = get_config_data()
        self.repopath = config.get('repopath')
        self.eiispath = config.get('repopath') or DEFAULT_INSTALL_PATH

    def log_append(self, data):
        self.wxLogView.AppendText(data)
        self.wxLogView.LineBreak()

    def update_packet_list(self):
        ''''''
        active_list = self.get_active_packet_list()
        index = self.manager.local_index.keys()

        # active_list = ['Форма 4', 'Форма 6', 'Справочник чего-то там', 'Распределение льготников']
        # index = ['Форма 4', 'Бухгалтерия', 'Ревизор']
        index = []

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



    def fix_active_packet_list(self):
        with open(PACKETLISTFILE, 'w') as fp:
            fp.write(to_json(sorted(self.active_packet_list)))

    def get_index_data(self):
        data = {}
        if os.path.exists(INDEXFILE):
            with open(INDEXFILE) as fp:
                data = from_json(fp.read())

        # return data

        return {
            'Бухгалтерия': '',
            'Отдел кадров': '',
            'Форма 4': '',
            'Форма 6': '',
            'Справочник ОКВЭД': '',
            'Администратор': '',
                }

    def fix_index_data(self):
        ''''''

    def update_gauge(self, data):
        self.wxGauge.Value = data

