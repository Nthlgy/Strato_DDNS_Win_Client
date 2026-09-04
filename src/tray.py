"""Native Windows notification-area indicator for the Strato-DDNS service."""

from __future__ import annotations

import ctypes
import configparser
import json
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONUP = 0x0202
WM_APP = 0x8000
TRAY_MESSAGE = WM_APP + 1
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NOTIFYICON_VERSION_4 = 4
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
TIMER_ID = 1
TIMER_INTERVAL_MS = 10_000
GUI_REFRESH_MS = 2_000

user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
    ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.LoadImageW.restype = wintypes.HANDLE


class WNDCLASSEXW(ctypes.Structure):
    """Windows class registration data for the hidden tray message window."""

    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HANDLE),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    """Notification-area icon data passed to Shell_NotifyIconW."""

    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


def application_directory() -> Path:
    """Return the directory beside the tray executable or the project root."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def asset_directory() -> Path:
    """Return the bundled icon directory in source and frozen builds."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "assets"
    return application_directory() / "assets"


def read_service_status(status_file: Path) -> tuple[bool, str]:
    """Return health and a compact tooltip based on the published service state."""
    try:
        status = json.loads(status_file.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(str(status["heartbeat_at"]))
        elapsed = (datetime.now(timezone.utc) - timestamp).total_seconds()
        stale_after = int(status.get("stale_after_seconds", 600))
        healthy = bool(status.get("healthy")) and elapsed <= stale_after
        addresses = status.get("addresses", {})
        address_text = ", ".join(
            f"{family}: {address}" for family, address in sorted(addresses.items())
        )
        message = str(status.get("message", "No status message."))
        if elapsed > stale_after:
            message = "Service heartbeat is stale or the service is stopped."
        details = address_text or message
        return healthy, f"Strato-DDNS: {details}"[:127]
    except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return False, "Strato-DDNS: No current service status available."


def create_status_icon(healthy: bool, running: bool) -> wintypes.HANDLE:
    """Load the high-resolution icon matching the current service state."""
    name = "healthy" if healthy and running else "fail" if running else "neutral"
    icon_path = asset_directory() / f"ddns-{name}.ico"
    return user32.LoadImageW(None, str(icon_path), 1, 0, 0, 0x00000010 | 0x00000040)


class TrayApplication:
    """Own the hidden window, icon and timer."""

    def __init__(self) -> None:
        self.status_file = application_directory() / "state" / "status.json"
        self.class_name = "StratoDdnsTrayWindow"
        self.icon: wintypes.HANDLE | None = None
        self.healthy: bool | None = None
        self.running: bool | None = None
        self.tooltip = "Strato-DDNS: Loading service status..."
        self.window: wintypes.HWND | None = None
        self.config_window_open = False
        self.window_procedure = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )(self._window_procedure)

    def _notification_data(self) -> NOTIFYICONDATAW:
        """Build data for adding or refreshing the notification-area icon."""
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self.window
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = TRAY_MESSAGE
        data.hIcon = self.icon
        data.szTip = self.tooltip
        return data

    def service_is_running(self) -> bool:
        """Return whether the Windows service is currently running."""
        try:
            result = subprocess.run(
                ["sc.exe", "query", "Strato-DDNS"],
                check=False,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            return False
        return result.returncode == 0 and "RUNNING" in result.stdout

    def refresh(self, add: bool = False) -> None:
        """Refresh the tooltip and icon from the service and status files."""
        healthy, tooltip = read_service_status(self.status_file)
        running = self.service_is_running()
        if not running:
            tooltip = "Strato-DDNS: Dienst ist nicht aktiv."
        if healthy != self.healthy or running != self.running:
            if self.icon:
                user32.DestroyIcon(self.icon)
            self.icon = create_status_icon(healthy, running)
            self.healthy = healthy
            self.running = running
        self.tooltip = tooltip
        action = NIM_ADD if add else NIM_MODIFY
        shell32.Shell_NotifyIconW(action, ctypes.byref(self._notification_data()))

    def show_status(self) -> None:
        """Open the configuration and service status window on a left click."""
        if self.config_window_open:
            return
        self.config_window_open = True
        threading.Thread(target=self._run_config_window, daemon=True).start()

    def _run_config_window(self) -> None:
        try:
            ConfigWindow(self).run()
        finally:
            self.config_window_open = False

    def start_service(self) -> None:
        """Ask WinSW to start the installed DDNS service."""
        try:
            result = subprocess.run(
                ["sc.exe", "start", "Strato-DDNS"],
                cwd=application_directory(),
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as error:
            user32.MessageBoxW(
                self.window,
                f"Der Dienst konnte nicht gestartet werden:\n{error}",
                "Strato-DDNS",
                0x10,
            )
            return
        if result.returncode != 0:
            user32.MessageBoxW(
                self.window,
                "Der Dienst konnte nicht gestartet werden. "
                "Prüfen Sie die Installation und die config.ini.",
                "Strato-DDNS",
                0x10,
            )
        self.refresh()

    def stop_service(self) -> None:
        """Ask WinSW to stop the installed DDNS service."""
        try:
            result = subprocess.run(
                ["sc.exe", "stop", "Strato-DDNS"],
                cwd=application_directory(),
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as error:
            user32.MessageBoxW(
                self.window,
                f"Der Dienst konnte nicht beendet werden:\n{error}",
                "Strato-DDNS",
                0x10,
            )
            return
        if result.returncode != 0:
            user32.MessageBoxW(
                self.window,
                "Der Dienst konnte nicht beendet werden.",
                "Strato-DDNS",
                0x10,
            )
        self.refresh()

    def _window_procedure(
        self, window: wintypes.HWND, message: int, wparam: int, lparam: int
    ) -> int:
        """Process timer, tray-click and shutdown messages for the hidden window."""
        if message == WM_TIMER:
            self.refresh()
            return 0
        if message == TRAY_MESSAGE:
            if lparam == WM_LBUTTONUP:
                self.show_status()
            return 0
        if message == WM_DESTROY:
            shell32.Shell_NotifyIconW(
                NIM_DELETE,
                ctypes.byref(self._notification_data()),
            )
            if self.icon:
                user32.DestroyIcon(self.icon)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(window, message, wparam, lparam)

    def run(self) -> None:
        """Create the hidden window and run the normal Windows message loop."""
        instance = ctypes.windll.kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSEXW()
        window_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        window_class.lpfnWndProc = ctypes.cast(self.window_procedure, ctypes.c_void_p)
        window_class.hInstance = instance
        window_class.lpszClassName = self.class_name
        user32.RegisterClassExW(ctypes.byref(window_class))
        self.window = user32.CreateWindowExW(
            0, self.class_name, "Strato-DDNS", 0, 0, 0, 0, 0, None, None, instance, None
        )
        self.refresh(add=True)
        user32.SetTimer(self.window, TIMER_ID, TIMER_INTERVAL_MS, None)
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))


class ConfigWindow:
    """Tkinter editor for config.ini and the current service state."""

    def __init__(self, tray: TrayApplication) -> None:
        self.tray = tray
        self.config_path = application_directory() / "config.ini"
        self.parser = configparser.ConfigParser(interpolation=None)
        self.variables: dict[tuple[str, str], tk.Variable] = {}
        self.root = tk.Tk()
        self.root.iconbitmap(str(asset_directory() / "ddns-neutral.ico"))

    def _read_config(self) -> None:
        if self.config_path.is_file():
            self.parser.read(self.config_path, encoding="utf-8")
        for section in ("ddns", "mail", "logging"):
            if not self.parser.has_section(section):
                self.parser.add_section(section)

    def _value(self, section: str, option: str) -> str:
        return self.parser.get(section, option, fallback="")

    def _entry(
        self,
        parent: ttk.Frame,
        row: int,
        section: str,
        option: str,
        label: str,
        password: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        variable = tk.StringVar(value=self._value(section, option))
        self.variables[(section, option)] = variable
        ttk.Entry(parent, textvariable=variable, show="*" if password else "").grid(
            row=row, column=1, sticky="ew", pady=3
        )

    def _paired_entries(
        self,
        parent: ttk.Frame,
        row: int,
        fields: tuple[tuple[str, str, bool], tuple[str, str, bool]],
    ) -> None:
        for column, (option, label, password) in enumerate(fields):
            label_column = column * 2
            ttk.Label(parent, text=label).grid(
                row=row, column=label_column, sticky="w", padx=(0, 8), pady=3
            )
            variable = tk.StringVar(value=self._value("ddns", option))
            self.variables[("ddns", option)] = variable
            ttk.Entry(parent, textvariable=variable, show="*" if password else "").grid(
                row=row, column=label_column + 1, sticky="ew", padx=(0, 14), pady=3
            )

    def _checkbutton(
        self, parent: ttk.Frame, row: int, section: str, option: str, label: str
    ) -> None:
        variable = tk.BooleanVar(value=self.parser.getboolean(section, option, fallback=False))
        self.variables[(section, option)] = variable
        ttk.Checkbutton(parent, text=label, variable=variable).grid(
            row=row, column=1, sticky="w", pady=3
        )

    def _section(self, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(self.root, text=title, padding=10)
        frame.pack(fill="x", padx=14, pady=(10, 0))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        return frame

    def _mail_pair(
        self,
        parent: ttk.Frame,
        row: int,
        fields: tuple[tuple[str, str, bool], tuple[str, str, bool]],
    ) -> None:
        for column, (option, label, password) in enumerate(fields):
            label_column = column * 2
            ttk.Label(parent, text=label).grid(
                row=row, column=label_column, sticky="w", padx=(0, 8), pady=3
            )
            variable = tk.StringVar(value=self._value("mail", option))
            self.variables[("mail", option)] = variable
            ttk.Entry(parent, textvariable=variable, show="*" if password else "").grid(
                row=row, column=label_column + 1, sticky="ew", padx=(0, 14), pady=3
            )

    def _save(self) -> None:
        for (section, option), variable in self.variables.items():
            self.parser.set(section, option, str(variable.get()).lower() if isinstance(variable, tk.BooleanVar) else str(variable.get()).strip())
        try:
            with self.config_path.open("w", encoding="utf-8") as config_file:
                self.parser.write(config_file)
        except OSError as error:
            messagebox.showerror("Strato-DDNS", f"Die Konfiguration konnte nicht gespeichert werden:\n{error}", parent=self.root)
            return
        messagebox.showinfo("Strato-DDNS", "Konfiguration gespeichert.", parent=self.root)

    def _update_status(self) -> None:
        healthy, message = read_service_status(self.tray.status_file)
        running = self.tray.service_is_running()
        if not running:
            text, color = "Gestoppt", "#777777"
        elif healthy:
            text, color = "Läuft · erfolgreich", "#198754"
        else:
            text, color = "Läuft · Fehler", "#dc3545"
        self.status_light.configure(background=color)
        self.status_label.configure(text=text, foreground=color)
        self.details_label.configure(text=message.replace("Strato-DDNS: ", "", 1))
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        if self.root.winfo_exists():
            self.root.after(GUI_REFRESH_MS, self._update_status)

    def _start(self) -> None:
        self.tray.start_service()
        self.root.after(500, self._update_status)

    def _stop(self) -> None:
        self.tray.stop_service()
        self.root.after(500, self._update_status)

    def run(self) -> None:
        self._read_config()
        self.root.title("Strato-DDNS")
        self.root.geometry("560x700")
        self.root.minsize(480, 580)
        self.root.columnconfigure(0, weight=1)

        status_frame = ttk.LabelFrame(self.root, text="Dienststatus", padding=10)
        status_frame.pack(fill="x", padx=14, pady=10)
        status_frame.columnconfigure(2, weight=1)
        self.status_light = tk.Label(status_frame, width=2, height=1, background="#777777")
        self.status_light.grid(row=0, column=0, padx=(0, 8))
        self.status_label = ttk.Label(status_frame, text="Wird geprüft...")
        self.status_label.grid(row=0, column=1, sticky="w")
        self.details_label = ttk.Label(status_frame, text="")
        self.details_label.grid(row=0, column=2, sticky="ew", padx=(14, 0))
        button_frame = ttk.Frame(status_frame)
        button_frame.grid(row=1, column=0, columnspan=3, sticky="e", pady=(10, 0))
        self.start_button = ttk.Button(button_frame, text="Starten", command=self._start)
        self.start_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(button_frame, text="Stoppen", command=self._stop)
        self.stop_button.pack(side="left")

        ddns = self._section("DDNS")
        self._entry(ddns, 0, "ddns", "hostname", "Hostname")
        self._entry(ddns, 1, "ddns", "hostname_2", "Hostname 2")
        self._entry(ddns, 2, "ddns", "hostname_3", "Hostname 3")
        self._paired_entries(
            ddns, 3, (("username", "Benutzername", False), ("password", "Passwort", True))
        )
        self._entry(ddns, 4, "ddns", "interval_seconds", "Intervall (sec)")
        self._checkbutton(ddns, 5, "ddns", "update_ipv6", "IPv6 aktualisieren")

        mail = self._section("E-Mail")
        self._checkbutton(mail, 0, "mail", "enabled", "E-Mail-Benachrichtigungen aktiv")
        self._mail_pair(mail, 1, (("host", "SMTP-Host", False), ("port", "Port", False)))
        self._mail_pair(mail, 2, (("username", "Benutzername", False), ("password", "Passwort", True)))
        self._entry(mail, 3, "mail", "sender", "Absender")
        self._entry(mail, 4, "mail", "recipient", "Empfänger")
        self._checkbutton(mail, 5, "mail", "starttls", "STARTTLS verwenden")
        self._checkbutton(mail, 6, "mail", "recovery_mail", "Wiederherstellungs-Mail senden")

        ttk.Button(self.root, text="Speichern", command=self._save).pack(anchor="e", padx=14, pady=10)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self._update_status()
        self.root.mainloop()


if __name__ == "__main__":
    TrayApplication().run()
