"""Run each saved printer's link in a background thread.

The links run on their own selector event loop in one thread, apart from the web server's
loop: aiomqtt needs a selector loop (Windows' default loop is not one), and a slow printer
can never hold up a web request. Saving or removing a printer on the Devices page calls
`reload`, which restarts (or stops) only that printer's link.
"""

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer
from filament_tracker.printer.link import LinkStatus, PrinterLink
from filament_tracker.services.printers import printer_config

logger = logging.getLogger(__name__)

STOP_TIMEOUT = 5.0

LinkFactory = Callable[[PrinterConfig, int, sessionmaker[Session]], PrinterLink]


class PrinterManager:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        box: SecretBox,
        link_factory: LinkFactory = PrinterLink,
    ) -> None:
        self._sessions = session_factory
        self._box = box
        self._link_factory = link_factory
        self.links: dict[int, PrinterLink] = {}
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        loop = asyncio.SelectorEventLoop()
        self._loop = loop
        self._thread = threading.Thread(
            target=self._run, args=(loop,), name="printer-links", daemon=True
        )
        self._thread.start()
        with self._sessions() as session:
            ids = list(session.scalars(select(Printer.id).order_by(Printer.id)))
        for printer_id in ids:
            self.reload(printer_id)
        logger.info("watching %d printer(s)", len(self.links))

    def reload(self, printer_id: int) -> None:
        """Start, restart or stop one printer's link to match what is saved: stopped if the
        printer is gone or has no usable access code."""
        with self._lock:
            if self._loop is None:
                return
            link = self._make(printer_id)
            future = asyncio.run_coroutine_threadsafe(self._swap(printer_id, link), self._loop)
            try:
                future.result(STOP_TIMEOUT)
            except (TimeoutError, concurrent.futures.TimeoutError):
                logger.warning("printer %s: the old link did not stop in time", printer_id)

    def stop(self) -> None:
        with self._lock:
            loop, thread = self._loop, self._thread
            if loop is None or thread is None:
                return
            future = asyncio.run_coroutine_threadsafe(self._stop_all(), loop)
            try:
                future.result(STOP_TIMEOUT)
            except (TimeoutError, concurrent.futures.TimeoutError):
                logger.warning("printer links did not stop in time")
            loop.call_soon_threadsafe(loop.stop)
            thread.join(STOP_TIMEOUT)
            self._loop = None

    def status(self, printer_id: int) -> LinkStatus | None:
        link = self.links.get(printer_id)
        return link.status if link else None

    def _make(self, printer_id: int) -> PrinterLink | None:
        with self._sessions() as session:
            printer = session.get(Printer, printer_id)
            config = printer_config(self._box, printer) if printer else None
        if config is None:
            return None
        return self._link_factory(config, printer_id, self._sessions)

    def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            loop.close()

    async def _swap(self, printer_id: int, link: PrinterLink | None) -> None:
        old = self._tasks.pop(printer_id, None)
        self.links.pop(printer_id, None)
        if old is not None:
            old.cancel()
            await asyncio.gather(old, return_exceptions=True)
        if link is not None:
            self.links[printer_id] = link
            self._tasks[printer_id] = asyncio.create_task(link.run())

    async def _stop_all(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
