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
!define VERSION $%CLIENTVER%
!include "MUI2.nsh"
!include "WinVer.nsh"

; The name of the installer
  Name '"Обновление ЕИИС Соцстрах. Клиент"'

  VIProductVersion "${VERSION}"
  VIAddVersionKey "ProductName" "Обновление ЕИИС Соцстрах. Клиент"
  VIAddVersionKey "Comments" "Программа для установки, обновления и удаления подсистем ЕИИС 'Соцстрах'"
  VIAddVersionKey "CompanyName" "Филиал №2 ГУ СРО ФСС РФ"
  VIAddVersionKey "LegalCopyright" "Михаил Петров <mb.petrov@ro66.fss.ru>"
  VIAddVersionKey "FileDescription" "Обновление ЕИИС Соцстрах. Клиент"
  VIAddVersionKey "FileVersion" "${VERSION}"

; The file to write
OutFile "dist\clientup-${VERSION}-x86.exe"
;Icon "eiisclient\gui\ico\update-96.ico"

; Request application privileges for Windows Vista and higher
RequestExecutionLevel user

;--------------------------------
;Interface Settings

!define MUI_ABORTWARNING
!define MUI_ICON "gui\img\update-96.ico"
Unicode True
BrandingText "Филиал №2 ГУ СРО ФСС РФ | 2020"
ShowInstDetails show

; The default installation directory
;InstallDir "$LOCALAPPDATA\Клиент обновления ЕИИС Соцстрах"
InstallDir "$LOCALAPPDATA\Клиент обновления ЕИИС Соцстрах"

; Registry key to check for directory (so if you install again, it will
; overwrite the old one automatically)
;InstallDirRegKey HKLM "Software\NSIS_Example2" "Install_Dir"



;--------------------------------
; Pages
    !define MUI_TEXT_WELCOME_INFO_TITLE "$(^Name)"
    !define MUI_TEXT_WELCOME_INFO_TEXT "Программа установит '$(^Name)' - ${VERSION}"
    ;!define MUI_COMPONENTSPAGE_NODESC
    !define MUI_COMPONENTSPAGE_SMALLDESC

    !insertmacro MUI_PAGE_WELCOME
    !insertmacro MUI_PAGE_LICENSE "license.txt"
    !insertmacro MUI_PAGE_COMPONENTS
    !insertmacro MUI_PAGE_DIRECTORY
    !insertmacro MUI_PAGE_INSTFILES
    !insertmacro MUI_PAGE_FINISH

    !insertmacro MUI_UNPAGE_WELCOME
    !insertmacro MUI_UNPAGE_CONFIRM
    !insertmacro MUI_UNPAGE_INSTFILES
    !insertmacro MUI_UNPAGE_FINISH


    !insertmacro MUI_LANGUAGE "Russian"

;--------------------------------
;LicenseText "Условия использования программы"
;LicenseData "license.txt"

; The stuff to install
Section "Основные файлы программы"
  ;!define MUI_INNERTEXT_COMPONENTS_DESCRIPTION_INFO "Установка файлов программы"
  SectionIn RO
  ; Set output path to the installation directory.
  SetOutPath $INSTDIR
  RMDir /r $INSTDIR
  CreateDirectory $INSTDIR
  ; Put file there
  File /r dist\W7\eiisclient\docs
  File /r dist\W7\eiisclient\Include
  File /r dist\W7\eiisclient\lib2to3
  File /r dist\W7\eiisclient\win32com
  File /r dist\W7\eiisclient\wx
  File dist\W7\eiisclient\*.*

  ;Store installation folder
;  WriteRegStr HKCU "Software\Обновление ЕИИС. Клиент" "" $INSTDIR

  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"


SectionEnd

; Optional section (can be disabled by the user)
SectionGroup /e "Создать ярлыки"
Section "на рабочем столе" "Создать ярлыки программы на рабочем столе и в меню приложений"
  ;!undef MUI_INNERTEXT_COMPONENTS_DESCRIPTION_INFO
  ;!define MUI_INNERTEXT_COMPONENTS_DESCRIPTION_INFO "установка ярлыка на рабочий стол"
  CreateShortcut "$DESKTOP\Обновление ЕИИС.lnk" "$INSTDIR\eiisclient.exe"
SectionEnd
Section "в меню приложений"
  ;!undef MUI_INNERTEXT_COMPONENTS_DESCRIPTION_INFO
  ;!define MUI_INNERTEXT_COMPONENTS_DESCRIPTION_INFO "установка ярлыков запуска и удаления программы в меню программ"
  CreateDirectory "$SMPROGRAMS\Обновление ЕИИС"
  CreateShortcut "$SMPROGRAMS\Обновление ЕИИС\Обновление ЕИИС. Клиент.lnk" "$INSTDIR\eiisclient.exe"
  CreateShortcut "$SMPROGRAMS\Обновление ЕИИС\Удаление программы.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd
SectionGroupEnd

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\Обновление ЕИИС\Обновление ЕИИС. Клиент.lnk"
  Delete "$SMPROGRAMS\Обновление ЕИИС\Удаление программы.lnk"
  RMDir /r "$SMPROGRAMS\Обновление ЕИИС"
  Delete "$DESKTOP\Обновление ЕИИС.lnk"
SectionEnd

Function .onInit
    ${IfNot} ${AtLeastWin7}
        MessageBox MB_OK "Требуется Windows 7 и выше"
        Quit
    ${EndIf}
FunctionEnd
