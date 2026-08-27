# Strato-DDNS

Ein Windows-Programm, das eine Strato-Domain mit der öffentlichen IP-Adresse
abgleicht. Ohne CLI-Parameter läuft `ddns.exe` dauerhaft und ist für WinSW als
Windows-Service ausgelegt.

## Voraussetzungen

- Windows
- Python 3.11 oder neuer (nur zum Bauen aus dem Quellcode)
- Für den Service-Build: [WinSW](https://github.com/winsw/winsw/releases), als
  `WinSW.exe` in diesem Projektverzeichnis

Zur Laufzeit ist ausschließlich `requests` eine externe Python-Bibliothek.
`PyInstaller` wird nur von `build_exe.cmd` zum Erzeugen der EXE installiert.

## Entwicklung und Installer-Build

Für die Entwicklung kann `build_exe.cmd` die beiden Einzeldateien
`ddns.exe` und `ddns-tray.exe` erzeugen.

Für die eigentliche Installationsdatei:

1. Inno Setup installieren und `ISCC.exe` zum `PATH` hinzufügen.
2. Die passende WinSW-Datei als `WinSW.exe` neben `build_installer.cmd` legen.
3. `build_installer.cmd` ausführen.

Das Ergebnis ist `dist\Strato_DDNS_Win_Client.exe`. Der Installer kopiert die
beiden Programme, WinSW und die Dienstdefinition nach
`%ProgramFiles%\Strato-DDNS`, legt eine neue `config.ini` aus
`config.example.ini` an und erzeugt die Verzeichnisse `logs` und `state`.
Die Konfiguration wird nicht überschrieben, wenn der Installer aktualisiert
wird. Der Installer gewährt dem angemeldeten Benutzer Schreibrechte auf
`config.ini`, `logs` und `state`, obwohl die Programme unter `%ProgramFiles%`
liegen. Der Dienst wird registriert, aber nicht automatisch gestartet, damit
die Konfiguration vor dem ersten Lauf angepasst werden kann. Das Tray-Symbol
wird für den aktuellen Benutzer in den Autostart aufgenommen und direkt
gestartet.

Die rechte Maustaste auf dem Tray-Symbol bietet die Einträge `Dienst starten`
und `Dienst beenden`. Das Tray-Symbol bleibt dabei immer aktiv; bei einem
inaktiven Dienst wird ein neutrales Symbol angezeigt.
Die Deinstallation in den Windows-Einstellungen stoppt und entfernt den
Dienst, entfernt Tray-Autostart und löscht Konfiguration, Logs und Statusdaten.

## Einrichtung

1. `config.ini` ausfüllen. Der Benutzername und das Passwort sind die in
   Strato für Dynamic DNS eingerichteten Zugangsdaten; sie stehen nie im Code.
   Für weitere Domains mit denselben Zugangsdaten `hostname_2` und optional
   `hostname_3` ausfüllen. Alle eingetragenen Hostnamen werden mit derselben
   öffentlichen IP in einem Strato-Update aktualisiert.
2. Optional SMTP in `[mail]` aktivieren. Bei `enabled = false` werden keine
   Mails versendet.
3. Bei einer Installation mit `Strato_DDNS_Win_Client.exe` den Dienst über das
  Tray-Symbol mit `Dienst starten` starten.

Für die manuelle Entwicklung bleiben `install_service.cmd` und
`install_tray_autostart.cmd` verfügbar. Das erste Skript erstellt aus
`DDNS.xml` die von WinSW erwartete Laufzeitdatei `WinSW.xml`.

Zum Entfernen den Dienst als Administrator mit `uninstall_service.cmd`
deinstallieren.

## Tray-Icons anpassen

Die editierbaren Icon-Quellen liegen in `assets`:

- `ddns-neutral.png` für den inaktiven Dienst
- `ddns-healthy.png` für einen gesunden laufenden Dienst
- `ddns-fail.png` für einen laufenden Dienst mit Fehler

Nach Änderungen die ICO-Dateien mit `py -3 tools\generate_icons.py` neu erzeugen
und anschließend `build_exe.cmd` ausführen.

## CLI

```
ddns.exe --test     :: prüft IP-Ermittlung und aktualisiert nur bei Änderung
ddns.exe --force    :: erzwingt einen Strato-Update
ddns.exe --status   :: zeigt die zuletzt erfolgreich gespeicherten IPs
ddns.exe --mail-test :: versendet eine SMTP-Testnachricht
```

Ohne Parameter wird sofort ein Zyklus ausgeführt und danach alle 300 Sekunden
(oder nach `interval_seconds`) geprüft.

## Verhalten und Dateien

- IPv4 wird über api.ipify.org, ipv4.icanhazip.com und checkip.amazonaws.com
  mit Retry und Timeout abgefragt. IPv6 ist über `update_ipv6 = true` optional.
- Strato wird nur bei neuer IP kontaktiert, außer bei `--force`. Bei aktivem
  IPv6 werden IPv4 und IPv6 zusammen in einem Strato-konformen Update gesendet;
  dies gilt zugleich für alle konfigurierten Hostnamen.
- `good` und `nochg` gelten als Erfolg. Antworten wie `badauth`, `nohost`,
  `notfqdn`, `911` und unbekannte Antworten erzeugen einen Fehler.
- `state/last_ip.txt` hält die zuletzt bestätigten Adressen.
- `state/error.flag` verhindert mehr als eine Fehlermail während desselben
  Fehlerzustands und wird bei erfolgreicher Wiederherstellung entfernt.
- `logs/ddns.log` wird automatisch rotiert (2 MiB, fünf Sicherungen).

Die Verzeichnisse `logs` und `state` werden beim ersten Programmstart erstellt.

## Statussymbol im Infobereich

`ddns-tray.exe` ist eine separate Benutzer-App für den Windows-Infobereich
(unten rechts). Der Windows-Dienst selbst darf kein Taskleistensymbol erzeugen.
Die Tray-App liest `state/status.json`, das der Dienst in jedem Prüfzyklus
aktualisiert:

- Grüner Haken: Dienst ist aktuell und der letzte DDNS-Abgleich war erfolgreich.
- Rotes Kreuz: Dienst läuft, aber der letzte Abgleich ist fehlgeschlagen oder
  der Heartbeat ist veraltet.
- Graues Symbol: Dienst ist nicht aktiv.
- Linksklick: Status anzeigen. Rechtsklick: Dienst starten oder beenden.

Nach `build_exe.cmd` startet `install_tray_autostart.cmd` die Tray-App sofort
und richtet sie für die aktuelle Windows-Anmeldung im Autostart ein. Zum
Entfernen dient `uninstall_tray_autostart.cmd`. Der Windows-Dienst und die
Tray-App müssen im selben Installationsordner liegen.
