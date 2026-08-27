@echo off
setlocal
cd /d "%~dp0"
if not exist "WinSW.exe" (
  echo WinSW.exe fehlt.
  exit /b 1
)
WinSW.exe stop
WinSW.exe uninstall
del /q "WinSW.xml" 2>nul
endlocal
