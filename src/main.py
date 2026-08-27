"""CLI entry point and service loop for Strato-DDNS."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from src.config import AppConfig, ConfigurationError, load_config
from src.ddns import DdnsError, update_ips
from src.ipcheck import IpLookupError, get_public_ip
from src.logger import create_logger
from src.mail import send_mail
from src.notifications import report_failure, report_recovery
from src.state import StateStore


def application_directory() -> Path:
    """Return the directory beside the executable, or the project root in Python."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def run_cycle(
    config: AppConfig, state: StateStore, logger: logging.Logger, force: bool
) -> bool:
    """Discover addresses and update Strato only when they differ from saved state."""
    stale_after_seconds = max(config.ddns.interval_seconds * 2, 60)
    state.heartbeat(stale_after_seconds)
    try:
        discovered = {
            "ipv4": get_public_ip(
                4, config.ddns.timeout_seconds, config.ddns.retries, logger
            )
        }
        if config.ddns.update_ipv6:
            discovered["ipv6"] = get_public_ip(
                6, config.ddns.timeout_seconds, config.ddns.retries, logger
            )

        previous = state.read_ips()
        changed = force or any(
            previous.get(family) != address
            for family, address in discovered.items()
        )
        if changed:
            update_ips(config.ddns, discovered, logger)
        else:
            logger.info(
                "All configured addresses are unchanged; no Strato update needed."
            )
        state.write_ips(discovered)
        report_recovery(state, config.mail, logger)
        state.write_status(
            True,
            "DDNS synchronization successful.",
            discovered,
            stale_after_seconds,
        )
        return True
    except (IpLookupError, DdnsError, OSError) as error:
        message = f"DDNS cycle failed: {error}"
        logger.exception(message)
        report_failure(state, config.mail, message, logger)
        state.write_status(
            False,
            message,
            state.read_ips(),
            stale_after_seconds,
        )
        return False


def show_status(state: StateStore) -> int:
    """Print the persistent status without contacting external services."""
    addresses = state.read_ips()
    if addresses:
        for family, address in sorted(addresses.items()):
            print(f"{family}: {address}")
    else:
        print("No successful DDNS update has been recorded.")
    print("status: ERROR" if state.has_error() else "status: OK")
    return 1 if state.has_error() else 0


def parse_arguments() -> argparse.Namespace:
    """Define the mutually exclusive command-line operations."""
    parser = argparse.ArgumentParser(description="Strato Dynamic DNS updater")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--test", action="store_true", help="Test IP lookup and update logic once."
    )
    group.add_argument(
        "--status", action="store_true", help="Show locally saved status."
    )
    group.add_argument(
        "--force",
        action="store_true",
        help="Force one Strato update if IP is unchanged.",
    )
    group.add_argument(
        "--mail-test",
        action="store_true",
        help="Send one test message using the configured SMTP settings.",
    )
    return parser.parse_args()


def main() -> int:
    """Run a requested CLI command or the continuous Windows-service loop."""
    args = parse_arguments()
    root = application_directory()
    state = StateStore(root / "state")
    if args.status:
        return show_status(state)
    try:
        config = load_config(root / "config.ini")
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    logger = create_logger(root / "logs" / "ddns.log", config.log_level)
    if args.mail_test:
        if not config.mail.enabled:
            logger.error("Mail test skipped: mail notifications are disabled.")
            return 2
        sent = send_mail(
            config.mail,
            "Strato-DDNS: SMTP-Test erfolgreich",
            "Diese Nachricht bestätigt die SMTP-Konfiguration von Strato-DDNS.",
            logger,
        )
        if sent:
            logger.info("SMTP test message submitted successfully.")
            return 0
        logger.error("SMTP test message could not be submitted.")
        return 1
    if args.test or args.force:
        return 0 if run_cycle(config, state, logger, force=args.force) else 1

    logger.info(
        "Strato-DDNS service started; interval: %s seconds.",
        config.ddns.interval_seconds,
    )
    while True:
        run_cycle(config, state, logger, force=False)
        time.sleep(config.ddns.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
