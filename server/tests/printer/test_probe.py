"""The Devices page's printer Test: the certificate is checked before the access code is
sent, and the answer is only a category."""

from typing import Any

import aiomqtt
import pytest

from filament_tracker.config import PrinterConfig
from filament_tracker.printer.probe import PrinterCheck, check_printer

CODE = "code1234"  # test value
CONFIG = PrinterConfig(name="P1S", host="printer.lan", serial="01P00A1", access_code=CODE)
PIN = "ab" * 32


class FakeClient:
    made: list[dict[str, Any]] = []

    def __init__(self, error: BaseException | None = None, **kwargs: Any) -> None:
        FakeClient.made.append(kwargs)
        self._error = error

    async def __aenter__(self) -> "FakeClient":
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def factory(error: BaseException | None = None):  # noqa: ANN201
    return lambda **kwargs: FakeClient(error, **kwargs)


def test_ok_connects_once_with_the_access_code() -> None:
    FakeClient.made = []
    result = check_printer(CONFIG, PIN, client_factory=factory(), fetch=lambda h, p: PIN)
    assert result is PrinterCheck.OK
    [made] = FakeClient.made
    assert (made["hostname"], made["port"], made["username"]) == ("printer.lan", 8883, "bblp")
    assert made["password"] == CODE
    assert made["tls_context"].pinned_sha256 == PIN
    assert made["identifier"].startswith("filament-tracker-test-")


def test_without_a_pin_the_found_certificate_is_used_for_this_test() -> None:
    FakeClient.made = []
    result = check_printer(CONFIG, None, client_factory=factory(), fetch=lambda h, p: "cd" * 32)
    assert result is PrinterCheck.OK
    assert FakeClient.made[0]["tls_context"].pinned_sha256 == "cd" * 32


def test_a_different_certificate_never_gets_the_code() -> None:
    FakeClient.made = []
    result = check_printer(
        CONFIG, PIN.upper(), client_factory=factory(), fetch=lambda h, p: "cd" * 32
    )
    assert result is PrinterCheck.PIN_MISMATCH
    assert FakeClient.made == []


def test_an_unreachable_printer() -> None:
    def fail(host: str, port: int) -> str:
        raise OSError("no route")

    assert check_printer(CONFIG, PIN, client_factory=factory(), fetch=fail) is (
        PrinterCheck.UNREACHABLE
    )


@pytest.mark.parametrize(
    ("error", "result"),
    [
        (aiomqtt.MqttCodeError(5), PrinterCheck.REFUSED),
        (aiomqtt.MqttCodeError(134), PrinterCheck.REFUSED),
        (aiomqtt.MqttCodeError(2), PrinterCheck.ERROR),
        (aiomqtt.MqttCodeError("odd"), PrinterCheck.ERROR),
        (aiomqtt.MqttError("gone"), PrinterCheck.UNREACHABLE),
        (OSError("reset"), PrinterCheck.UNREACHABLE),
    ],
)
def test_connection_problems(error: BaseException, result: PrinterCheck) -> None:
    assert check_printer(CONFIG, PIN, client_factory=factory(error), fetch=lambda h, p: PIN) is (
        result
    )
