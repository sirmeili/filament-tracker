"""Run every configured printer's link in a background thread.

The links run on their own selector event loop in one thread, apart from the web server's
loop: aiomqtt needs a selector loop (Windows' default loop is not one), and a slow printer
can never hold up a web request.
"""

import asyncio
import logging
import threading
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.config import PrinterConfig
from filament_tracker.db.models import Printer
from filament_tracker.printer.link import LinkStatus, PrinterLink

logger = logging.getLogger(__name__)

STOP_TIMEOUT = 5.0

LinkFactory = Callable[[PrinterConfig, int, sessionmaker[Session]], PrinterLink]


def sync_printers(session: Session, configs: list[PrinterConfig]) -> dict[str, int]:
    """Create or update a `printer` row for each configured printer, by serial. Rows for
    printers no longer configured are kept, for their history. Returns serial -> id."""
    ids: dict[str, int] = {}
    for config in configs:
        printer = session.scalar(select(Printer).where(Printer.serial == config.serial))
        if printer is None:
            printer = Printer(serial=config.serial)
            session.add(printer)
        printer.name = config.name
        printer.host = config.host
        printer.port = config.port
        session.flush()
        ids[config.serial] = printer.id
    session.commit()
    return ids


class PrinterManager:
    def __init__(
        self,
        configs: list[PrinterConfig],
        session_factory: sessionmaker[Session],
        link_factory: LinkFactory = PrinterLink,
    ) -> None:
        self._configs = configs
        self._sessions = session_factory
        self._link_factory = link_factory
        self.links: dict[int, PrinterLink] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stopping: asyncio.Event | None = None

    def start(self) -> None:
        with self._sessions() as session:
            ids = sync_printers(session, self._configs)
        self.links = {
            ids[c.serial]: self._link_factory(c, ids[c.serial], self._sessions)
            for c in self._configs
        }
        if not self.links:
            return
        self._loop = asyncio.SelectorEventLoop()
        # Made here, so stop() works even before the thread starts waiting on it.
        self._stopping = asyncio.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(self._loop, self._stopping),
            name="printer-links",
            daemon=True,
        )
        self._thread.start()
        logger.info("watching %d printer(s)", len(self.links))

    def stop(self) -> None:
        if self._loop is None or self._thread is None:
            return
        loop, stopping = self._loop, self._stopping
        if stopping is not None:
            loop.call_soon_threadsafe(stopping.set)
        self._thread.join(STOP_TIMEOUT)

    def status(self, printer_id: int) -> LinkStatus | None:
        link = self.links.get(printer_id)
        return link.status if link else None

    def _run(self, loop: asyncio.AbstractEventLoop, stopping: asyncio.Event) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main(stopping))
        finally:
            loop.close()

    async def _main(self, stopping: asyncio.Event) -> None:
        tasks = [asyncio.create_task(link.run()) for link in self.links.values()]
        await stopping.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
