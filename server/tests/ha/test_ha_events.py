import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from ha_helpers import add_product, add_spools
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import EventSource, EventType, SpoolState
from filament_tracker.ha.events import (
    LOOKBACK,
    EventFeed,
    EventsStatus,
    HaEvent,
    HaEventSender,
)
from filament_tracker.ha.rest import HaRest, HaRestError, Problem
from filament_tracker.services.events import append_event, revert_event

TOKEN = SecretStr("ha-long-lived-token")
T0 = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def record(session: Session, product: Product, event_type: EventType, **kw: Any) -> Spool:
    spool = kw.pop("spool", None) or Spool(product_id=product.id)
    if spool.id is None:
        session.add(spool)
        session.flush()
    append_event(session, spool, event_type, kw.pop("source", EventSource.SCANNER), T0, **kw)
    session.commit()
    return spool


class FakeRest(HaRest):
    """Records fired events; fails as told."""

    def __init__(self, failures: list[Problem] | None = None) -> None:
        super().__init__("http://ha.lan:8123", TOKEN)
        object.__setattr__(self, "sent", [])
        object.__setattr__(self, "failures", list(failures or []))

    def fire(self, event_type: str, data: dict[str, Any]) -> None:
        if self.failures:  # type: ignore[attr-defined]
            raise HaRestError(self.failures.pop(0), 500)  # type: ignore[attr-defined]
        self.sent.append((event_type, data))  # type: ignore[attr-defined]


def test_fires_each_spool_event_once_from_any_source(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        product = add_product(session)
        session.commit()
        feed = EventFeed(started_at=T0 - timedelta(days=1))
        assert feed.poll(session, datetime.now(UTC)) == []

        spool = record(session, product, EventType.RECEIVED)
        record(session, product, EventType.OPENED, spool=spool, source=EventSource.UI)
        record(session, product, EventType.EMPTY, spool=spool, source=EventSource.AMS)
        events = feed.poll(session, datetime.now(UTC))

        assert [e.event_type for e in events] == [
            "filament_tracker_spool_received",
            "filament_tracker_spool_opened",
            "filament_tracker_spool_emptied",
        ]
        assert events[1].data | {"event_id": "-", "occurred_at": "-"} == {
            "event_id": "-",
            "spool_id": spool.id,
            "product_id": product.id,
            "product": "Black PLA Basic",
            "filament_type": "PLA",
            "color": "#000000",
            "state": "empty",
            "source": "ui",
            "flagged": False,
            "occurred_at": "-",
        }
        assert feed.poll(session, datetime.now(UTC)) == []  # nothing new


def test_ignores_events_from_before_the_server_started(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        product = add_product(session)
        record(session, product, EventType.RECEIVED)
        feed = EventFeed(started_at=datetime.now(UTC) + timedelta(seconds=1))
        assert feed.poll(session, datetime.now(UTC)) == []


def test_skips_an_event_undone_before_it_was_fired(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        product = add_product(session)
        feed = EventFeed(started_at=T0 - timedelta(days=1))
        spool = record(session, product, EventType.RECEIVED)
        revert_event(session, spool.events[0], EventSource.UI, T0)
        session.commit()

        assert feed.poll(session, datetime.now(UTC)) == []


def test_forgets_fired_events_after_the_lookback(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        product = add_product(session)
        feed = EventFeed(started_at=T0 - timedelta(days=1))
        record(session, product, EventType.RECEIVED)
        now = datetime.now(UTC)
        assert len(feed.poll(session, now)) == 1
        assert len(feed.fired) == 1

        assert feed.poll(session, now + LOOKBACK + timedelta(seconds=1)) == []
        assert feed.fired == {}


def test_fires_low_stock_when_a_product_goes_low(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        black = add_product(session, low_stock_threshold=1)
        white = add_product(session, "White PETG", filament_type="PETG", color_rgba="ffffffff")
        add_spools(session, black, SpoolState.SEALED, 2)
        add_spools(session, white, SpoolState.SEALED, 1)
        white.low_stock_threshold = 1  # already low when the server starts
        session.commit()
        feed = EventFeed(started_at=datetime.now(UTC))
        assert feed.poll(session, datetime.now(UTC)) == []  # the first poll sets the baseline

        black.low_stock_threshold = 2
        session.commit()
        assert feed.poll(session, datetime.now(UTC)) == [
            HaEvent(
                "filament_tracker_low_stock",
                {
                    "product_id": black.id,
                    "product": "Black PLA Basic",
                    "filament_type": "PLA",
                    "color": "#000000",
                    "sealed": 2,
                    "threshold": 2,
                },
            )
        ]
        assert feed.poll(session, datetime.now(UTC)) == []  # still low: not again

        black.low_stock_threshold = 0
        session.commit()
        assert feed.poll(session, datetime.now(UTC)) == []  # recovered
        black.low_stock_threshold = 2
        session.commit()
        assert [e.data["product"] for e in feed.poll(session, datetime.now(UTC))] == [
            "Black PLA Basic"
        ]


def sender(sessions: sessionmaker[Session], rest: HaRest | None) -> HaEventSender:
    return HaEventSender(rest, sessions, poll_seconds=0.01, retries=(0.0, 0.0))


def test_sends_new_events(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest()
    events = sender(sessions, rest)
    events.feed = EventFeed(started_at=T0 - timedelta(days=1))
    with sessions() as session:
        record(session, add_product(session), EventType.RECEIVED)

    events.step()

    assert [t for t, _ in rest.sent] == ["filament_tracker_spool_received"]  # type: ignore[attr-defined]
    assert events.status is EventsStatus.READY


def test_retries_then_gives_up_with_a_warning(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    rest = FakeRest([Problem.UNREACHABLE] * 3)
    events = sender(sessions, rest)
    events.feed = EventFeed(started_at=T0 - timedelta(days=1))
    with sessions() as session:
        record(session, add_product(session), EventType.RECEIVED)

    with caplog.at_level(logging.WARNING):
        events.step()

    assert rest.sent == []  # type: ignore[attr-defined]
    assert events.status is EventsStatus.FAILING
    assert "filament_tracker_spool_received not sent: unreachable" in caplog.text
    assert TOKEN.get_secret_value() not in caplog.text


def test_a_retry_that_works_recovers(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest([Problem.UNREACHABLE, Problem.ERROR])
    events = sender(sessions, rest)
    events.feed = EventFeed(started_at=T0 - timedelta(days=1))
    with sessions() as session:
        record(session, add_product(session), EventType.RECEIVED)

    events.step()

    assert len(rest.sent) == 1  # type: ignore[attr-defined]
    assert events.status is EventsStatus.READY


def test_a_refused_token_is_not_retried(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest([Problem.REFUSED, Problem.REFUSED])
    events = sender(sessions, rest)
    events.feed = EventFeed(started_at=T0 - timedelta(days=1))
    with sessions() as session:
        record(session, add_product(session), EventType.RECEIVED)

    events.step()

    assert rest.failures == [Problem.REFUSED]  # type: ignore[attr-defined]
    assert events.status is EventsStatus.FAILING


def test_a_database_problem_is_logged_and_skipped(caplog: pytest.LogCaptureFixture) -> None:
    def broken() -> Session:
        raise RuntimeError("database is locked")

    events = HaEventSender(FakeRest(), broken)  # type: ignore[arg-type]
    events.step()
    assert "could not read the database" in caplog.text


def test_stopping_ends_retries_and_sending(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest([Problem.UNREACHABLE] * 5)
    events = HaEventSender(rest, sessions, retries=(30.0,))
    events.feed = EventFeed(started_at=T0 - timedelta(days=1))
    with sessions() as session:
        product = add_product(session)
        record(session, product, EventType.RECEIVED)
        record(session, product, EventType.RECEIVED)
    events._stopping.set()  # noqa: SLF001

    events.step()  # returns at once: no 30 s wait, and the second event is not tried

    assert len(rest.failures) == 5  # type: ignore[attr-defined]


def test_stopping_mid_retry(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest([Problem.UNREACHABLE] * 5)
    events = HaEventSender(rest, sessions, retries=(30.0,))
    timer = threading.Timer(0.05, events._stopping.set)  # noqa: SLF001
    timer.start()
    events._send(HaEvent("x", {}))  # noqa: SLF001
    timer.join()
    assert len(rest.failures) == 4  # type: ignore[attr-defined]


def test_runs_on_its_own_thread_until_stopped(sessions: sessionmaker[Session]) -> None:
    rest = FakeRest()
    events = sender(sessions, rest)

    events.start()
    with sessions() as session:
        record(session, add_product(session), EventType.RECEIVED)
    for _ in range(500):
        if rest.sent:  # type: ignore[attr-defined]
            break
        threading.Event().wait(0.01)
    assert any(t.name == "ha-events" for t in threading.enumerate())
    events.stop()

    assert [t for t, _ in rest.sent] == ["filament_tracker_spool_received"]  # type: ignore[attr-defined]
    assert not any(t.name == "ha-events" for t in threading.enumerate())


def test_without_home_assistant_nothing_starts(sessions: sessionmaker[Session]) -> None:
    events = HaEventSender(None, sessions)
    events.start()
    events.stop()
    assert events.status is EventsStatus.OFF
    assert not any(t.name == "ha-events" for t in threading.enumerate())
