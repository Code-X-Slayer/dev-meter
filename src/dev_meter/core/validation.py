"""Validation helpers for configuration and external destinations."""

import ipaddress
import socket
from urllib.parse import urlsplit


def validate_upstream_url(value: str) -> None:
    """Reject URL destinations that are unsafe for future outbound requests."""
    parsed = urlsplit(value)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("upstream URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("upstream URL must not include credentials")

    normalized_hostname = hostname.rstrip(".").lower()
    blocked_names = {"localhost", "localhost.localdomain", "metadata.google.internal"}
    if (
        normalized_hostname in blocked_names
        or normalized_hostname.endswith(".local")
        or normalized_hostname.endswith(".internal")
    ):
        raise ValueError("upstream URL points to an internal hostname")

    addresses: set[str] = set()
    try:
        addresses.update(
            address[4][0] for address in socket.getaddrinfo(normalized_hostname, None)
        )
    except socket.gaierror:
        pass

    try:
        addresses.add(str(ipaddress.ip_address(normalized_hostname)))
    except ValueError:
        pass

    for address in addresses:
        parsed_address = ipaddress.ip_address(address)
        if (
            parsed_address.is_loopback
            or parsed_address.is_private
            or parsed_address.is_link_local
            or parsed_address.is_unspecified
            or parsed_address.is_reserved
            or parsed_address.is_multicast
        ):
            raise ValueError("upstream URL points to an unsafe network address")
