# -*- coding: utf-8 -*- 

###########################################################################
## Python code generated with wxFormBuilder (version Jun 11 2018)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.adv
import wx.html
import wx.xrc


###########################################################################
## Class fmMain
###########################################################################

class fmMain ( wx.Frame ):
    
    def __init__( self, parent ):
        wx.Frame.__init__(self, parent, id=wx.ID_ANY, title=u"Обновление ЕИИС Соцстрах", pos=wx.DefaultPosition,
                          size=wx.Size(1000, 700), style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)
        
        self.SetSizeHints( wx.Size( 400,200 ), wx.DefaultSize )
        
        bSizer21 = wx.BoxSizer( wx.VERTICAL )
        
        self.pToolbar = wx.Panel( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bsToolbar = wx.BoxSizer( wx.HORIZONTAL )
        
        
        self.pToolbar.SetSizer( bsToolbar )
        self.pToolbar.Layout()
        bsToolbar.Fit( self.pToolbar )
        bSizer21.Add( self.pToolbar, 0, wx.EXPAND, 5 )
        
        self.sMain = wx.SplitterWindow( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.SP_3D|wx.SP_3DBORDER|wx.SP_LIVE_UPDATE )
        self.sMain.SetSashGravity( 0 )
        self.sMain.SetSashSize( 5 )
        self.sMain.Bind( wx.EVT_IDLE, self.sMainOnIdle )
        self.sMain.SetMinimumPaneSize( 100 )
        
        self.pLeft = wx.Panel( self.sMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        self.pLeft.SetMinSize( wx.Size( 300,-1 ) )
        
        bSizer26 = wx.BoxSizer( wx.VERTICAL )
        
        bSizer26.SetMinSize( wx.Size( 200,200 ) ) 
        bSizer111 = wx.BoxSizer( wx.HORIZONTAL )
        
        self.m_staticText1 = wx.StaticText( self.pLeft, wx.ID_ANY, u"Пакеты подсистем:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText1.Wrap( -1 )
        
        self.m_staticText1.SetToolTip( u"Для установки/удаления поставьте/снимите галку" )
        
        bSizer111.Add( self.m_staticText1, 0, wx.ALL, 5 )
        
        
        bSizer111.Add( ( 0, 0), 1, wx.EXPAND, 5 )
        
        self.btRefresh = wx.BitmapButton( self.pLeft, wx.ID_ANY, wx.ArtProvider.GetBitmap( wx.ART_UNDO, wx.ART_BUTTON ), wx.DefaultPosition, wx.DefaultSize, 0 )
        self.btRefresh.SetToolTip( u"Обновить список пакетов" )
        
        bSizer111.Add( self.btRefresh, 0, wx.ALL, 5 )
        
        
        bSizer26.Add( bSizer111, 0, wx.EXPAND, 5 )
        
        wxPacketListChoices = [u"Choice 1", u"Choice 2", u"Choice 3", u"Choice 4", u"Choice 5"]
        self.wxPacketList = wx.CheckListBox( self.pLeft, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wxPacketListChoices, 0 )
        self.wxPacketList.SetFont( wx.Font( wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, wx.EmptyString ) )
        self.wxPacketList.SetToolTip( u"Установить галки для установки пакетов.\nСнять галки для удаления пакетов." )
        self.wxPacketList.SetMinSize( wx.Size( 200,-1 ) )
        
        bSizer26.Add( self.wxPacketList, 1, wx.ALL|wx.EXPAND, 5 )
        
        bSizer28 = wx.BoxSizer( wx.HORIZONTAL )
        
        
        bSizer26.Add( bSizer28, 0, wx.EXPAND|wx.ALIGN_RIGHT, 5 )
        
        
        self.pLeft.SetSizer( bSizer26 )
        self.pLeft.Layout()
        bSizer26.Fit( self.pLeft )
        self.pRight = wx.Panel( self.sMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        self.pRight.SetMinSize( wx.Size( 200,-1 ) )
        
        bSizer27 = wx.BoxSizer( wx.VERTICAL )
        
        self.m_splitter2 = wx.SplitterWindow( self.pRight, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.SP_3D )
        self.m_splitter2.SetSashSize( 10 )
        self.m_splitter2.Bind( wx.EVT_IDLE, self.m_splitter2OnIdle )
        self.m_splitter2.SetMinimumPaneSize( 100 )
        
        self.m_panel5 = wx.Panel( self.m_splitter2, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bSizer10 = wx.BoxSizer( wx.VERTICAL )
        
        self.wxInfoView = wx.html.HtmlWindow( self.m_panel5, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.html.HW_SCROLLBAR_AUTO )
        self.wxInfoView.SetMinSize( wx.Size( -1,200 ) )
        
        bSizer10.Add( self.wxInfoView, 1, wx.ALL|wx.EXPAND, 5 )
        
        
        self.m_panel5.SetSizer( bSizer10 )
        self.m_panel5.Layout()
        bSizer10.Fit( self.m_panel5 )
        self.m_panel6 = wx.Panel( self.m_splitter2, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bSizer11 = wx.BoxSizer( wx.VERTICAL )
        
        self.wxLogView = wx.TextCtrl( self.m_panel6, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.HSCROLL|wx.TE_MULTILINE|wx.TE_NOHIDESEL|wx.TE_READONLY|wx.TE_RICH )
        bSizer11.Add( self.wxLogView, 1, wx.ALL|wx.EXPAND, 5 )
        
        bSizer12 = wx.BoxSizer( wx.HORIZONTAL )
        
        self.btUpdate = wx.Button( self.m_panel6, wx.ID_ANY, u"Обновить", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.btUpdate.SetDefault()
        
        self.btUpdate.SetToolTip( u"Запустить процесс установки/обновления пакетов." )
        self.btUpdate.SetHelpText( u"Запустить процесс обновления/установки" )
        
        bSizer12.Add( self.btUpdate, 0, wx.ALL, 5 )

        bSizer12.Add((0, 0), 1, wx.EXPAND, 5)

        self.m_hyperlink2 = wx.adv.HyperlinkCtrl(self.m_panel6, wx.ID_ANY, u"Руководство",
                                                 u"http://www.fss6602.lan/wiki/obnovlenie-podsistem-eiis-socstrah-klient/",
                                                 wx.DefaultPosition, wx.DefaultSize, wx.adv.HL_DEFAULT_STYLE)
        bSizer12.Add(self.m_hyperlink2, 0, wx.ALL, 5)
        
        
        bSizer11.Add( bSizer12, 0, wx.EXPAND, 5 )
        
        
        self.m_panel6.SetSizer( bSizer11 )
        self.m_panel6.Layout()
        bSizer11.Fit( self.m_panel6 )
        self.m_splitter2.SplitHorizontally( self.m_panel5, self.m_panel6, 0 )
        bSizer27.Add( self.m_splitter2, 1, wx.EXPAND, 5 )
        
        
        self.pRight.SetSizer( bSizer27 )
        self.pRight.Layout()
        bSizer27.Fit( self.pRight )
        self.sMain.SplitVertically( self.pLeft, self.pRight, 291 )
        bSizer21.Add( self.sMain, 1, wx.EXPAND, 5 )
        
        
        self.SetSizer( bSizer21 )
        self.Layout()
        self.wxStatusBar = self.CreateStatusBar( 1, wx.STB_SIZEGRIP, wx.ID_ANY )
        self.wxMenuBar = wx.MenuBar( 0 )
        self.menuFile = wx.Menu()
        self.menuitemUpdate = wx.MenuItem(self.menuFile, wx.ID_ANY, u"Обновить список пакетов" + u"\t" + u"F5",
                                          u"Обновить список пакетов подсистем", wx.ITEM_NORMAL)
        self.menuFile.Append( self.menuitemUpdate )
        
        self.menuFile.AppendSeparator()
        
        self.m_menu2 = wx.Menu()
        self.menuitem_select_all = wx.MenuItem( self.m_menu2, wx.ID_ANY, u"Выбрать все пакеты", wx.EmptyString, wx.ITEM_NORMAL )
        self.m_menu2.Append( self.menuitem_select_all )
        
        self.menuitem_unselect_all = wx.MenuItem( self.m_menu2, wx.ID_ANY, u"Снять все выделения", wx.EmptyString, wx.ITEM_NORMAL )
        self.m_menu2.Append( self.menuitem_unselect_all )
        
        self.menuFile.AppendSubMenu( self.m_menu2, u"Выбор пакетов" )
        
        self.menuFile.AppendSeparator()
        
        self.menuitemExit = wx.MenuItem( self.menuFile, wx.ID_EXIT, u"Завершить"+ u"\t" + u"Ctrl+q", u"Завершить работу программы", wx.ITEM_NORMAL )
        self.menuFile.Append( self.menuitemExit )
        
        self.wxMenuBar.Append( self.menuFile, u"Файл" ) 
        
        self.menuService = wx.Menu()
        self.menuConfig = wx.MenuItem( self.menuService, wx.ID_ANY, u"Настройки", u"Настройки программы", wx.ITEM_NORMAL )
        self.menuService.Append( self.menuConfig )
        
        self.m_menu1 = wx.Menu()
        self.menuitemPurge = wx.MenuItem(self.m_menu1, wx.ID_ANY, u"Удалить подсистемы, помеченные как \"удаленные\"",
                                         u"Удаление неиспользуемых подсистем с компьютера", wx.ITEM_NORMAL)
        self.m_menu1.Append( self.menuitemPurge )
        
        self.menuitemCleanBuffer = wx.MenuItem( self.m_menu1, wx.ID_ANY, u"Очистить буфер", u"Очистить буфер", wx.ITEM_NORMAL )
        self.m_menu1.Append( self.menuitemCleanBuffer )
        
        self.menuService.AppendSubMenu( self.m_menu1, u"Очистка" )
        
        self.menuService.AppendSeparator()
        
        self.menuitemLinksUpdate = wx.MenuItem( self.menuService, wx.ID_ANY, u"Обновить ярлыки", u"Обновить ярлыки подсистем на рабочем столе", wx.ITEM_NORMAL )
        self.menuService.Append( self.menuitemLinksUpdate )
        
        self.btFull = wx.MenuItem( self.menuService, wx.ID_ANY, u"Полная обработка", u"Включить режим полной обработки файлов пакетов", wx.ITEM_CHECK )
        self.menuService.Append( self.btFull )
        
        self.wxMenuBar.Append( self.menuService, u"Сервис" ) 
        
        self.menuHelp = wx.Menu()
        self.menuitemManual = wx.MenuItem(self.menuHelp, wx.ID_ANY, u"Руководство" + u"\t" + u"F1",
                                          u"Открыть руководство по работе с программой", wx.ITEM_NORMAL)
        self.menuHelp.Append( self.menuitemManual )
        
        self.menuHelp.AppendSeparator()
        
        self.menuitemHelp = wx.MenuItem( self.menuHelp, wx.ID_ANY, u"О программе", u"Информация о программе", wx.ITEM_NORMAL )
        self.menuHelp.Append( self.menuitemHelp )
        
        self.wxMenuBar.Append( self.menuHelp, u"Помощь" ) 
        
        self.SetMenuBar( self.wxMenuBar )
        
        
        self.Centre( wx.BOTH )
        
        # Connect Events
        self.btRefresh.Bind( wx.EVT_BUTTON, self.on_refresh )
        self.wxPacketList.Bind( wx.EVT_ENTER_WINDOW, self.on_enter_package_list )
        self.wxInfoView.Bind(wx.EVT_ENTER_WINDOW, self.on_enter_view_info)
        self.wxLogView.Bind( wx.EVT_ENTER_WINDOW, self.on_enter_log_info )
        self.btUpdate.Bind( wx.EVT_BUTTON, self.on_update )
        self.Bind( wx.EVT_MENU, self.on_update, id = self.menuitemUpdate.GetId() )
        self.Bind( wx.EVT_MENU, self.on_menu_select_all, id = self.menuitem_select_all.GetId() )
        self.Bind( wx.EVT_MENU, self.on_menu_unselect_all, id = self.menuitem_unselect_all.GetId() )
        self.Bind( wx.EVT_MENU, self.on_exit, id = self.menuitemExit.GetId() )
        self.Bind( wx.EVT_MENU, self.on_config, id = self.menuConfig.GetId() )
        self.Bind( wx.EVT_MENU, self.on_purge, id = self.menuitemPurge.GetId() )
        self.Bind( wx.EVT_MENU, self.on_clean_buffer, id = self.menuitemCleanBuffer.GetId() )
        self.Bind( wx.EVT_MENU, self.on_links_update, id = self.menuitemLinksUpdate.GetId() )
        self.Bind( wx.EVT_MENU, self.on_btFull, id = self.btFull.GetId() )
        self.Bind(wx.EVT_MENU, self.on_help, id=self.menuitemManual.GetId())
        self.Bind( wx.EVT_MENU, self.on_about, id = self.menuitemHelp.GetId() )
    
    def __del__( self ):
        pass
    
    
    # Virtual event handlers, overide them in your derived class
    def on_refresh( self, event ):
        pass
    
    def on_enter_package_list( self, event ):
        pass

    def on_enter_view_info(self, event):
        pass
    
    def on_enter_log_info( self, event ):
        pass
    
    def on_update( self, event ):
        pass
    
    
    def on_menu_select_all( self, event ):
        pass
    
    def on_menu_unselect_all( self, event ):
        pass
    
    def on_exit( self, event ):
        pass
    
    def on_config( self, event ):
        pass
    
    def on_purge( self, event ):
        pass
    
    def on_clean_buffer( self, event ):
        pass
    
    def on_links_update( self, event ):
        pass
    
    def on_btFull( self, event ):
        pass

    def on_help(self, event):
        pass
    
    def on_about( self, event ):
        pass
    
    def sMainOnIdle( self, event ):
    	self.sMain.SetSashPosition( 291 )
    	self.sMain.Unbind( wx.EVT_IDLE )
    
    def m_splitter2OnIdle( self, event ):
    	self.m_splitter2.SetSashPosition( 0 )
    	self.m_splitter2.Unbind( wx.EVT_IDLE )
    

###########################################################################
## Class fmConfig
###########################################################################

class fmConfig ( wx.Frame ):
    
    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 800,377 ), style = wx.CAPTION|wx.CLOSE_BOX|wx.FRAME_FLOAT_ON_PARENT|wx.RESIZE_BORDER|wx.TAB_TRAVERSAL )
        
        self.SetSizeHints( wx.Size( -1,220 ), wx.DefaultSize )
        
        bSizer31 = wx.BoxSizer( wx.VERTICAL )
        
        bSizer31.SetMinSize( wx.Size( 500,-1 ) ) 
        self.m_panel15 = wx.Panel( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bSizer34 = wx.BoxSizer( wx.VERTICAL )
        
        fgSizer1 = wx.FlexGridSizer( 0, 2, 0, 0 )
        fgSizer1.AddGrowableCol( 0 )
        fgSizer1.SetFlexibleDirection( wx.HORIZONTAL )
        fgSizer1.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_ALL )
        
        self.m_staticText4 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Путь установки подсистем:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText4.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText4, 0, wx.ALL, 5 )
        
        self.wxEiisInstallPath = wx.DirPickerCtrl( self.m_panel15, wx.ID_ANY, wx.EmptyString, u"Выберите директорию для установки подсистем", wx.DefaultPosition, wx.DefaultSize, wx.DIRP_DEFAULT_STYLE|wx.DIRP_SMALL )
        self.wxEiisInstallPath.SetToolTip( u"Директория для установки подсистем" )
        
        fgSizer1.Add( self.wxEiisInstallPath, 0, wx.ALL|wx.EXPAND, 5 )
        
        self.m_staticText61 = wx.StaticText( self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText61.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText61, 0, wx.ALL, 5 )
        
        self.wxInstallToUserProfile = wx.CheckBox( self.m_panel15, wx.ID_ANY, u"устанавливать в профиль пользователя", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.wxInstallToUserProfile.SetValue(True) 
        self.wxInstallToUserProfile.SetToolTip( u"Выберите, если требуется установка в профиль пользователя. \nНапример, при отсутствии прав на установку в папку Program Files\n" )
        
        fgSizer1.Add( self.wxInstallToUserProfile, 0, wx.ALL, 5 )
        
        self.wxStaticText1 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Путь к репозиторию:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.wxStaticText1.Wrap( -1 )
        
        fgSizer1.Add( self.wxStaticText1, 0, wx.ALL, 5 )
        
        self.wxRepoPath = wx.TextCtrl( self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 500,-1 ), 0 )
        self.wxRepoPath.SetMaxLength( 256 ) 
        self.wxRepoPath.SetToolTip( u"Путь к репозиторию " )
        
        fgSizer1.Add( self.wxRepoPath, 0, wx.ALL|wx.EXPAND, 5 )
        
        self.m_staticText3 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Количество потоков загрузки:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText3.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText3, 0, wx.ALL, 5 )
        
        wxThreadsCountChoices = [ u"1", u"2", u"3", u"4", u"5" ]
        self.wxThreadsCount = wx.Choice( self.m_panel15, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wxThreadsCountChoices, 0 )
        self.wxThreadsCount.SetSelection( 0 )
        self.wxThreadsCount.SetToolTip( u"Количество потоков загрузки.\n\nВ некоторых случаях увеличение количества потоков уменьшает время загрузки файлов с сервера.\nУстанавливается опытным путем." )
        
        fgSizer1.Add( self.wxThreadsCount, 0, wx.ALL, 5 )
        
        self.m_staticText6 = wx.StaticText( self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText6.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText6, 0, wx.ALL, 5 )
        
        self.wxPurgePackets = wx.CheckBox( self.m_panel15, wx.ID_ANY, u"Удалять файлы подсистем с диска, при удалении пакета", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.wxPurgePackets.SetToolTip( u"Для сокращения объема закачиваемых файлов из репозитория можно оставлять локально файлы подсистем, при деактивации пакетов подсистем. В дальнейшем будут скачиваться только новые файлы." )
        
        fgSizer1.Add( self.wxPurgePackets, 0, wx.ALL, 5 )
        
        self.m_staticText7 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Кодировка", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText7.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText7, 0, wx.ALL, 5 )

        self.wxEncode = wx.TextCtrl(self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0)
        self.wxEncode.SetToolTip( u"Кодировка симвлолв в файлах, используемых программой.\n\nПо-умолчанию UTF-8" )
        
        fgSizer1.Add( self.wxEncode, 0, wx.ALL|wx.EXPAND, 5 )
        
        self.m_staticText8 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Кодировка FTP-сервера", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText8.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText8, 0, wx.ALL, 5 )
        
        self.wxFTPEncode = wx.TextCtrl( self.m_panel15, wx.ID_ANY, u"UTF-8", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.wxFTPEncode.SetToolTip( u"Кодировка символов сервера репозитория.\n\nПри возникновении ошибки в разпознавании имен файлов на сервере программой, установить кодировку символов, используемую сервером" )
        
        fgSizer1.Add( self.wxFTPEncode, 0, wx.ALL|wx.EXPAND, 5 )
        
        
        bSizer34.Add( fgSizer1, 0, wx.EXPAND, 5 )
        
        
        bSizer34.Add( ( 0, 0), 1, wx.EXPAND, 5 )
        
        sd = wx.StdDialogButtonSizer()
        self.sdApply = wx.Button( self.m_panel15, wx.ID_APPLY )
        sd.AddButton( self.sdApply )
        self.sdCancel = wx.Button( self.m_panel15, wx.ID_CANCEL )
        sd.AddButton( self.sdCancel )
        sd.Realize();
        
        bSizer34.Add( sd, 0, wx.EXPAND|wx.BOTTOM|wx.RIGHT, 5 )
        
        
        self.m_panel15.SetSizer( bSizer34 )
        self.m_panel15.Layout()
        bSizer34.Fit( self.m_panel15 )
        bSizer31.Add( self.m_panel15, 1, wx.EXPAND, 5 )
        
        
        self.SetSizer( bSizer31 )
        self.Layout()
        
        self.Centre( wx.BOTH )
        
        # Connect Events
        self.wxInstallToUserProfile.Bind( wx.EVT_CHECKBOX, self.on_eiis_path_click )
        self.sdApply.Bind( wx.EVT_BUTTON, self.Apply )
        self.sdCancel.Bind( wx.EVT_BUTTON, self.Cancel )
    
    def __del__( self ):
        pass
    
    
    # Virtual event handlers, overide them in your derived class
    def on_eiis_path_click( self, event ):
        pass
    
    def Apply( self, event ):
        pass
    
    def Cancel( self, event ):
        pass
    

