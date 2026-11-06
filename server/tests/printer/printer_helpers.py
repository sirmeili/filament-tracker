"""Shared by the printer tests: a throwaway certificate and the TLS server's details.

The certificate is made with the openssl command when the tests run, so no key is ever
stored in the repo.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class TlsServer:
    host: str
    port: int
    sha256: str


def make_certificate(directory: Path, name: str) -> tuple[Path, Path]:
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is needed to make a test certificate")
    cert, key = directory / f"{name}.pem", directory / f"{name}.key"
    subprocess.run(  # noqa: S603 - fixed arguments, test only
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            f"/CN={name}",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    return cert, key
