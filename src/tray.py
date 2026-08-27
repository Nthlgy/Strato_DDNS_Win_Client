"""Native Windows notification-area indicator for the Strato-DDNS service."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
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
ID_STOP_SERVICE = 1001
ID_START_SERVICE = 1002
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_BORDER = 0x00800000
BS_PUSHBUTTON = 0x00000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
TIMER_ID = 1
TIMER_INTERVAL_MS = 10_000

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
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
    """Own the hidden window, icon, timer and context menu."""

    def __init__(self) -> None:
        self.status_file = application_directory() / "state" / "status.json"
        self.class_name = "StratoDdnsTrayWindow"
        self.icon: wintypes.HANDLE | None = None
        self.healthy: bool | None = None
        self.running: bool | None = None
        self.tooltip = "Strato-DDNS: Loading service status..."
        self.window: wintypes.HWND | None = None
        self.menu_window: wintypes.HWND | None = None
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
        """Display the full current tooltip on a left click."""
        user32.MessageBoxW(self.window, self.tooltip, "Strato-DDNS", 0x40)

    def start_service(self) -> None:
        """Ask WinSW to start the installed DDNS service."""
        service_launcher = application_directory() / "WinSW.exe"
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
        service_launcher = application_directory() / "WinSW.exe"
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

    def show_menu(self) -> None:
        """Show a small native popup with visible service-control buttons."""
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        if self.menu_window:
            user32.DestroyWindow(self.menu_window)
        self.menu_window = user32.CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_TOPMOST,
            self.class_name,
            "Strato-DDNS",
            WS_POPUP | WS_BORDER,
            point.x - 170,
            point.y - 58,
            170,
            58,
            self.window,
            None,
            ctypes.windll.kernel32.GetModuleHandleW(None),
            None,
        )
        for command_id, label, top in (
            (ID_START_SERVICE, "Dienst starten", 4),
            (ID_STOP_SERVICE, "Dienst beenden", 30),
        ):
            user32.CreateWindowExW(
                0,
                "BUTTON",
                label,
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                4,
                top,
                162,
                23,
                self.menu_window,
                command_id,
                ctypes.windll.kernel32.GetModuleHandleW(None),
                None,
            )
        user32.ShowWindow(self.menu_window, 1)
        user32.SetForegroundWindow(self.menu_window)

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
            elif lparam == WM_RBUTTONUP:
                self.show_menu()
            return 0
        if message == WM_COMMAND and window == self.menu_window:
            command_id = wparam & 0xFFFF
            user32.DestroyWindow(self.menu_window)
            self.menu_window = None
            if command_id == ID_START_SERVICE:
                self.start_service()
            elif command_id == ID_STOP_SERVICE:
                self.stop_service()
            return 0
        if message == WM_DESTROY:
            if window == self.menu_window:
                self.menu_window = None
                return 0
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


if __name__ == "__main__":
    TrayApplication().run()
