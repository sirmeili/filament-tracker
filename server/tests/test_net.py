from ipaddress import ip_address

import pytest
from starlette.requests import HTTPConnection

from filament_tracker.config import Settings
from filament_tracker.net import client_ip, is_trusted, parse_ip

PROXY = "192.168.1.5"


def _conn(peer: str | None, forwarded: str | None = None) -> HTTPConnection:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    scope = {
        "type": "http",
        "headers": headers,
        "client": (peer, 1234) if peer is not None else None,
    }
    return HTTPConnection(scope)


def _settings(proxies: str = "") -> Settings:
    return Settings(database_url="sqlite://", forwarded_allow_ips=proxies, _env_file=None)


@pytest.mark.parametrize("value", [None, "", "testclient", "1.2.3"])
def test_parse_ip_rejects_non_addresses(value: str | None) -> None:
    assert parse_ip(value) is None


def test_without_a_proxy_the_peer_is_the_client() -> None:
    conn = _conn("203.0.113.7", "192.168.1.20")

    assert client_ip(conn, _settings()) == ip_address("203.0.113.7")


def test_a_proxy_without_a_forwarded_header_is_the_client() -> None:
    assert client_ip(_conn(PROXY), _settings(PROXY)) == ip_address(PROXY)


@pytest.mark.parametrize(
    ("forwarded", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("10.0.0.1, 203.0.113.7", "203.0.113.7"),  # the left entry came from the client
        (f"203.0.113.7, {PROXY}", "203.0.113.7"),  # proxy addresses are skipped
        (f"{PROXY}, {PROXY}", PROXY),  # all proxies: the leftmost
        ("2001:db8::1", "2001:db8::1"),
    ],
)
def test_behind_a_proxy_the_rightmost_other_address_is_the_client(
    forwarded: str, expected: str
) -> None:
    assert client_ip(_conn(PROXY, forwarded), _settings(PROXY)) == ip_address(expected)


def test_a_garbled_forwarded_header_gives_no_address() -> None:
    assert client_ip(_conn(PROXY, "203.0.113.7, junk"), _settings(PROXY)) is None


def test_no_peer_gives_no_address_and_is_not_trusted() -> None:
    conn = _conn(None)

    assert client_ip(conn, _settings()) is None
    assert not is_trusted(conn, _settings())


@pytest.mark.parametrize(
    ("peer", "trusted"),
    [
        ("192.168.1.20", True),
        ("10.4.5.6", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("fd00::5", True),
        ("203.0.113.7", False),
        ("2001:db8::1", False),
        ("testclient", False),
    ],
)
def test_private_ranges_are_trusted_by_default(peer: str, trusted: bool) -> None:
    assert is_trusted(_conn(peer), _settings()) is trusted
