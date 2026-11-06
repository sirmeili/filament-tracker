"""The printer link against a real MQTT broker (the fake printer in server/fakeprinter/).

Runs only when FT_FAKE_BROKER (host:port) is set, as it is in CI; see server/README.md
to run it locally. Everything else about the link is covered by test_link.py.
"""

import asyncio
import os
import threading
import time
from pathlib import Path

import aiomqtt
import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.config import PrinterConfig
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Printer, Spool
from filament_tracker.printer.link import LinkState, PrinterLink
from filament_tracker.printer.tls import fetch_fingerprint
from filament_tracker.simulator.fakeprinter import FakePrinter, _test_broker_tls

BROKER = os.environ.get("FT_FAKE_BROKER")
ACCESS_CODE = os.environ.get("FT_FAKE_BROKER_CODE", "fake-access-code")
REPORTS = Path(__file__).parent / "reports"
SERIAL = "FAKE01"

pytestmark = pytest.mark.skipif(not BROKER, reason="set FT_FAKE_BROKER to use the broker")


def host_port() -> tuple[str, int]:
    host, _, port = (BROKER or "").rpartition(":")
    return host, int(port)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def add_printer(sessions: sessionmaker[Session], pin: str | None = None) -> int:
    host, port = host_port()
    with sessions() as session:
        printer = Printer(name="Fake", serial=SERIAL, host=host, port=port, cert_sha256=pin)
        session.add(printer)
        session.commit()
        return printer.id


def run_link_until(link: PrinterLink, done: "callable[[], bool]", seconds: float = 20) -> None:  # type: ignore[valid-type]
    """Run the link on its own selector loop in a thread until `done()` or a timeout."""
    loop = asyncio.SelectorEventLoop()
    task_holder: dict[str, asyncio.Task[None]] = {}

    def run() -> None:
        asyncio.set_event_loop(loop)
        task_holder["task"] = loop.create_task(link.run())
        try:
            loop.run_until_complete(task_holder["task"])
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not done():
        time.sleep(0.2)
    loop.call_soon_threadsafe(lambda: task_holder["task"].cancel())
    thread.join(5)


def play_printer() -> threading.Thread:
    """The fake printer: publishes the full report and answers pushall for a while."""
    host, port = host_port()
    printer = FakePrinter(SERIAL, (REPORTS / "pushall.json").read_text(encoding="utf-8"))

    async def play() -> None:
        async with aiomqtt.Client(
            hostname=host,
            port=port,
            username="bblp",
            password=ACCESS_CODE,
            tls_context=_test_broker_tls(),
            tls_insecure=True,
        ) as client:
            await asyncio.wait_for(printer.play(client), timeout=25)

    def run() -> None:
        try:
            asyncio.run(play(), loop_factory=asyncio.SelectorEventLoop)
        except TimeoutError:
            pass

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def config() -> PrinterConfig:
    host, port = host_port()
    return PrinterConfig(name="Fake", host=host, port=port, serial=SERIAL, access_code=ACCESS_CODE)


def test_the_link_pins_the_broker_and_reads_the_ams(sessions: sessionmaker[Session]) -> None:
    printer_id = add_printer(sessions)
    play_printer()
    link = PrinterLink(config(), printer_id, sessions)

    def spools() -> int:
        with sessions() as session:
            return len(session.scalars(select(Spool)).all())

    run_link_until(link, lambda: spools() == 2)

    assert spools() == 2
    with sessions() as session:
        printer = session.get_one(Printer, printer_id)
        assert printer.cert_sha256 == fetch_fingerprint(*host_port())
        assert printer.last_report_at is not None


def test_a_different_certificate_is_refused(sessions: sessionmaker[Session]) -> None:
    printer_id = add_printer(sessions, pin="0" * 64)
    link = PrinterLink(config(), printer_id, sessions)

    run_link_until(link, lambda: link.status.state is LinkState.PIN_MISMATCH, seconds=10)

    assert link.status.state is LinkState.PIN_MISMATCH
    assert link.status.presented_sha256 == fetch_fingerprint(*host_port())
