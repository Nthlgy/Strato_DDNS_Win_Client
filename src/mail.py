"""SMTP message delivery used by error notifications."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from src.config import MailConfig


def send_mail(
    config: MailConfig, subject: str, body: str, logger: logging.Logger
) -> bool:
    """Send one plaintext SMTP message when mail notifications are enabled."""
    if not config.enabled:
        return False
    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = config.recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
            smtp.ehlo()
            if config.starttls:
                smtp.starttls()
                smtp.ehlo()
            if config.username:
                smtp.login(config.username, config.password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as error:
        logger.exception("Could not send notification mail: %s", error)
        return False
