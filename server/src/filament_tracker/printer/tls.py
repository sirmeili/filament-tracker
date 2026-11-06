"""Trust a printer's TLS certificate by pinning it on first use.

Bambu printers (and MQTT proxies) use certificates no public authority signs, so the
server records the SHA-256 fingerprint of the certificate it first sees and from then on
accepts only that certificate. The check runs right after the TLS handshake, before the
MQTT client sends anything, so the access code never goes to a different certificate.
"""

import hashlib
import socket
import ssl


class CertificateMismatchError(ssl.SSLError):
    """The server's certificate is not the pinned one."""

    def __init__(self, actual: str | None) -> None:
        super().__init__("the printer's certificate does not match the pinned one")
        self.actual = actual


def fingerprint(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


class _PinnedSocket(ssl.SSLSocket):
    def do_handshake(self, block: bool = False) -> None:
        super().do_handshake(block)
        der = self.getpeercert(binary_form=True)
        actual = fingerprint(der) if der else None
        if actual is None or actual != getattr(self.context, "pinned_sha256", None):
            raise CertificateMismatchError(actual)


class PinnedContext(ssl.SSLContext):
    """A TLS client context that accepts only the certificate with `pinned_sha256`."""

    sslsocket_class = _PinnedSocket
    pinned_sha256: str


def _unverified_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # No authority signs these certificates; the pin does the checking instead.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def pinned_context(sha256: str) -> PinnedContext:
    context = PinnedContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.pinned_sha256 = sha256.lower()
    return context


def fetch_fingerprint(host: str, port: int, timeout: float = 10.0) -> str:
    """Complete a TLS handshake only, and return the server certificate's fingerprint.
    Nothing is sent over the connection."""
    with (
        socket.create_connection((host, port), timeout=timeout) as raw,
        _unverified_context().wrap_socket(raw) as tls,
    ):
        der = tls.getpeercert(binary_form=True)
    if not der:
        raise ssl.SSLError("the server sent no certificate")
    return fingerprint(der)
