import asyncio
import threading
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.config import PrinterConfig
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Printer
from filament_tracker.printer.link import LinkState, LinkStatus
from filament_tracker.printer.manager import PrinterManager, sync_printers


def config(serial: str = "01P00A1", **fields: Any) -> PrinterConfig:
    values = {"name": "P1S", "host": "192.168.1.40", "serial": serial, "access_code": "x"}
    return PrinterConfig(**(values | fields))


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


class FakeLink:
    """Runs until cancelled, recording that it ran on another thread."""

    def __init__(self, cfg: PrinterConfig, printer_id: int, sessions: object) -> None:
        self.config = cfg
        self.printer_id = printer_id
        self.status = LinkStatus(LinkState.STARTING, None)  # type: ignore[arg-type]
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.thread: str | None = None

    async def run(self) -> None:
        self.thread = threading.current_thread().name
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


def test_sync_creates_and_updates_printers_by_serial(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        first = sync_printers(session, [config(), config("OTHER", name="Old")])
        second = sync_printers(session, [config("OTHER", name="New", host="proxy.lan", port=18883)])
        printers = session.scalars(select(Printer).order_by(Printer.id)).all()

    assert second == {"OTHER": first["OTHER"]}
    assert [(p.serial, p.name, p.host, p.port) for p in printers] == [
        ("01P00A1", "P1S", "192.168.1.40", 8883),
        ("OTHER", "New", "proxy.lan", 18883),
    ]


def test_sync_keeps_the_pin(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        ids = sync_printers(session, [config()])
        session.get_one(Printer, ids["01P00A1"]).cert_sha256 = "ab" * 32
        session.commit()
        sync_printers(session, [config(host="10.0.0.9")])
        assert session.get_one(Printer, ids["01P00A1"]).cert_sha256 == "ab" * 32


def test_links_run_on_their_own_thread_until_stopped(sessions: sessionmaker[Session]) -> None:
    manager = PrinterManager([config(), config("OTHER")], sessions, FakeLink)  # type: ignore[arg-type]
    manager.start()
    links: list[FakeLink] = list(manager.links.values())  # type: ignore[arg-type]
    assert all(link.started.wait(5) for link in links)

    manager.stop()

    assert all(link.cancelled.is_set() for link in links)
    assert {link.thread for link in links} == {"printer-links"}
    printer_id = links[0].printer_id
    assert manager.status(printer_id) is links[0].status
    assert manager.status(9999) is None


def test_stopping_right_after_starting_still_stops(sessions: sessionmaker[Session]) -> None:
    manager = PrinterManager([config()], sessions, FakeLink)  # type: ignore[arg-type]
    manager.start()
    manager.stop()

    assert manager._thread is not None and not manager._thread.is_alive()


def test_no_printers_means_no_thread(sessions: sessionmaker[Session]) -> None:
    manager = PrinterManager([], sessions)
    manager.start()
    manager.stop()

    assert manager.links == {}
    assert manager._thread is None
