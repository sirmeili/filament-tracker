import asyncio
import json
from pathlib import Path
from typing import Any

import aiomqtt
import pytest

from filament_tracker.simulator import fakeprinter
from filament_tracker.simulator.fakeprinter import FakePrinter, is_pushall

REPORTS = Path(__file__).parent / "reports"
PUSHALL = json.dumps({"pushing": {"sequence_id": "0", "command": "pushall"}})


class Message:
    def __init__(self, payload: object) -> None:
        self.payload = payload


class FakeBroker:
    """Records what the fake printer publishes; delivers requests to it."""

    def __init__(self, requests: list[object]) -> None:
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []
        self._requests = requests

    async def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    @property
    def messages(self) -> Any:
        async def deliver() -> Any:
            for request in self._requests:
                await asyncio.sleep(0)
                yield Message(request)

        return deliver()


async def no_wait(seconds: float) -> None:
    await asyncio.sleep(0)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (PUSHALL.encode(), True),
        (PUSHALL, True),
        ('{"pushing": {"command": "start"}}', False),
        ('{"print": {}}', False),
        ("[1]", False),
        ("not json", False),
        (7, False),
    ],
)
def test_is_pushall(payload: object, expected: bool) -> None:
    assert is_pushall(payload) is expected


def test_the_printer_publishes_its_report_changes_and_answers_pushall() -> None:
    printer = FakePrinter("FAKE01", "full", ["change-1", "change-2"], sleep=no_wait)
    broker = FakeBroker([b"{}", PUSHALL.encode()])

    asyncio.run(printer.play(broker))

    report = "device/FAKE01/report"
    assert broker.subscribed == ["device/FAKE01/request"]
    assert broker.published[0] == (report, "full")
    assert sorted(broker.published[1:]) == sorted(
        [(report, "change-1"), (report, "change-2"), (report, "full")]
    )


def test_main_needs_the_access_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(fakeprinter.ACCESS_CODE_ENV, raising=False)

    code = fakeprinter.main(["--serial", "FAKE01", "--report", str(REPORTS / "pushall.json")])

    assert code == 2
    assert "FT_ACCESS_CODE" in capsys.readouterr().err


def test_main_refuses_unreadable_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(fakeprinter.ACCESS_CODE_ENV, "code")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")

    code = fakeprinter.main(["--serial", "FAKE01", "--report", str(broken)])

    assert code == 2
    assert "Cannot read a report file" in capsys.readouterr().err


def test_main_reports_an_unreachable_broker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(fakeprinter.ACCESS_CODE_ENV, "code")

    async def fail(args: object, access_code: str) -> None:
        raise aiomqtt.MqttError("refused")

    monkeypatch.setattr(fakeprinter, "_run", fail)
    code = fakeprinter.main(["--serial", "FAKE01", "--report", str(REPORTS / "pushall.json")])

    assert code == 1
    assert "Cannot reach the broker" in capsys.readouterr().err


def test_main_stops_quietly_on_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(fakeprinter.ACCESS_CODE_ENV, "code")

    async def interrupted(args: object, access_code: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(fakeprinter, "_run", interrupted)

    assert fakeprinter.main(["--serial", "S", "--report", str(REPORTS / "pushall.json")]) == 0


def test_main_runs_the_printer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(fakeprinter.ACCESS_CODE_ENV, "code")
    seen: dict[str, Any] = {}

    async def record(args: Any, access_code: str) -> None:
        seen.update(serial=args.serial, then=args.then, code=access_code)

    monkeypatch.setattr(fakeprinter, "_run", record)
    delta = str(REPORTS / "remain-delta.json")
    code = fakeprinter.main(
        ["--serial", "S", "--report", str(REPORTS / "pushall.json"), "--then", delta]
    )

    assert code == 0
    assert seen == {"serial": "S", "then": [Path(delta)], "code": "code"}
