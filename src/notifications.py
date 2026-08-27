"""Failure and recovery notification policy."""

from __future__ import annotations

import logging

from src.config import MailConfig
from src.mail import send_mail
from src.state import StateStore


def report_failure(
    state: StateStore, config: MailConfig, message: str, logger: logging.Logger
) -> None:
    """Record a failure and send exactly one mail for the failure period."""
    already_reported = state.has_error()
    state.record_error(message)
    if not already_reported:
        send_mail(config, "Strato-DDNS: Fehler", message, logger)


def report_recovery(
    state: StateStore, config: MailConfig, logger: logging.Logger
) -> None:
    """Clear a failure marker and optionally send a recovery notification."""
    if not state.has_error():
        return
    state.clear_error()
    if config.recovery_mail:
        send_mail(
            config,
            "Strato-DDNS: Wiederhergestellt",
            "Der Strato-DDNS-Abgleich funktioniert wieder.",
            logger,
        )
