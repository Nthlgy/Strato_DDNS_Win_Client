"""Strato Dynamic DNS update client."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

from src.config import DdnsConfig

UPDATE_URL = "https://dyndns.strato.com/nic/update"


class DdnsError(RuntimeError):
    """Raised when Strato rejects an update or cannot be contacted."""


@dataclass(frozen=True)
class UpdateResult:
    """The parsed response to an update request."""

    successful: bool
    response: str


def update_ips(
    config: DdnsConfig, addresses: dict[str, str], logger: logging.Logger
) -> UpdateResult:
    """Send the changed address set to Strato's DynDNS endpoint.

    Strato expects IPv4 and IPv6 together as a comma-separated ``myip`` value.
    Sending both families preserves the current A and AAAA record as one update.
    """
    address_text = ",".join(
        address
        for family, address in (
            ("ipv4", addresses.get("ipv4")),
            ("ipv6", addresses.get("ipv6")),
        )
        if address
    )
    request_error: requests.RequestException | None = None
    for attempt in range(1, config.retries + 1):
        try:
            response = requests.get(
                UPDATE_URL,
                # Strato's DynDNS API accepts comma-separated hostnames.
                params={
                    "hostname": ",".join(config.hostnames),
                    "myip": address_text,
                },
                auth=(config.username, config.password),
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            break
        except requests.RequestException as error:
            request_error = error
            logger.warning(
                "Strato update failed (%s/%s): %s",
                attempt,
                config.retries,
                error,
            )
            if attempt < config.retries:
                time.sleep(attempt)
    else:
        raise DdnsError(f"Strato update request failed: {request_error}")

    answer = response.text.strip()
    keyword = answer.split(maxsplit=1)[0].lower() if answer else ""
    if keyword in {"good", "nochg"}:
        logger.info("Strato accepted %s update: %s", address_text, answer)
        return UpdateResult(successful=True, response=answer)

    # These are permanent or protocol errors, and must not be silently ignored.
    known_errors = {
        "badauth", "nohost", "notfqdn", "badagent", "abuse", "911", "dnserr",
    }
    description = "known error" if keyword in known_errors else "unexpected response"
    raise DdnsError(f"Strato returned {description}: {answer or '<empty>'}")
