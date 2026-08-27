"""Logging setup for Strato-DDNS."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def create_logger(log_file: Path, level_name: str) -> logging.Logger:
    """Create the application logger, writing both to a file and console."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("strato_ddns")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, level_name.upper(), logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
