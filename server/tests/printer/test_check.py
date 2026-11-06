import asyncio
import json
from pathlib import Path
from typing import Any

import aiomqtt
import pytest
from pydantic import SecretStr

from filament_tracker.config import PrinterConfig, Settings
from filament_tracker.decoder.synthetic import SyntheticTag
from filament_tracker.printer import check
from filament_tracker.printer.check import Capture, TagIds, describe, keep, redact

REPORTS = Path(__file__).parent / "reports"
SERIAL = "01P00A000000001"
TRAY = "A1B2C3D4E5F60718293A4B5C6D7E8F90"


def config(name: str = "P1S") -> PrinterConfig:
    return PrinterConfig(
        name=name, host="192.168.1.40", serial=SERIAL, access_code=SecretStr("12345678")
    )


def report(trays: list[dict[str, Any]], unit: str = "0") -> str:
    return json.dumps(
        {"print": {"command": "push_status", "ams": {"ams": [{"id": unit, "tray": trays}]}}}
    )


def capture_of(*payloads: object) -> Capture:
    capture = Capture()
    for payload in payloads:
        capture.add(payload)
    return capture


def test_capture_skips_what_is_not_a_report() -> None:
    capture = capture_of(b"not json", 7, "x" * (check.MAX_PAYLOAD + 1), "[1]", report([]).encode())

    assert len(capture.messages) == 2
    assert capture.raw == {}


def test_capture_keeps_the_raw_fields_of_each_tray() -> None:
    capture = capture_of(
        report(
            [{"id": "0", "tray_type": "PLA", "tag_uid": "AABBCCDD11223344"}, "bad", {"id": "x"}]
        ),
        report([{"id": "0", "remain": 40}]),
    )

    assert capture.raw == {
        (0, 0): {"id": "0", "tray_type": "PLA", "tag_uid": "AABBCCDD11223344", "remain": 40}
    }


def test_describe_without_an_ams() -> None:
    assert describe(Capture(), []) == ["No AMS in the report."]


def test_describe_shows_each_slot_and_which_tags_match() -> None:
    capture = capture_of(
        report(
            [
                {
                    "id": "0",
                    "tray_type": "PLA",
                    "tray_info_idx": "GFA00",
                    "remain": 37,
                    "tray_uuid": TRAY,
                    "tag_uid": "AABBCCDD11223344",
                },
                {"id": "1"},
                {
                    "id": "2",
                    "tray_type": "PETG",
                    "remain": -1,
                    "tray_uuid": "0" * 32,
                    "tag_uid": "",
                },
            ]
        )
    )
    tags = [
        TagIds("tag 1 (PLA Basic, 000000FF)", "AABBCCDD11223344", TRAY),
        TagIds("tag 2 (PLA Basic, 000000FF)", "01020304", "F" * 32),
    ]

    lines = describe(capture, tags)

    assert lines == [
        "AMS 1, slot 1: PLA / - / material GFA00 / color - / remain 37 -> 37%",
        "    tray_uuid: 32 hex digits; tag_uid: 16 hex digits",
        "    tag 1 (PLA Basic, 000000FF): tray_uuid equals the tag's tray UID",
        "    tag 1 (PLA Basic, 000000FF): tag_uid equals the tag's UID",
        "AMS 1, slot 2: empty",
        "AMS 1, slot 3: PETG / - / material - / color - / remain -1 -> unknown",
        "    tray_uuid: all zeros; tag_uid: missing",
        "tag 2 (PLA Basic, 000000FF): matches no slot",
    ]
    assert not any(TRAY in line for line in lines)


def test_redact_hides_identifiers_but_keeps_them_comparable() -> None:
    message = {
        "print": {
            "ams": {
                "ams": [
                    {
                        "ams_id": "X1",
                        "chip_id": "",
                        "tray": [{"tray_uuid": TRAY}, {"tray_uuid": TRAY}],
                    }
                ]
            },
            "note": f"{SERIAL} at 192.168.1.40",
            "remain": 5,
        }
    }

    out = redact(message, SERIAL, b"key")
    unit = out["print"]["ams"]["ams"][0]

    assert unit["ams_id"].startswith("redacted-")
    assert unit["chip_id"] == ""
    assert unit["tray"][0] == unit["tray"][1] != {"tray_uuid": TRAY}
    assert out["print"]["note"] == "SERIAL at 192.0.2.0"
    assert out["print"]["remain"] == 5
    assert redact("plain", "", b"key") == "plain"


def test_keep_takes_only_the_ams_parts() -> None:
    assert keep({"print": {"command": "push_status", "ams": {}, "net": {"ip": 1}}}) == {
        "print": {"command": "push_status", "ams": {}}
    }
    assert keep({"print": {"command": "push_status", "wifi_signal": "-40dBm"}}) is None
    assert keep({"info": {}}) is None
    assert keep([1]) is None


def test_save_writes_redacted_lines(tmp_path: Path) -> None:
    full = (REPORTS / "p1s-pushall.json").read_text(encoding="utf-8")
    capture = capture_of(
        full, json.dumps({"print": {"command": "push_status", "nozzle_temper": 20}})
    )
    path = tmp_path / "out" / "capture.jsonl"

    check.save(capture, path, SERIAL)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "F1355C00D33B76E627CEE268E882FDD8" not in lines[0]
    assert json.loads(lines[0])["print"]["ams"]["ams"][1]["id"] == "128"


def write_dump(directory: Path, tag: SyntheticTag) -> Path:
    path = directory / "tag.bin"
    path.write_bytes(tag.image())
    return path


def test_load_tags_labels_by_position_and_product(tmp_path: Path) -> None:
    tag = SyntheticTag(detailed_filament_type="PETG HF", color_rgba="515151FF")
    loaded = check.load_tags([write_dump(tmp_path, tag)])

    assert loaded == [
        TagIds("tag 1 (PETG HF, 515151FF)", tag.tag_uid.hex().upper(), tag.tray_uid.hex().upper())
    ]


class FakeClient:
    def __init__(self, payloads: list[str], **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.payloads = payloads
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    @property
    def messages(self) -> Any:
        payloads = self.payloads

        async def deliver() -> Any:
            for payload in payloads:
                yield type("Message", (), {"payload": payload})()
            await asyncio.sleep(10)

        return deliver()


def test_collect_pins_asks_for_pushall_and_listens(monkeypatch: pytest.MonkeyPatch) -> None:
    clients: list[FakeClient] = []
    ticks = iter([0.0, 0.0, 5.0])

    def factory(**kwargs: Any) -> FakeClient:
        clients.append(
            FakeClient([report([{"id": "0", "tray_type": "PLA"}]), "{}", "{}"], **kwargs)
        )
        return clients[0]

    pin, capture = asyncio.run(
        check.collect(
            config(),
            2,
            client_factory=factory,
            fetch=lambda h, p: "ab" * 32,
            clock=lambda: next(ticks),
        )
    )

    client = clients[0]
    assert pin == "ab" * 32
    assert client.kwargs["username"] == "bblp"
    assert client.kwargs["password"] == "12345678"  # noqa: S105 - test value
    assert client.kwargs["tls_insecure"] is True
    assert client.subscribed == [f"device/{SERIAL}/report"]
    assert client.published[0][0] == f"device/{SERIAL}/request"
    assert "pushall" in client.published[0][1]
    assert len(capture.messages) == 2


def test_collect_stops_at_the_timeout() -> None:
    def factory(**kwargs: Any) -> FakeClient:
        return FakeClient([], **kwargs)

    _, capture = asyncio.run(
        check.collect(config(), 0.05, client_factory=factory, fetch=lambda h, p: "ab" * 32)
    )

    assert capture.messages == []


def settings(*printers: PrinterConfig) -> Settings:
    return Settings(printers=list(printers), _env_file=None)  # type: ignore[call-arg]


def test_main_needs_the_printer(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["check"], settings=settings()) == 2
    assert check.main(["check", "--name", "X1C"], settings=settings(config())) == 2
    assert "No such printer" in capsys.readouterr().err


def test_main_refuses_a_bad_dump(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"x")

    assert check.main(["check", "--dump", str(bad)], settings=settings(config())) == 2
    assert "Cannot read a dump" in capsys.readouterr().err


def test_main_reports_a_failed_connection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fail(*args: object) -> None:
        raise aiomqtt.MqttError("refused")

    monkeypatch.setattr(check, "collect", fail)

    assert check.main(["check"], settings=settings(config())) == 1
    assert "Cannot connect to P1S" in capsys.readouterr().err


def test_main_prints_the_slots_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tag = SyntheticTag()
    tray = tag.tray_uid.hex().upper()

    async def collected(printer: PrinterConfig, seconds: float) -> tuple[str, Capture]:
        assert (printer.name, seconds) == ("Second", 15.0)
        return "cd" * 32, capture_of(
            report([{"id": "0", "tray_type": "PLA", "tray_uuid": tray}], unit="128")
        )

    monkeypatch.setattr(check, "collect", collected)
    out = tmp_path / "capture.jsonl"
    argv = [
        "check",
        "--name",
        "Second",
        "--dump",
        str(write_dump(tmp_path, tag)),
        "--save",
        str(out),
    ]

    second = PrinterConfig(name="Second", host="h", serial="S2", access_code=SecretStr("c"))
    assert check.main(argv, settings=settings(config(), second)) == 0

    printed = capsys.readouterr().out
    assert "Second: certificate cdcdcdcdcdcdcdcd..., 1 messages" in printed
    assert "AMS HT 1: PLA" in printed
    assert "tray_uuid equals the tag's tray UID" in printed
    assert tray not in printed
    assert tray not in out.read_text(encoding="utf-8")
