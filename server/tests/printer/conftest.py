"""A local TLS server with a throwaway self-signed certificate, standing in for a printer."""

import socket
import ssl
import threading
from collections.abc import Iterator

import pytest
from printer_helpers import TlsServer, make_certificate

from filament_tracker.printer.tls import fingerprint


@pytest.fixture(scope="session")
def tls_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TlsServer]:
    cert, key = make_certificate(tmp_path_factory.mktemp("tls"), "fake-printer")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))

    listener = socket.create_server(("127.0.0.1", 0))
    listener.settimeout(0.2)
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                raw, _ = listener.accept()
            except TimeoutError:
                continue
            try:
                with context.wrap_socket(raw, server_side=True) as tls:
                    tls.settimeout(1)
                    tls.recv(1)
            except (OSError, ssl.SSLError):
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield TlsServer("127.0.0.1", port, fingerprint(der))
    stop.set()
    thread.join(2)
    listener.close()
