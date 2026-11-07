"""The Home Assistant links (MQTT entities and REST events), built from the settings in use.

Saving the Home Assistant settings calls `reload`, which stops both links and starts them
again with the new values, so a change applies without restarting the server.
"""

import logging
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.registry import BY_KEY
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.ha.broker import BrokerConfig, broker_config
from filament_tracker.ha.events import HaEventSender
from filament_tracker.ha.publisher import HaPublisher
from filament_tracker.ha.rest import HaRest

logger = logging.getLogger(__name__)

DEFAULT_PREFIX = "homeassistant"


@dataclass(frozen=True)
class HaConfig:
    broker: BrokerConfig | None
    prefix: str
    rest: HaRest | None


def ha_config(
    store: SettingsStore,
    overrides: dict[str, str] | None = None,
    cleared: Iterable[str] = (),
) -> HaConfig:
    """The Home Assistant settings in use, with `overrides` (cleaned values entered on the
    Settings page but not saved, for Test) on top, and `cleared` secrets left out. An empty
    secret override is ignored, so Test uses the saved secret."""
    overrides = overrides or {}
    cleared = set(cleared)

    def value(key: str) -> str | None:
        if key in cleared:
            return None
        if key in overrides and (overrides[key] or not BY_KEY[key].secret):
            return overrides[key] or None
        return store.text(key)

    try:
        broker = broker_config(
            value("mqtt_url"), value("mqtt_user"), _secret(value("mqtt_password"))
        )
    except ValueError:
        logger.warning("Home Assistant MQTT: the broker URL is not usable; entities are off")
        broker = None
    url, token = value("ha_url"), value("ha_token")
    rest = None
    if url and token:
        try:
            rest = HaRest(url, SecretStr(token))
        except ValueError:
            logger.warning("Home Assistant events: the HA URL is not usable; events are off")
    return HaConfig(broker, value("ha_discovery_prefix") or DEFAULT_PREFIX, rest)


def _secret(value: str | None) -> SecretStr | None:
    return None if value is None else SecretStr(value)


PublisherFactory = Callable[..., HaPublisher]
SenderFactory = Callable[..., HaEventSender]


class HomeAssistantLink:
    def __init__(
        self,
        store: SettingsStore,
        session_factory: sessionmaker[Session],
        *,
        publisher_factory: PublisherFactory = HaPublisher,
        sender_factory: SenderFactory = HaEventSender,
    ) -> None:
        self._store = store
        self._sessions = session_factory
        self._publisher_factory = publisher_factory
        self._sender_factory = sender_factory
        self._lock = threading.Lock()
        self.publisher: HaPublisher | None = None
        self.sender: HaEventSender | None = None

    def start(self) -> None:
        with self._lock:
            self._start()

    def stop(self) -> None:
        with self._lock:
            self._stop()

    def reload(self) -> None:
        """Stop both links and start them with the settings in use now."""
        with self._lock:
            self._stop()
            self._start()
            logger.info("Home Assistant settings applied")

    def _start(self) -> None:
        config = ha_config(self._store)
        self.publisher = self._publisher_factory(config.broker, config.prefix, self._sessions)
        self.sender = self._sender_factory(config.rest, self._sessions)
        self.publisher.start()
        self.sender.start()

    def _stop(self) -> None:
        if self.sender is not None:
            self.sender.stop()
        if self.publisher is not None:
            self.publisher.stop()
