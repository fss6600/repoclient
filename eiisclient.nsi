# -*- coding: windows-1251 -*-
; example2.nsi
;
; This script is based on example1.nsi, but it remember the directory,
; has uninstall support and (optionally) installs start menu shortcuts.
;
; It will install example2.nsi into a directory that the user selects.
;
; See install-shared.nsi for a more robust way of checking for administrator rights.
; See install-per-user.nsi for a file association example.

;--------------------------------
XPStyle on
!define VERSION $%CLIENTVER%

; The name of the installer
Name '"Обновление ЕИИС Соцстрах. Клиент. ${VERSION}"'

; The file to write
OutFile "dist\clientup-${VERSION}-x86.exe"
Icon "eiisclient\gui\ico\update-96.ico"

; Request application privileges for Windows Vista and higher
RequestExecutionLevel user ;admin

; Build Unicode installer
Unicode True
LoadLanguageFile "${NSISDIR}\Contrib\Language files\Russian.nlf"


; The default installation directory
InstallDir "$LocalAppData\Клиент обновления ЕИИС Соцстрах"

; Registry key to check for directory (so if you install again, it will
; overwrite the old one automatically)
;InstallDirRegKey HKLM "Software\NSIS_Example2" "Install_Dir"

;--------------------------------
; Pages

Page license
PageEx custom
   Caption "Readme"
   ;SubCaption "TExt"
PageExEnd
Page directory
Page instfiles

BrandingText "Филиал №2 ГУ СРО ФСС РФ | 2020"

;--------------------------------
LicenseText "Условия использования программы"
LicenseData "license.txt"

DirText "Программа установит ${NAME} версии ${VERSION} по указанному пути" "Путь установки (по-умолчанию в профиль пользователя)"

Section "Custom"

SectionEnd



; The stuff to install
Section ""

  SectionIn RO

  ; Set output path to the installation directory.
  SetOutPath $INSTDIR
  RMDir /r $INSTDIR
  CreateDirectory $INSTDIR
  ; Put file there
  File /r dist\eiisclient\docs
  File /r dist\eiisclient\Include
  File /r dist\eiisclient\lib2to3
  File /r dist\eiisclient\win32com
  File /r dist\eiisclient\wx
  File dist\eiisclient\*.*
;  File /x dist\eiisclient\_asyncio.pyd
;  File /x dist\eiisclient\_decimal.pyd
;  File /x dist\eiisclient\_multiprocessing.pyd


SectionEnd

; Optional section (can be disabled by the user)
Section "Shortcuts"

;  CreateDirectory "$SMPROGRAMS\Обновление ЕИИС"
;  CreateShortcut "$SMPROGRAMS\Example2\Uninstall.lnk" "$INSTDIR\uninstall.exe"
;  CreateShortcut "$SMPROGRAMS\Обновление ЕИИС\Обновление ЕИИС.lnk" "$INSTDIR\eiisclient.exe"
  CreateShortcut "$DESKTOP\Обновление ЕИИС.lnk" "$INSTDIR\eiisclient.exe"

SectionEnd


