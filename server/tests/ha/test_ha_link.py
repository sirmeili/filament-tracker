import logging
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_session_factory
from filament_tracker.ha.link import HomeAssistantLink, ha_config

TOKEN = "ha-token-value-1234"  # noqa: S105 - test value


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def make_store(sessions: sessionmaker[Session], **env: Any) -> SettingsStore:
    settings = Settings(database_url="sqlite://", _env_file=None, **env)
    return SettingsStore(settings, sessions, SecretBox(bytes(range(32))))


class Fake:
    """Stands in for HaPublisher or HaEventSender."""

    def __init__(self, *args: Any) -> None:
        self.args = args
        self.calls: list[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")


def test_uses_env_values_until_some_are_saved(sessions: sessionmaker[Session]) -> None:
    store = make_store(
        sessions,
        mqtt_url="mqtt://broker:1883",
        mqtt_user="ha",
        mqtt_password=SecretStr("pw"),
        ha_url="http://ha:8123",
        ha_token=SecretStr(TOKEN),
    )

    config = ha_config(store)
    assert config.broker is not None
    assert (config.broker.host, config.broker.port, config.broker.username) == (
        "broker",
        1883,
        "ha",
    )
    assert config.prefix == "homeassistant"
    assert config.rest is not None and config.rest.url == "http://ha:8123"

    store.save({"mqtt_url": "", "ha_discovery_prefix": "ha2"})
    config = ha_config(store)
    assert config.broker is None
    assert config.prefix == "ha2"


def test_entered_values_go_on_top_for_a_test(sessions: sessionmaker[Session]) -> None:
    store = make_store(sessions, ha_url="http://ha:8123", ha_token=SecretStr(TOKEN))

    blank_secret = ha_config(store, {"ha_url": "http://other:8123", "ha_token": ""})
    assert blank_secret.rest is not None
    assert blank_secret.rest.url == "http://other:8123"
    assert blank_secret.rest.token.get_secret_value() == TOKEN  # blank: the saved one

    assert ha_config(store, {"ha_url": ""}).rest is None
    assert ha_config(store, cleared=["ha_token"]).rest is None
    assert ha_config(store, {"ha_token": "new"}).rest.token.get_secret_value() == "new"  # type: ignore[union-attr]


class BadStore:
    """Values that the settings checks would refuse, as an old database might hold."""

    def text(self, key: str) -> str | None:
        return {"mqtt_url": "ftp://x", "ha_url": "ftp://x", "ha_token": "t"}.get(key)


def test_unusable_values_turn_the_link_off(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    config = ha_config(BadStore())  # type: ignore[arg-type]
    assert config.broker is None
    assert config.rest is None
    assert "ftp://x" not in caplog.text


def test_reload_restarts_both_links_with_new_settings(sessions: sessionmaker[Session]) -> None:
    store = make_store(sessions)
    link = HomeAssistantLink(store, sessions, publisher_factory=Fake, sender_factory=Fake)

    link.start()
    first_publisher, first_sender = link.publisher, link.sender
    assert first_publisher.args[0] is None  # type: ignore[union-attr]
    assert first_sender.args[0] is None  # type: ignore[union-attr]

    store.save({"mqtt_url": "mqtt://broker:1883", "ha_url": "http://ha:8123", "ha_token": TOKEN})
    link.reload()

    assert first_publisher.calls == ["start", "stop"]  # type: ignore[union-attr]
    assert first_sender.calls == ["start", "stop"]  # type: ignore[union-attr]
    assert link.publisher.args[0].host == "broker"  # type: ignore[union-attr]
    assert link.sender.args[0].url == "http://ha:8123"  # type: ignore[union-attr]
    assert link.publisher.calls == ["start"]  # type: ignore[union-attr]

    link.stop()
    assert link.publisher.calls == ["start", "stop"]  # type: ignore[union-attr]


def test_stopping_before_starting_is_harmless(sessions: sessionmaker[Session]) -> None:
    HomeAssistantLink(make_store(sessions), sessions).stop()
