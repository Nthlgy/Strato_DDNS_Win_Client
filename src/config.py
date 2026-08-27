"""Loading and validation of the config.ini file."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when config.ini is missing a required, valid value."""


@dataclass(frozen=True)
class DdnsConfig:
    """Connection details for Strato Dynamic DNS."""

    hostnames: tuple[str, ...]
    username: str
    password: str
    update_ipv6: bool
    timeout_seconds: int
    retries: int
    interval_seconds: int


@dataclass(frozen=True)
class MailConfig:
    """SMTP notification settings."""

    enabled: bool
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str
    starttls: bool
    recovery_mail: bool


@dataclass(frozen=True)
class AppConfig:
    """All validated application configuration."""

    ddns: DdnsConfig
    mail: MailConfig
    log_level: str


def _required(parser: configparser.ConfigParser, section: str, option: str) -> str:
    """Return a non-empty setting or raise a useful configuration error."""
    value = parser.get(section, option, fallback="").strip()
    if not value:
        raise ConfigurationError(f"[{section}] {option} must be configured.")
    return value


def load_config(config_path: Path) -> AppConfig:
    """Read config.ini and return a strongly typed configuration object."""
    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8")
    for section in ("ddns", "mail", "logging"):
        if not parser.has_section(section):
            raise ConfigurationError(f"Missing [{section}] section in config.ini.")

    try:
        primary_hostname = _required(parser, "ddns", "hostname")
        # Empty optional hostnames are ignored, preserving one-host configurations.
        hostnames = tuple(
            hostname
            for hostname in (
                primary_hostname,
                parser.get("ddns", "hostname_2", fallback="").strip(),
                parser.get("ddns", "hostname_3", fallback="").strip(),
            )
            if hostname
        )
        if len(set(hostnames)) != len(hostnames):
            raise ConfigurationError("DDNS hostnames must not be duplicated.")

        ddns = DdnsConfig(
            hostnames=hostnames,
            username=_required(parser, "ddns", "username"),
            password=_required(parser, "ddns", "password"),
            update_ipv6=parser.getboolean("ddns", "update_ipv6", fallback=False),
            timeout_seconds=parser.getint("ddns", "timeout_seconds", fallback=10),
            retries=parser.getint("ddns", "retries", fallback=3),
            interval_seconds=parser.getint("ddns", "interval_seconds", fallback=300),
        )
        mail = MailConfig(
            enabled=parser.getboolean("mail", "enabled", fallback=False),
            host=parser.get("mail", "host", fallback="").strip(),
            port=parser.getint("mail", "port", fallback=587),
            username=parser.get("mail", "username", fallback="").strip(),
            password=parser.get("mail", "password", fallback="").strip(),
            sender=parser.get("mail", "sender", fallback="").strip(),
            recipient=parser.get("mail", "recipient", fallback="").strip(),
            starttls=parser.getboolean("mail", "starttls", fallback=True),
            recovery_mail=parser.getboolean("mail", "recovery_mail", fallback=True),
        )
    except (ValueError, configparser.Error) as error:
        raise ConfigurationError(f"Invalid config.ini value: {error}") from error

    if ddns.timeout_seconds < 1 or ddns.retries < 1 or ddns.interval_seconds < 1:
        raise ConfigurationError(
            "timeout_seconds, retries and interval_seconds must be positive."
        )
    if mail.enabled and not all((mail.host, mail.sender, mail.recipient)):
        raise ConfigurationError("Enabled mail needs host, sender and recipient.")
    log_level = parser.get("logging", "level", fallback="INFO")
    return AppConfig(ddns=ddns, mail=mail, log_level=log_level)
