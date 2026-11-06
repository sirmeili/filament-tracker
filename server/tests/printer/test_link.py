import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiomqtt
import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.config import PrinterConfig
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Printer, Spool
from filament_tracker.printer import link as link_module
from filament_tracker.printer.link import (
    PUSHALL,
    LinkState,
    PrinterLink,
)
from filament_tracker.printer.tls import CertificateMismatchError, PinnedContext

REPORTS = Path(__file__).parent / "reports"
ACCESS_CODE = "secret-access-code-1234"
PIN = "ab" * 32
T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
CONFIG = PrinterConfig(
    name="P1S", host="192.168.1.40", port=8884, serial="01P00A000000001", access_code=ACCESS_CODE
)


def report(name: str) -> bytes:
    return (REPORTS / f"{name}.json").read_bytes()


class Stop(Exception):
    """Ends a link's run loop in a test."""


class FakeMessage:
    def __init__(self, payload: object) -> None:
        self.payload = payload


class FakeClient:
    """Plays one MQTT session: delivers the queued payloads, then disconnects."""

    def __init__(self, payloads: list[object], kwargs: dict[str, Any]) -> None:
        self.kwargs = kwargs
        self.subscribed: list[str] = []
        self.published: list[tuple[str, str]] = []
        self._payloads = payloads

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
        async def deliver() -> Any:
            await asyncio.sleep(0)  # let the pushall task run first
            for payload in self._payloads:
                yield FakeMessage(payload)
            raise aiomqtt.MqttError("disconnected")

        return deliver()


class Harness:
    """A link with fakes for the network, the clock and sleeping."""

    def __init__(self, sessions: sessionmaker[Session], printer_id: int) -> None:
        self.sessions = sessions
        self.sessions_plan: list[list[object] | BaseException] = []
        self.clients: list[FakeClient] = []
        self.fetches = 0
        self.sleeps: list[float] = []
        self.now = T0
        self.max_sleeps = 1
        self.link = PrinterLink(
            CONFIG,
            printer_id,
            sessions,
            client_factory=self.client,
            fetch=self.fetch,
            sleep=self.sleep,
            clock=lambda: self.now,
        )

    def client(self, **kwargs: Any) -> FakeClient:
        plan = self.sessions_plan.pop(0) if self.sessions_plan else []
        if isinstance(plan, BaseException):
            raise plan
        client = FakeClient(plan, kwargs)
        self.clients.append(client)
        return client

    def fetch(self, host: str, port: int) -> str:
        assert (host, port) == (CONFIG.host, CONFIG.port)
        self.fetches += 1
        return PIN

    async def sleep(self, seconds: float) -> None:
        if seconds == PUSHALL_SECONDS:
            await asyncio.Event().wait()  # the pushall timer: wait until cancelled
        self.sleeps.append(seconds)
        if len(self.sleeps) >= self.max_sleeps:
            raise Stop

    def run(self) -> None:
        with pytest.raises(Stop):
            asyncio.run(self.link.run())


PUSHALL_SECONDS = link_module.PUSHALL_EVERY.total_seconds()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def printer_id(sessions: sessionmaker[Session]) -> int:
    with sessions() as session:
        printer = Printer(name="P1S", serial=CONFIG.serial, host=CONFIG.host, port=CONFIG.port)
        session.add(printer)
        session.commit()
        return printer.id


@pytest.fixture
def harness(sessions: sessionmaker[Session], printer_id: int) -> Harness:
    return Harness(sessions, printer_id)


def stored(harness: Harness) -> Printer:
    with harness.sessions() as session:
        printer = session.get_one(Printer, harness.link.printer_id)
        session.expunge(printer)
        return printer


def spool_count(harness: Harness) -> int:
    with harness.sessions() as session:
        return len(session.scalars(select(Spool)).all())


def test_first_connect_pins_the_certificate_then_reads_reports(harness: Harness) -> None:
    harness.sessions_plan = [[report("pushall")]]

    harness.run()

    client = harness.clients[0]
    assert client.kwargs["hostname"] == CONFIG.host
    assert client.kwargs["port"] == 8884
    assert client.kwargs["username"] == "bblp"
    assert client.kwargs["password"] == ACCESS_CODE
    assert client.kwargs["tls_insecure"] is True
    context = client.kwargs["tls_context"]
    assert isinstance(context, PinnedContext) and context.pinned_sha256 == PIN
    assert client.subscribed == [f"device/{CONFIG.serial}/report"]
    assert client.published == [(f"device/{CONFIG.serial}/request", json.dumps(PUSHALL))]
    printer = stored(harness)
    assert (printer.cert_sha256, printer.last_report_at) == (PIN, T0)
    assert spool_count(harness) == 2
    assert harness.link.status.state is LinkState.DISCONNECTED


def test_a_stored_pin_is_used_without_fetching(harness: Harness) -> None:
    with harness.sessions() as session:
        session.get_one(Printer, harness.link.printer_id).cert_sha256 = "cd" * 32
        session.commit()

    harness.run()

    assert harness.fetches == 0
    assert harness.clients[0].kwargs["tls_context"].pinned_sha256 == "cd" * 32


def test_a_pin_mismatch_is_reported_and_retried(harness: Harness) -> None:
    mismatch = aiomqtt.MqttError("handshake failed")
    mismatch.__cause__ = CertificateMismatchError("ef" * 32)
    harness.sessions_plan = [mismatch]

    harness.run()

    status = harness.link.status
    assert (status.state, status.presented_sha256) == (LinkState.PIN_MISMATCH, "ef" * 32)


def test_failures_back_off_up_to_a_minute(harness: Harness) -> None:
    harness.sessions_plan = [OSError("refused")] * 8
    harness.max_sleeps = 8

    harness.run()

    assert harness.sleeps == [1, 2, 4, 8, 16, 32, 60, 60]
    assert harness.link.status.state is LinkState.DISCONNECTED


def test_a_session_that_connected_resets_the_backoff(harness: Harness) -> None:
    harness.sessions_plan = [OSError("refused"), OSError("refused"), []]
    harness.max_sleeps = 3

    harness.run()

    assert harness.sleeps == [1, 2, 1]


def test_unchanged_and_unusable_reports_write_nothing(harness: Harness) -> None:
    link = harness.link
    link.handle(report("pushall"))
    harness.now = T0 + timedelta(seconds=10)

    for payload in [report("pushall"), report("no-ams"), b"not json", 42, b"{" * 1_000_001]:
        link.handle(payload)

    assert stored(harness).last_report_at == T0
    assert spool_count(harness) == 2


def test_last_report_is_written_at_most_once_a_minute(harness: Harness) -> None:
    link = harness.link
    link.handle(report("no-ams"))
    harness.now = T0 + timedelta(seconds=59)
    link.handle(report("no-ams"))
    assert stored(harness).last_report_at == T0

    harness.now = T0 + timedelta(minutes=1)
    link.handle(report("no-ams").decode())
    assert stored(harness).last_report_at == T0 + timedelta(minutes=1)


def test_a_change_is_ingested(harness: Harness) -> None:
    link = harness.link
    link.handle(report("pushall"))
    link.handle(report("remain-delta"))

    with harness.sessions() as session:
        remaining = session.scalars(select(Spool.remaining_pct).order_by(Spool.id)).all()
    assert remaining == [80, 0]


def test_a_failing_report_is_logged_and_the_link_carries_on(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*args: object) -> None:
        raise RuntimeError("database is locked")

    monkeypatch.setattr(link_module, "ingest", broken)
    harness.sessions_plan = [[report("pushall")]]

    harness.run()

    assert "could not apply a report" in caplog.text
    assert harness.link.status.state is LinkState.DISCONNECTED


def test_the_access_code_is_never_logged(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness.sessions_plan = [OSError("refused"), [report("pushall"), b"bad"]]
    harness.max_sleeps = 2

    harness.run()

    assert caplog.text
    assert ACCESS_CODE not in caplog.text
    assert ACCESS_CODE not in repr(CONFIG)
