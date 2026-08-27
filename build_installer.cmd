@echo off
setlocal
cd /d "%~dp0"

call build_exe.cmd
if errorlevel 1 exit /b %errorlevel%

if not exist "WinSW.exe" (
  echo WinSW.exe fehlt. Bitte die passende WinSW-Datei neben dieses Skript legen.
  exit /b 1
)

where ISCC.exe >nul 2>&1
if errorlevel 1 (
  echo ISCC.exe fehlt. Bitte Inno Setup installieren und ISCC.exe zum PATH hinzufuegen.
  exit /b 1
)

ISCC.exe installer\Strato_DDNS_Win_Client.iss
set "exit_code=%errorlevel%"
endlocal & exit /b %exit_code%
