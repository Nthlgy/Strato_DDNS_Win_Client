"""Public IP address discovery with retry and fallback providers."""

from __future__ import annotations

import ipaddress
import logging
import time

import requests

IPV4_SERVICES = (
    "https://api.ipify.org",
    "https://ipv4.icanhazip.com",
    "https://checkip.amazonaws.com",
)
IPV6_SERVICES = ("https://api64.ipify.org", "https://ipv6.icanhazip.com")


class IpLookupError(RuntimeError):
    """Raised when no public IP service can provide a valid address."""


def get_public_ip(
    version: int, timeout_seconds: int, retries: int, logger: logging.Logger
) -> str:
    """Return a public IPv4 or IPv6 address from a fallback service."""
    services = IPV4_SERVICES if version == 4 else IPV6_SERVICES
    failures: list[str] = []
    for attempt in range(1, retries + 1):
        for service in services:
            try:
                response = requests.get(service, timeout=timeout_seconds)
                response.raise_for_status()
                address = ipaddress.ip_address(response.text.strip())
                if address.version != version:
                    raise ValueError(
                        f"Expected IPv{version}, received {address.version}"
                    )
                return str(address)
            except (requests.RequestException, ValueError) as error:
                failures.append(f"{service}: {error}")
                logger.warning("IP lookup failed (%s/%s): %s", attempt, retries, error)
        if attempt < retries:
            time.sleep(attempt)
    raise IpLookupError("; ".join(failures))
