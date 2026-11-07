from typing import Any

import aiomqtt
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode
from pydantic import SecretStr

from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.check import CheckResult, check_broker, check_rest
from filament_tracker.ha.rest import HaRestError, Problem

BROKER = BrokerConfig("broker.local", 1883, False, "user", SecretStr("broker-pass"))


class FakeClient:
    """Stands in for aiomqtt.Client: records how it was made, then connects or fails."""

    made: list[dict[str, Any]] = []

    def __init__(self, fail: BaseException | None = None, **kwargs: Any) -> None:
        self.fail = fail
        FakeClient.made.append(kwargs)

    async def __aenter__(self) -> "FakeClient":
        if self.fail is not None:
            raise self.fail
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def factory(fail: BaseException | None = None):  # noqa: ANN201
    return lambda **kwargs: FakeClient(fail, **kwargs)


def test_nothing_to_try_without_a_broker() -> None:
    assert check_broker(None) is CheckResult.OFF


def test_connects_once_with_the_settings() -> None:
    FakeClient.made = []
    assert check_broker(BROKER, factory()) is CheckResult.OK
    made = FakeClient.made[0]
    assert (made["hostname"], made["port"], made["username"]) == ("broker.local", 1883, "user")
    assert made["password"] == "broker-pass"  # noqa: S105 - test value
    assert made["tls_context"] is None


@pytest.mark.parametrize(
    ("error", "result"),
    [
        (aiomqtt.MqttCodeError(5, "not authorised"), CheckResult.REFUSED),
        (aiomqtt.MqttCodeError(4), CheckResult.REFUSED),
        (
            aiomqtt.MqttCodeError(ReasonCode(PacketTypes.CONNACK, identifier=135)),
            CheckResult.REFUSED,
        ),
        (aiomqtt.MqttCodeError(2), CheckResult.ERROR),
        (aiomqtt.MqttCodeError(None), CheckResult.ERROR),
        (aiomqtt.MqttError("gone"), CheckResult.UNREACHABLE),
        (OSError("no route"), CheckResult.UNREACHABLE),
        (TimeoutError(), CheckResult.UNREACHABLE),
    ],
)
def test_failures_become_categories(error: BaseException, result: CheckResult) -> None:
    assert check_broker(BROKER, factory(error)) is result


class FakeRest:
    def __init__(self, problem: Problem | None = None) -> None:
        self.problem = problem

    def check(self) -> None:
        if self.problem is not None:
            raise HaRestError(self.problem, 500)


@pytest.mark.parametrize(
    ("problem", "result"),
    [
        (None, CheckResult.OK),
        (Problem.UNREACHABLE, CheckResult.UNREACHABLE),
        (Problem.REFUSED, CheckResult.REFUSED),
        (Problem.ERROR, CheckResult.ERROR),
    ],
)
def test_home_assistant_answers_become_categories(
    problem: Problem | None, result: CheckResult
) -> None:
    assert check_rest(FakeRest(problem)) is result  # type: ignore[arg-type]


def test_nothing_to_try_without_home_assistant() -> None:
    assert check_rest(None) is CheckResult.OFF
