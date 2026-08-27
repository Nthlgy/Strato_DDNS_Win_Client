@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --onefile --name ddns --paths . src\main.py
py -3 -m PyInstaller --onefile --noconsole --add-data "assets;assets" --name ddns-tray --paths . src\tray.py
copy /y "dist\ddns.exe" "ddns.exe"
copy /y "dist\ddns-tray.exe" "ddns-tray.exe"
endlocal
