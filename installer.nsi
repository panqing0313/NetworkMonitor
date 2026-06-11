; Network Monitor Windows Installer
; NSIS (Nullsoft Scriptable Install System)

!define PRODUCT_NAME "Network Monitor"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "local"
!define PRODUCT_WEB_SITE "https://github.com/panqing0313/NetworkMonitor"

SetCompressor lzma
RequestExecutionLevel admin

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Network_Monitor_v1.0_Setup.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "Software\${PRODUCT_NAME}" ""

; Modern UI
!include "MUI2.nsh"
!include "FileFunc.nsh"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy all files from build output
    File /r "dist\Network Monitor\*.*"

    ; Create Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\Network Monitor.exe" "" "$INSTDIR\_internal\resources\icon.icns" 0
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" \
        "$INSTDIR\uninst.exe"

    ; Desktop shortcut
    CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" \
        "$INSTDIR\Network Monitor.exe"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"

    ; Registry for Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "NoRepair" 1
SectionEnd

Section "Uninstall"
    ; Remove files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

    ; Remove registry
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
