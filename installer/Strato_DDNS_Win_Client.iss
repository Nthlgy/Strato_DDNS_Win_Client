#define MyAppName "Strato DDNS Windows Client"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Strato DDNS"
#define MyAppExeName "ddns.exe"

[Setup]
AppId={{A6B7813C-9D5B-4C62-BF78-7B4A98D4F4DF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Strato-DDNS
DefaultGroupName={#MyAppName}
UninstallDisplayName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=Strato_DDNS_Win_Client
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Files]
Source: "..\ddns.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ddns-tray.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\WinSW.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\DDNS.xml"; DestDir: "{app}"; DestName: "WinSW.xml"; Flags: ignoreversion
Source: "..\config.example.ini"; DestDir: "{app}"; DestName: "config.ini"; Permissions: users-modify; Flags: onlyifdoesntexist

[Dirs]
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\state"; Permissions: users-modify

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Strato-DDNS-Tray"; ValueData: "{app}\ddns-tray.exe"; Flags: uninsdeletevalue

[Run]
Filename: "{sys}\icacls.exe"; Parameters: """{app}\config.ini"" /grant *S-1-5-32-545:M"; WorkingDir: "{app}"; StatusMsg: "Schreibrechte für die Konfiguration werden gesetzt..."; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{app}\logs"" /grant *S-1-5-32-545:(OI)(CI)M"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{sys}\icacls.exe"; Parameters: """{app}\state"" /grant *S-1-5-32-545:(OI)(CI)M"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{app}\WinSW.exe"; Parameters: "install"; WorkingDir: "{app}"; StatusMsg: "DDNS-Dienst wird installiert..."; Flags: runhidden waituntilterminated
Filename: "{sys}\sc.exe"; Parameters: "sdset Strato-DDNS ""D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)(A;;RPWPDT;;;BU)(A;;CCLCSWLOCRRC;;;AU)"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{app}\ddns-tray.exe"; WorkingDir: "{app}"; Description: "Tray-Symbol starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM ddns-tray.exe /F"; RunOnceId: "StopStratoDdnsTray"; Flags: runhidden waituntilterminated
Filename: "{app}\WinSW.exe"; Parameters: "stop"; WorkingDir: "{app}"; RunOnceId: "StopStratoDdnsService"; Flags: runhidden waituntilterminated
Filename: "{app}\WinSW.exe"; Parameters: "uninstall"; WorkingDir: "{app}"; RunOnceId: "UninstallStratoDdnsService"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\state"
Type: files; Name: "{app}\config.ini"
Type: files; Name: "{app}\WinSW.xml"
Type: files; Name: "{app}\WinSW.err.log"
Type: files; Name: "{app}\WinSW.out.log"
Type: files; Name: "{app}\WinSW.wrapper.log"
