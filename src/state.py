"""Persistent local state for addresses and failure notification suppression."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class StateStore:
    """Read and write state files below the application's state directory."""

    def __init__(self, state_directory: Path) -> None:
        self.state_directory = state_directory
        self.last_ip_file = state_directory / "last_ip.txt"
        self.error_file = state_directory / "error.flag"
        self.status_file = state_directory / "status.json"
        self.state_directory.mkdir(parents=True, exist_ok=True)

    def read_ips(self) -> dict[str, str]:
        """Return previously confirmed IP addresses by family."""
        if not self.last_ip_file.is_file():
            return {}
        result: dict[str, str] = {}
        for line in self.last_ip_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"ipv4", "ipv6"} and value:
                result[key] = value
        return result

    def write_ips(self, addresses: dict[str, str]) -> None:
        """Persist confirmed addresses atomically enough for this single process."""
        content = "".join(
            f"{key}={value}\n" for key, value in sorted(addresses.items())
        )
        self.last_ip_file.write_text(content, encoding="utf-8")

    def has_error(self) -> bool:
        """Return whether a previous update cycle failed."""
        return self.error_file.is_file()

    def record_error(self, message: str) -> None:
        """Persist the current failure text."""
        self.error_file.write_text(message + "\n", encoding="utf-8")

    def clear_error(self) -> None:
        """Remove the failure marker after a successful cycle."""
        if self.error_file.exists():
            self.error_file.unlink()

    def read_status(self) -> dict[str, object]:
        """Return the public service status, or an empty value before first run."""
        if not self.status_file.is_file():
            return {}
        try:
            content = self.status_file.read_text(encoding="utf-8")
            status = json.loads(content)
        except (OSError, json.JSONDecodeError):
            return {}
        return status if isinstance(status, dict) else {}

    def write_status(
        self,
        healthy: bool,
        message: str,
        addresses: dict[str, str],
        stale_after_seconds: int,
    ) -> None:
        """Atomically publish service health for the separate tray application."""
        now = datetime.now(timezone.utc).isoformat()
        status = {
            "heartbeat_at": now,
            "healthy": healthy,
            "message": message,
            "addresses": addresses,
            "stale_after_seconds": stale_after_seconds,
        }
        temporary_file = self.status_file.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_file.replace(self.status_file)

    def heartbeat(self, stale_after_seconds: int) -> None:
        """Refresh the liveness timestamp before a potentially slow update cycle."""
        previous = self.read_status()
        healthy = bool(previous.get("healthy", False))
        message = str(previous.get("message", "DDNS service is starting."))
        self.write_status(
            healthy,
            message,
            self.read_ips(),
            stale_after_seconds,
        )
