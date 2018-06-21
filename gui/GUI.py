# -*- coding: utf-8 -*- 

###########################################################################
## Python code generated with wxFormBuilder (version Jun 11 2018)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
import wx.richtext

ID_ANY = 1000

###########################################################################
## Class FrameMain
###########################################################################

class FrameMain ( wx.Frame ):
    
    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"Обновление ЕИИС Соцстрах", pos = wx.DefaultPosition, size = wx.Size( 800,600 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )
        
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
        self.m_staticText1 = wx.StaticText( self.pLeft, wx.ID_ANY, u"Пакеты подсистем:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText1.Wrap( -1 )
        
        self.m_staticText1.SetToolTip( u"Для установки/удаления поставьте/снимите галку" )
        
        bSizer26.Add( self.m_staticText1, 0, wx.ALL, 5 )
        
        m_checkList4Choices = [u"Choice 1", u"Choice 2", u"Choice 3", u"Choice 4", u"Choice 5"]
        self.m_checkList4 = wx.CheckListBox( self.pLeft, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, m_checkList4Choices, 0 )
        self.m_checkList4.SetMinSize( wx.Size( 200,-1 ) )
        
        bSizer26.Add( self.m_checkList4, 1, wx.ALL|wx.EXPAND, 5 )
        
        bSizer28 = wx.BoxSizer( wx.HORIZONTAL )
        
        self.btUpdate = wx.Button( self.pLeft, wx.ID_ANY, u"Обновить", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.btUpdate.SetDefault()
        
        self.btUpdate.SetToolTip( u"Обновить/установить подсистемы" )
        
        bSizer28.Add( self.btUpdate, 1, wx.ALL, 5 )
        
        
        bSizer26.Add( bSizer28, 0, wx.EXPAND|wx.ALIGN_RIGHT, 5 )
        
        
        self.pLeft.SetSizer( bSizer26 )
        self.pLeft.Layout()
        bSizer26.Fit( self.pLeft )
        self.pRight = wx.Panel( self.sMain, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        self.pRight.SetMinSize( wx.Size( 200,-1 ) )
        
        bSizer27 = wx.BoxSizer( wx.VERTICAL )
        
        self.m_richText6 = wx.richtext.RichTextCtrl( self.pRight, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_READONLY|wx.VSCROLL|wx.HSCROLL|wx.NO_BORDER|wx.WANTS_CHARS )
        bSizer27.Add( self.m_richText6, 1, wx.EXPAND |wx.ALL, 5 )
        
        
        self.pRight.SetSizer( bSizer27 )
        self.pRight.Layout()
        bSizer27.Fit( self.pRight )
        self.sMain.SplitVertically( self.pLeft, self.pRight, 291 )
        bSizer21.Add( self.sMain, 1, wx.EXPAND, 5 )
        
        
        self.SetSizer( bSizer21 )
        self.Layout()
        self.statusBar = self.CreateStatusBar( 1, wx.STB_SIZEGRIP, wx.ID_ANY )
        self.m_menubar1 = wx.MenuBar( 0 )
        self.mFile = wx.Menu()
        self.menuitemUpdate = wx.MenuItem( self.mFile, ID_ANY, u"Обновить"+ u"\t" + u"F5", u"Обновить пакеты", wx.ITEM_NORMAL )
        self.mFile.Append( self.menuitemUpdate )
        
        self.mFile.AppendSeparator()
        
        self.menuitemExit = wx.MenuItem( self.mFile, wx.ID_EXIT, u"Завершить"+ u"\t" + u"Ctrl+q", u"Завершить работу программы", wx.ITEM_NORMAL )
        self.mFile.Append( self.menuitemExit )
        
        self.m_menubar1.Append( self.mFile, u"Файл" ) 
        
        self.mService = wx.Menu()
        self.mConfig = wx.MenuItem( self.mService, wx.ID_ANY, u"Настройки", wx.EmptyString, wx.ITEM_NORMAL )
        self.mService.Append( self.mConfig )
        
        self.mService.AppendSeparator()
        
        self.mLinksUpdate = wx.MenuItem( self.mService, wx.ID_ANY, u"Обновить ярлыки", wx.EmptyString, wx.ITEM_NORMAL )
        self.mService.Append( self.mLinksUpdate )
        
        self.m_menubar1.Append( self.mService, u"Сервис" ) 
        
        self.mHelp = wx.Menu()
        self.mAbout = wx.MenuItem( self.mHelp, wx.ID_ABOUT, u"О программе"+ u"\t" + u"F1", u"Информация о программе", wx.ITEM_NORMAL )
        self.mHelp.Append( self.mAbout )
        
        self.m_menubar1.Append( self.mHelp, u"Помощь" ) 
        
        self.SetMenuBar( self.m_menubar1 )
        
        
        self.Centre( wx.BOTH )
        
        # Connect Events
        self.Bind( wx.EVT_ACTIVATE, self.init )
        self.btUpdate.Bind( wx.EVT_BUTTON, self.on_update )
        self.Bind( wx.EVT_MENU, self.on_update, id = self.menuitemUpdate.GetId() )
        self.Bind( wx.EVT_MENU, self.on_exit, id = self.menuitemExit.GetId() )
        self.Bind( wx.EVT_MENU, self.on_config, id = self.mConfig.GetId() )
        self.Bind( wx.EVT_MENU, self.LinksUpdate, id = self.mLinksUpdate.GetId() )
        self.Bind( wx.EVT_MENU, self.on_about, id = self.mAbout.GetId() )
    
    def __del__( self ):
        pass
    
    
    # Virtual event handlers, overide them in your derived class
    def init( self, event ):
        pass
    
    def on_update( self, event ):
        pass
    
    
    def on_exit( self, event ):
        pass
    
    def on_config( self, event ):
        pass
    
    def LinksUpdate( self, event ):
        pass
    
    def on_about( self, event ):
        pass
    
    def sMainOnIdle( self, event ):
    	self.sMain.SetSashPosition( 291 )
    	self.sMain.Unbind( wx.EVT_IDLE )
    

###########################################################################
## Class FrameConfig
###########################################################################

class FrameConfig ( wx.Frame ):
    
    def __init__( self, parent ):
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 800,155 ), style = wx.CAPTION|wx.CLOSE_BOX|wx.FRAME_FLOAT_ON_PARENT|wx.RESIZE_BORDER|wx.TAB_TRAVERSAL )
        
        self.SetSizeHints( wx.Size( -1,-1 ), wx.DefaultSize )
        
        bSizer31 = wx.BoxSizer( wx.VERTICAL )
        
        bSizer31.SetMinSize( wx.Size( 500,-1 ) ) 
        self.m_panel15 = wx.Panel( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        bSizer34 = wx.BoxSizer( wx.VERTICAL )
        
        fgSizer1 = wx.FlexGridSizer( 0, 2, 0, 0 )
        fgSizer1.AddGrowableCol( 0 )
        fgSizer1.SetFlexibleDirection( wx.HORIZONTAL )
        fgSizer1.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_ALL )
        
        self.RepoPath = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Путь к репозиторию:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.RepoPath.Wrap( -1 )
        
        fgSizer1.Add( self.RepoPath, 0, wx.ALL, 5 )
        
        self.m_textCtrl19 = wx.TextCtrl( self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 500,-1 ), 0 )
        self.m_textCtrl19.SetToolTip( u"Путь к репозиторию " )
        
        fgSizer1.Add( self.m_textCtrl19, 0, wx.ALL|wx.EXPAND, 5 )
        
        self.m_staticText24 = wx.StaticText( self.m_panel15, wx.ID_ANY, u"Путь к рабочей директории программы:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText24.Wrap( -1 )
        
        fgSizer1.Add( self.m_staticText24, 0, wx.ALL, 5 )
        
        self.WorkDir = wx.TextCtrl( self.m_panel15, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        self.WorkDir.SetToolTip( u"Путь к рабочей папке программы" )
        
        fgSizer1.Add( self.WorkDir, 0, wx.ALL|wx.EXPAND, 5 )
        
        
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
        self.sdApply.Bind( wx.EVT_BUTTON, self.Apply )
        self.sdCancel.Bind( wx.EVT_BUTTON, self.Cancel )
    
    def __del__( self ):
        pass
    
    
    # Virtual event handlers, overide them in your derived class
    def Apply( self, event ):
        pass
    
    def Cancel( self, event ):
        pass
    

