"""Fire Home Assistant events for automations (docs/SPEC.md, Home Assistant).

- `filament_tracker_spool_received`, `_spool_opened` and `_spool_emptied`, for each such
  event recorded while the server runs, from any source (scanner, phone, web app, printer);
- `filament_tracker_low_stock`, when a product goes from not low to low.

Every few seconds the sender reads what is new and fires it through Home Assistant's REST
API. Only events recorded after the server started are fired, so a restart never replays
history into automations. An event undone before it is fired is skipped; one undone later
stays fired. A failed request is retried a few times and then dropped with a warning.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from filament_tracker.db.models import Event, Spool
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import EventType
from filament_tracker.ha.rest import HaRest, HaRestError, Problem
from filament_tracker.ha.snapshot import ProductState, take_snapshot

logger = logging.getLogger(__name__)

POLL_SECONDS = 5.0
# How far back each poll looks, so an event committed a little after it was stamped is
# still seen. Events already fired are remembered for this long.
LOOKBACK = timedelta(minutes=2)
RETRIES = (1.0, 4.0, 15.0)
STOP_TIMEOUT = 5.0

SPOOL_EVENTS = {
    EventType.RECEIVED: "filament_tracker_spool_received",
    EventType.OPENED: "filament_tracker_spool_opened",
    EventType.EMPTY: "filament_tracker_spool_emptied",
}
LOW_STOCK_EVENT = "filament_tracker_low_stock"


class EventsStatus(StrEnum):
    OFF = "off"
    READY = "ready"  # the last request worked, or nothing has been sent yet
    FAILING = "failing"  # the last request failed after its retries


@dataclass(frozen=True)
class HaEvent:
    event_type: str
    data: dict[str, Any]


def _color(rgba: str) -> str:
    return f"#{rgba[:6].upper()}"


def spool_event(event: Event) -> HaEvent:
    spool: Spool = event.spool
    product = spool.product
    return HaEvent(
        SPOOL_EVENTS[event.type],
        {
            "event_id": str(event.id),
            "spool_id": spool.id,
            "product_id": product.id,
            "product": product.display_name,
            "filament_type": product.filament_type,
            "color": _color(product.color_rgba),
            "state": spool.state.value if spool.state else None,
            "source": event.source.value,
            "flagged": event.flagged,
            "occurred_at": event.occurred_at.isoformat(),
        },
    )


def low_stock_event(product: ProductState) -> HaEvent:
    return HaEvent(
        LOW_STOCK_EVENT,
        {
            "product_id": product.id,
            "product": product.name,
            "filament_type": product.filament_type,
            "color": _color(product.color_rgba),
            "sealed": product.sealed,
            "threshold": product.low_stock_threshold,
        },
    )


@dataclass
class EventFeed:
    """What is new since the last poll. Not thread-safe; one sender uses it."""

    started_at: datetime
    fired: dict[UUID, datetime] = field(default_factory=dict)
    low: set[int] | None = None  # products low at the last poll; None before the first

    def poll(self, session: Session, now: datetime) -> list[HaEvent]:
        out = self._spool_events(session, now)
        snapshot = take_snapshot(session)
        low_now = {p.id: p for p in snapshot.low_stock}
        if self.low is not None:
            out += [low_stock_event(p) for i, p in low_now.items() if i not in self.low]
        self.low = set(low_now)
        return out

    def _spool_events(self, session: Session, now: datetime) -> list[HaEvent]:
        since = max(self.started_at, now - LOOKBACK)
        self.fired = {i: at for i, at in self.fired.items() if at >= now - LOOKBACK}
        query = (
            select(Event)
            .where(
                Event.recorded_at >= since,
                Event.type.in_(list(SPOOL_EVENTS)),
                Event.reverted_by.is_(None),
            )
            .options(selectinload(Event.spool).selectinload(Spool.product))
            .order_by(Event.recorded_at, Event.id)
        )
        out = []
        for event in session.scalars(query):
            if event.id in self.fired:
                continue
            self.fired[event.id] = event.recorded_at
            out.append(spool_event(event))
        return out


class HaEventSender:
    def __init__(
        self,
        rest: HaRest | None,
        session_factory: sessionmaker[Session],
        *,
        poll_seconds: float = POLL_SECONDS,
        retries: tuple[float, ...] = RETRIES,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.rest = rest
        self._sessions = session_factory
        self._poll_seconds = poll_seconds
        self._retries = retries
        self._clock = clock
        self.status = EventsStatus.OFF if rest is None else EventsStatus.READY
        self.feed = EventFeed(started_at=clock())
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.rest is None:
            return
        self.feed = EventFeed(started_at=self._clock())
        self._thread = threading.Thread(target=self.run, name="ha-events", daemon=True)
        self._thread.start()
        logger.info("firing Home Assistant events at %s", self.rest.url)

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT)

    def run(self) -> None:
        while not self._stopping.is_set():
            self.step()
            self._stopping.wait(self._poll_seconds)

    def step(self) -> None:
        """One poll: read what is new and fire it."""
        try:
            with self._sessions() as session:
                events = self.feed.poll(session, self._clock())
        except Exception:
            logger.exception("Home Assistant events: could not read the database")
            return
        for event in events:
            if self._stopping.is_set():
                return
            self._send(event)

    def _send(self, event: HaEvent) -> None:
        assert self.rest is not None  # noqa: S101 - only started with a REST client
        for attempt, delay in enumerate((0.0, *self._retries)):
            if delay and self._stopping.wait(delay):
                return
            try:
                self.rest.fire(event.event_type, event.data)
            except HaRestError as error:
                if error.problem is Problem.REFUSED or attempt == len(self._retries):
                    self.status = EventsStatus.FAILING
                    logger.warning(
                        "Home Assistant events: %s not sent: %s", event.event_type, error
                    )
                    return
                continue
            self.status = EventsStatus.READY
            return
