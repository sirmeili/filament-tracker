"""Shared pieces for the Home Assistant tests: stock in the database and a fake MQTT client."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from filament_tracker.db.models import Product, Spool
from filament_tracker.domain.enums import SpoolState


def add_product(session: Session, name: str = "Black PLA Basic", **fields: Any) -> Product:
    values = {
        "material_id": "GFA00",
        "variant_id": "A00-K00",
        "filament_type": "PLA",
        "color_rgba": "000000FF",
        "display_name": name,
    } | fields
    product = Product(**values)
    session.add(product)
    session.flush()
    return product


def add_spools(session: Session, product: Product, state: SpoolState, count: int = 1) -> None:
    for _ in range(count):
        session.add(Spool(product_id=product.id, state=state))
    session.flush()


@dataclass
class Message:
    topic: str
    payload: Any


@dataclass
class FakeBroker:
    """What every fake client published, and a way to talk to the current one."""

    published: list[tuple[str, str, int, bool]] = field(default_factory=list)
    clients: list["FakeClient"] = field(default_factory=list)
    refuse: int = 0  # refuse this many connections first
    kwargs: list[dict[str, Any]] = field(default_factory=list)

    def factory(self, **kwargs: Any) -> "FakeClient":
        self.kwargs.append(kwargs)
        client = FakeClient(self)
        self.clients.append(client)
        return client

    def topics(self) -> list[str]:
        return [topic for topic, *_ in self.published]

    def last(self, topic: str) -> str | None:
        found = [payload for t, payload, *_ in self.published if t == topic]
        return found[-1] if found else None


class FakeClient:
    def __init__(self, broker: FakeBroker) -> None:
        self.broker = broker
        self.subscribed: list[str] = []
        self.inbox: asyncio.Queue[Message | None] = asyncio.Queue()
        self.messages = self._messages()

    async def __aenter__(self) -> "FakeClient":
        from aiomqtt import MqttError

        if self.broker.refuse > 0:
            self.broker.refuse -= 1
            raise MqttError("Connection refused")
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        self.broker.published.append((topic, payload, qos, retain))

    async def _messages(self):  # type: ignore[no-untyped-def]
        from aiomqtt import MqttError

        while True:
            message = await self.inbox.get()
            if message is None:
                raise MqttError("Disconnected")
            yield message

    def send(self, topic: str, payload: Any) -> None:
        self.inbox.put_nowait(Message(topic, payload))

    def drop(self) -> None:
        self.inbox.put_nowait(None)
