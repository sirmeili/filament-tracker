"""Client addresses behind a reverse proxy, and the LAN check.

`X-Forwarded-For` is believed only when the direct peer is a configured proxy
(`FORWARDED_ALLOW_IPS`). The header is read from the right, skipping proxy addresses,
so a client cannot pretend to be on the LAN by sending its own header.
"""

from collections.abc import Iterable
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import HTTPConnection

from filament_tracker.config import Network, Settings

Address = IPv4Address | IPv6Address


def parse_ip(value: str | None) -> Address | None:
    if not value:
        return None
    try:
        return ip_address(value.strip())
    except ValueError:
        return None


def _within(address: Address, networks: Iterable[Network]) -> bool:
    return any(address.version == net.version and address in net for net in networks)


def client_ip(request: HTTPConnection, settings: Settings) -> Address | None:
    """The real client address, or None if it cannot be determined."""
    peer = parse_ip(request.client.host if request.client else None)
    if peer is None or not _within(peer, settings.forwarded_allow_ips):
        return peer
    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer
    hops = [part.strip() for part in forwarded.split(",")]
    for hop in reversed(hops):
        address = parse_ip(hop)
        if address is None:
            return None
        if not _within(address, settings.forwarded_allow_ips):
            return address
    return parse_ip(hops[0])


def is_trusted(request: HTTPConnection, settings: Settings) -> bool:
    """True if the client is on a trusted network (the LAN)."""
    address = client_ip(request, settings)
    return address is not None and _within(address, settings.trusted_networks)
