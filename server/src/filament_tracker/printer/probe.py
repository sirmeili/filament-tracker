"""The Devices page's Test button for a printer: connect once and disconnect.

The certificate is checked before anything is sent: with a pin, a different certificate
is reported as a mismatch and the access code is never sent to it. Without a pin, the
certificate found is trusted for this one connection, as on first use, but not saved.
Results are only a category, never the printer's error text.
"""

import asyncio
import secrets
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import aiomqtt

from filament_tracker.config import PrinterConfig
from filament_tracker.ha.check import REFUSED_CODES, TIMEOUT_SECONDS
from filament_tracker.printer.link import USERNAME
from filament_tracker.printer.tls import fetch_fingerprint, pinned_context


class PrinterCheck(StrEnum):
    OK = "ok"
    UNREACHABLE = "unreachable"
    REFUSED = "refused"  # the access code was not accepted
    PIN_MISMATCH = "pin_mismatch"
    ERROR = "error"


def _code(error: aiomqtt.MqttCodeError) -> int | None:
    rc: Any = error.rc
    try:
        return int(getattr(rc, "value", rc))
    except (TypeError, ValueError):
        return None


async def _connect(config: PrinterConfig, sha256: str, client_factory: Callable[..., Any]) -> None:
    client = client_factory(
        hostname=config.host,
        port=config.port,
        username=USERNAME,
        password=config.access_code.get_secret_value(),
        identifier=f"filament-tracker-test-{secrets.token_hex(4)}",
        tls_context=pinned_context(sha256),
        tls_insecure=True,
        timeout=TIMEOUT_SECONDS,
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with client:
            pass


def check_printer(
    config: PrinterConfig,
    pinned_sha256: str | None,
    *,
    client_factory: Callable[..., Any] = aiomqtt.Client,
    fetch: Callable[[str, int], str] = fetch_fingerprint,
) -> PrinterCheck:
    """Runs its own selector event loop (aiomqtt needs one on Windows), so it can be called
    from a request's worker thread."""
    try:
        found = fetch(config.host, config.port)
    except (OSError, TimeoutError):
        return PrinterCheck.UNREACHABLE
    if pinned_sha256 is not None and found != pinned_sha256.lower():
        return PrinterCheck.PIN_MISMATCH
    loop = asyncio.SelectorEventLoop()
    try:
        loop.run_until_complete(_connect(config, found, client_factory))
    except aiomqtt.MqttCodeError as error:
        return PrinterCheck.REFUSED if _code(error) in REFUSED_CODES else PrinterCheck.ERROR
    except (aiomqtt.MqttError, OSError, TimeoutError):
        return PrinterCheck.UNREACHABLE
    finally:
        loop.close()
    return PrinterCheck.OK
