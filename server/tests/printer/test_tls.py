import socket

import pytest
from printer_helpers import TlsServer

from filament_tracker.printer.tls import (
    CertificateMismatchError,
    fetch_fingerprint,
    fingerprint,
    pinned_context,
)


def connect(server: TlsServer, sha256: str) -> None:
    with (
        socket.create_connection((server.host, server.port), timeout=5) as raw,
        pinned_context(sha256).wrap_socket(raw),
    ):
        pass


def test_fingerprint_is_lower_case_sha256_hex() -> None:
    assert fingerprint(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_fetching_reads_the_certificate_fingerprint(tls_server: TlsServer) -> None:
    assert fetch_fingerprint(tls_server.host, tls_server.port) == tls_server.sha256


def test_the_pinned_certificate_is_accepted(tls_server: TlsServer) -> None:
    connect(tls_server, tls_server.sha256.upper())


def test_any_other_certificate_is_refused(tls_server: TlsServer) -> None:
    with pytest.raises(CertificateMismatchError) as error:
        connect(tls_server, "0" * 64)

    assert error.value.actual == tls_server.sha256


def test_fetching_from_nothing_fails() -> None:
    with socket.create_server(("127.0.0.1", 0)) as unused:
        port = unused.getsockname()[1]
    with pytest.raises(OSError):
        fetch_fingerprint("127.0.0.1", port, timeout=2)
