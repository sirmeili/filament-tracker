"""What `ft-ha check` looks at: the server's retained messages on the broker, and the
entities Home Assistant made from them.

Everything here returns plain lines of text with counts and states only: never an address,
a user name, a password or a token.
"""

import asyncio
import json
import secrets
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import aiomqtt

from filament_tracker.ha.broker import BrokerConfig
from filament_tracker.ha.entities import (
    AVAILABILITY_TOPIC,
    DEVICE,
    LOW_STOCK_TOPIC,
    NODE,
    ONLINE,
    TOTALS,
    TOTALS_TOPIC,
)

TIMEOUT_SECONDS = 10.0
LOW_FILAMENT = ("low_filament", "Low filament")


@dataclass(frozen=True)
class Entity:
    """One of the five entities: where it is configured and what it should show."""

    component: str
    object_id: str
    name: str
    key: str | None  # the field of the totals message, or None for Low filament


ENTITIES = tuple(Entity("sensor", oid, name, key) for oid, name, key, _icon in TOTALS) + (
    Entity("binary_sensor", LOW_FILAMENT[0], LOW_FILAMENT[1], None),
)


def config_topic(prefix: str, entity: Entity) -> str:
    return f"{prefix}/{entity.component}/{NODE}/{entity.object_id}/config"


def topics(prefix: str) -> list[str]:
    """What to subscribe to: the discovery messages and the three state topics."""
    return [f"{prefix}/+/{NODE}/+/config", AVAILABILITY_TOPIC, TOTALS_TOPIC, LOW_STOCK_TOPIC]


async def _read(
    broker: BrokerConfig, prefix: str, seconds: float, client_factory: Callable[..., Any]
) -> dict[str, str]:
    password = broker.password.get_secret_value() if broker.password else None
    seen: dict[str, str] = {}
    client = client_factory(
        hostname=broker.host,
        port=broker.port,
        username=broker.username,
        password=password,
        identifier=f"filament-tracker-check-{secrets.token_hex(4)}",
        tls_context=broker.tls_context(),
        timeout=TIMEOUT_SECONDS,
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        await client.__aenter__()
    try:
        for topic in topics(prefix):
            await client.subscribe(topic)
        try:
            async with asyncio.timeout(seconds):
                async for message in client.messages:
                    if message.retain:
                        payload = message.payload
                        text = payload.decode() if isinstance(payload, bytes) else str(payload)
                        seen[str(message.topic)] = text
        except TimeoutError:
            pass  # listened long enough: retained messages arrive straight after subscribing
    finally:
        await client.__aexit__(None, None, None)
    return seen


def read_retained(
    broker: BrokerConfig,
    prefix: str,
    seconds: float = 3.0,
    client_factory: Callable[..., Any] = aiomqtt.Client,
) -> dict[str, str]:
    """The retained messages the server published, by topic. Raises aiomqtt.MqttError or
    OSError when the broker cannot be used."""
    loop = asyncio.SelectorEventLoop()  # aiomqtt needs a selector loop on Windows
    try:
        return loop.run_until_complete(_read(broker, prefix, seconds, client_factory))
    finally:
        loop.close()


def _json(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


@dataclass
class Report:
    """Lines to print, and whether every check passed."""

    lines: list[str] = field(default_factory=list)
    ok: bool = True

    def add(self, line: str, ok: bool = True) -> None:
        self.lines.append(line if ok else f"{line}  <-- problem")
        self.ok = self.ok and ok


def broker_report(retained: dict[str, str], prefix: str) -> Report:
    """Whether the server's discovery and state messages are on the broker."""
    report = Report()
    found = [e for e in ENTITIES if config_topic(prefix, e) in retained]
    complete = len(found) == len(ENTITIES)
    report.add(f"  Discovery: {len(found)} of {len(ENTITIES)} entities", complete)
    for entity in ENTITIES:
        if entity not in found:
            report.add(f"    missing: {entity.name}", False)
    extra = sum(1 for topic in retained if topic.endswith("/config")) - len(found)
    if extra > 0:
        report.add(f"  Old discovery messages still retained: {extra}", False)
    availability = retained.get(AVAILABILITY_TOPIC)
    report.add(
        f"  Availability: {availability or 'not published'}",
        availability == ONLINE,
    )
    totals = _json(retained.get(TOTALS_TOPIC))
    if totals is None:
        report.add("  Totals: not published", False)
    else:
        report.add(
            "  Totals: {spools} spools, {open} open, {sealed} sealed, {in_review} in review".format(
                **{key: totals.get(key, "?") for key in ("spools", "open", "sealed", "in_review")}
            )
        )
    low = _json(retained.get(LOW_STOCK_TOPIC))
    if low is None:
        report.add("  Low filament: not published", False)
    else:
        count = low.get("count", 0)
        noun = "product" if count == 1 else "products"
        report.add(f"  Low filament: {'on' if low.get('low') else 'off'} ({count} {noun} low)")
    return report


def expected_state(entity: Entity, retained: dict[str, str]) -> str | None:
    """The state Home Assistant should show for this entity, from the broker's messages."""
    if retained.get(AVAILABILITY_TOPIC) != ONLINE:
        return "unavailable"
    if entity.key is None:
        low = _json(retained.get(LOW_STOCK_TOPIC))
        return None if low is None else ("on" if low.get("low") else "off")
    totals = _json(retained.get(TOTALS_TOPIC))
    value = None if totals is None else totals.get(entity.key)
    return None if value is None else str(value)


def _same(shown: str, expected: str) -> bool:
    if shown == expected:
        return True
    try:
        return float(shown) == float(expected)
    except ValueError:
        return False


def find_entity(states: Iterable[dict[str, Any]], entity: Entity) -> dict[str, Any] | None:
    """Home Assistant names an entity of a named device "<device> <entity>", and its ID
    after that name, unless someone renamed it; both are tried."""
    friendly = f"{DEVICE['name']} {entity.name}"
    entity_id = f"{entity.component}.{NODE}_{entity.name.lower().replace(' ', '_')}"
    for state in states:
        attributes = state.get("attributes")
        name = attributes.get("friendly_name") if isinstance(attributes, dict) else None
        if name == friendly or state.get("entity_id") == entity_id:
            return state
    return None


def entities_report(states: list[dict[str, Any]], retained: dict[str, str] | None) -> Report:
    """Each entity as Home Assistant shows it, compared with the broker when it was read."""
    report = Report()
    for entity in ENTITIES:
        state = find_entity(states, entity)
        if state is None:
            report.add(f"  {entity.name}: not found in Home Assistant", False)
            continue
        shown = str(state.get("state"))
        expected = None if retained is None else expected_state(entity, retained)
        if expected is None:
            report.add(f"  {entity.name}: {shown}")
        elif _same(shown, expected):
            report.add(f"  {entity.name}: {shown} (matches the broker)")
        else:
            # The server publishes within about 5 seconds, so a difference can be a change
            # that is still on its way; run the check again to be sure.
            report.add(f"  {entity.name}: {shown}, the broker has {expected}", False)
    return report
