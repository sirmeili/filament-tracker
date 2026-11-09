import asyncio
import logging
import threading
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.config import PrinterConfig
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Printer, SeededPrinter
from filament_tracker.printer import manager as manager_module
from filament_tracker.printer.link import LinkState, LinkStatus
from filament_tracker.printer.manager import PrinterManager
from filament_tracker.services.printers import (
    access_code,
    access_code_unreadable,
    printer_config,
    seal_access_code,
    seed_printers,
)

BOX = SecretBox(bytes(range(32)))
CODE = "code1234"  # test value


def config(serial: str = "01P00A1", **fields: Any) -> PrinterConfig:
    values = {"name": "P1S", "host": "192.168.1.40", "serial": serial, "access_code": CODE}
    return PrinterConfig(**(values | fields))


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def add(sessions: sessionmaker[Session], serial: str = "01P00A1", code: str | None = CODE) -> int:
    with sessions() as session:
        printer = Printer(name="P1S", host="192.168.1.40", port=8883, serial=serial)
        session.add(printer)
        session.flush()
        if code is not None:
            seal_access_code(BOX, printer, code)
        session.commit()
        return printer.id


class FakeLink:
    """Runs until cancelled, recording that it ran on another thread."""

    made: list["FakeLink"] = []

    def __init__(self, cfg: PrinterConfig, printer_id: int, sessions: object) -> None:
        self.config = cfg
        self.printer_id = printer_id
        self.status = LinkStatus(LinkState.STARTING, None)  # type: ignore[arg-type]
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.thread: str | None = None
        FakeLink.made.append(self)

    async def run(self) -> None:
        self.thread = threading.current_thread().name
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled.set()


# --- seeding from PRINTERS and the sealed access code --------------------------------


def test_printers_are_seeded_once(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        assert seed_printers(session, BOX, [config(), config("OTHER", name="Other")]) == 2
        printer = session.scalars(select(Printer).where(Printer.serial == "01P00A1")).one()
        assert printer.access_code is not None and CODE not in printer.access_code
        assert access_code(BOX, printer).get_secret_value() == CODE  # type: ignore[union-attr]

        # Edited in the app, then the server restarts with the same PRINTERS: kept as edited.
        printer.name = "Renamed"
        session.delete(session.scalars(select(Printer).where(Printer.serial == "OTHER")).one())
        session.commit()
        assert seed_printers(session, BOX, [config(), config("OTHER")]) == 0
        assert [p.name for p in session.scalars(select(Printer))] == ["Renamed"]


def test_a_printer_from_before_gets_its_access_code(sessions: sessionmaker[Session]) -> None:
    printer_id = add(sessions, code=None)
    with sessions() as session:
        session.get_one(Printer, printer_id).cert_sha256 = "ab" * 32
        session.commit()
        seed_printers(session, BOX, [config(host="10.0.0.9")])
        printer = session.get_one(Printer, printer_id)
        assert (printer.host, printer.cert_sha256) == ("10.0.0.9", "ab" * 32)
        assert printer_config(BOX, printer) == config(host="10.0.0.9")
        assert session.scalars(select(SeededPrinter.serial)).all() == ["01P00A1"]


def test_an_access_code_is_bound_to_its_printer(sessions: sessionmaker[Session]) -> None:
    first, second = add(sessions), add(sessions, "OTHER", code=None)
    with sessions() as session:
        a, b = session.get_one(Printer, first), session.get_one(Printer, second)
        b.access_code = a.access_code  # copied to another row: cannot be opened there
        assert access_code(BOX, b) is None
        assert access_code_unreadable(BOX, b)
        assert printer_config(BOX, b) is None
        assert not access_code_unreadable(BOX, a)
        other_key = SecretBox(bytes(32))
        assert access_code(other_key, a) is None


def test_unusable_saved_values_do_not_connect(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    printer_id = add(sessions)
    with sessions() as session:
        printer = session.get_one(Printer, printer_id)
        printer.serial = "bad serial!"
        assert printer_config(BOX, printer) is None
    assert CODE not in caplog.text


# --- the links ------------------------------------------------------------------------


def test_links_run_on_their_own_thread_until_stopped(sessions: sessionmaker[Session]) -> None:
    add(sessions), add(sessions, "OTHER"), add(sessions, "NOCODE", code=None)
    manager = PrinterManager(sessions, BOX, FakeLink)  # type: ignore[arg-type]
    manager.start()
    links: list[FakeLink] = list(manager.links.values())  # type: ignore[arg-type]
    assert len(links) == 2  # the printer without an access code is not connected
    assert all(link.started.wait(5) for link in links)
    assert links[0].config.access_code.get_secret_value() == CODE

    manager.stop()

    assert all(link.cancelled.is_set() for link in links)
    assert {link.thread for link in links} == {"printer-links"}
    printer_id = links[0].printer_id
    assert manager.status(printer_id) is links[0].status
    assert manager.status(9999) is None
    manager.stop()  # twice is harmless
    manager.reload(printer_id)  # after stopping: nothing happens


def test_reload_restarts_or_stops_one_printer(sessions: sessionmaker[Session]) -> None:
    first, second = add(sessions), add(sessions, "OTHER")
    manager = PrinterManager(sessions, BOX, FakeLink)  # type: ignore[arg-type]
    manager.start()
    try:
        old, other = manager.links[first], manager.links[second]
        assert old.started.wait(5)  # type: ignore[attr-defined]
        with sessions() as session:
            session.get_one(Printer, first).host = "10.0.0.9"
            session.commit()

        manager.reload(first)

        new = manager.links[first]
        assert new is not old and new.config.host == "10.0.0.9"
        assert old.cancelled.is_set()  # type: ignore[attr-defined]
        assert manager.links[second] is other and not other.cancelled.is_set()  # type: ignore[attr-defined]

        with sessions() as session:
            session.delete(session.get_one(Printer, first))
            session.commit()
        manager.reload(first)
        assert first not in manager.links
        assert manager.status(first) is None

        third = add(sessions, "NEW")
        manager.reload(third)
        assert manager.links[third].started.wait(5)  # type: ignore[attr-defined]
    finally:
        manager.stop()


def test_no_printers_still_starts_for_later(sessions: sessionmaker[Session]) -> None:
    manager = PrinterManager(sessions, BOX, FakeLink)  # type: ignore[arg-type]
    manager.start()
    try:
        assert manager.links == {}
        printer_id = add(sessions)
        manager.reload(printer_id)
        assert manager.links[printer_id].started.wait(5)  # type: ignore[attr-defined]
    finally:
        manager.stop()
    assert manager._thread is not None and not manager._thread.is_alive()


def test_reload_before_start_does_nothing(sessions: sessionmaker[Session]) -> None:
    manager = PrinterManager(sessions, BOX, FakeLink)  # type: ignore[arg-type]
    manager.reload(add(sessions))
    manager.stop()
    assert manager.links == {}


class Stubborn(FakeLink):
    """Takes a while to stop when cancelled."""

    async def run(self) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.5)


@pytest.mark.parametrize("step", ["reload", "stop"])
def test_slow_stops_are_logged_not_raised(
    sessions: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    step: str,
) -> None:
    printer_id = add(sessions)
    monkeypatch.setattr(manager_module, "STOP_TIMEOUT", 0.05)
    manager = PrinterManager(sessions, BOX, Stubborn)  # type: ignore[arg-type]
    caplog.set_level(logging.WARNING)
    manager.start()
    assert manager.links[printer_id].started.wait(5)  # type: ignore[attr-defined]
    if step == "reload":
        manager.reload(printer_id)
        assert "the old link did not stop in time" in caplog.text
    manager.stop()
    if step == "stop":
        assert "printer links did not stop in time" in caplog.text
