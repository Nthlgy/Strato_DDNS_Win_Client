@echo off
setlocal
cd /d "%~dp0"
if not exist "WinSW.exe" (
  echo WinSW.exe fehlt. Bitte WinSW herunterladen und neben diese Datei legen.
  exit /b 1
)
if not exist "ddns.exe" (
  echo ddns.exe fehlt. Bitte zuerst build_exe.cmd ausfuehren.
  exit /b 1
)
copy /y "DDNS.xml" "WinSW.xml" >nul
WinSW.exe install
WinSW.exe start
endlocal
