"""The Settings page's Test button: try the broker and Home Assistant once.

Results are only a category (owner's choice, 2026-11-07): never the server's error text,
which could repeat an address, a user name or worse.
"""

import asyncio
import secrets
from collections.abc import Callable
from enum import StrEnum
from typing import Any

import aiomqtt

from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.rest import HaRest, HaRestError, Problem

TIMEOUT_SECONDS = 10.0
# CONNACK codes for a refused user name or password: MQTT 3.1.1 (4, 5) and MQTT 5 (134, 135).
REFUSED_CODES = frozenset({4, 5, 134, 135})


class CheckResult(StrEnum):
    OK = "ok"
    OFF = "off"  # not set, so nothing to try
    UNREACHABLE = "unreachable"
    REFUSED = "refused"
    ERROR = "error"


def _code(error: aiomqtt.MqttCodeError) -> int | None:
    rc: Any = error.rc
    try:
        return int(getattr(rc, "value", rc))
    except (TypeError, ValueError):
        return None


async def _connect(broker: BrokerConfig, client_factory: Callable[..., Any]) -> None:
    password = broker.password.get_secret_value() if broker.password else None
    client = client_factory(
        hostname=broker.host,
        port=broker.port,
        username=broker.username,
        password=password,
        identifier=f"filament-tracker-test-{secrets.token_hex(4)}",
        tls_context=broker.tls_context(),
        timeout=TIMEOUT_SECONDS,
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        async with client:
            pass


def check_broker(
    broker: BrokerConfig | None, client_factory: Callable[..., Any] = aiomqtt.Client
) -> CheckResult:
    """Connect once and disconnect. Runs its own selector event loop (aiomqtt needs one on
    Windows), so it can be called from a request's worker thread."""
    if broker is None:
        return CheckResult.OFF
    loop = asyncio.SelectorEventLoop()
    try:
        loop.run_until_complete(_connect(broker, client_factory))
    except aiomqtt.MqttCodeError as error:
        return CheckResult.REFUSED if _code(error) in REFUSED_CODES else CheckResult.ERROR
    except (aiomqtt.MqttError, OSError, TimeoutError):
        return CheckResult.UNREACHABLE
    finally:
        loop.close()
    return CheckResult.OK


def check_rest(rest: HaRest | None) -> CheckResult:
    if rest is None:
        return CheckResult.OFF
    try:
        rest.check()
    except HaRestError as error:
        return {
            Problem.UNREACHABLE: CheckResult.UNREACHABLE,
            Problem.REFUSED: CheckResult.REFUSED,
        }.get(error.problem, CheckResult.ERROR)
    return CheckResult.OK
