@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --onefile --version-file version_info.txt --name ddns --paths . src\main.py
py -3 -m PyInstaller --onefile --noconsole --version-file version_info.txt --add-data "assets;assets" --name ddns-tray --paths . src\tray.py
copy /y "dist\ddns.exe" "ddns.exe"
copy /y "dist\ddns-tray.exe" "ddns-tray.exe"
endlocal
