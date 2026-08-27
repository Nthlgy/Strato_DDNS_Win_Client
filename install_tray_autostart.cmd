@echo off
setlocal
cd /d "%~dp0"
if not exist "ddns-tray.exe" (
  echo ddns-tray.exe fehlt. Bitte zuerst build_exe.cmd ausfuehren.
  exit /b 1
)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Strato-DDNS-Tray" /t REG_SZ /d ^"%~dp0ddns-tray.exe^" /f
start "" "%~dp0ddns-tray.exe"
endlocal
