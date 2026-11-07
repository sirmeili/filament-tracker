"""The settings that can be saved in the app, by group.

Each one names its `.env` setting (the starting value), whether it is a secret, and how a
value is checked. Check errors never repeat the value, which may be a secret or hold one.
Groups other than Home Assistant arrive in M9 (see Milestones in docs/SPEC.md).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from filament_tracker.ha.broker import parse_mqtt_url
from filament_tracker.ha.rest import parse_ha_url

MAX_VALUE = 1024
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}(/[A-Za-z0-9_-]{1,64}){0,3}$")


def _mqtt_url(value: str) -> str:
    parse_mqtt_url(value)
    return value


def _ha_url(value: str) -> str:
    return parse_ha_url(value)


def _prefix(value: str) -> str:
    if not PREFIX_PATTERN.fullmatch(value):
        raise ValueError("use letters, digits, - and _, with up to three / between parts")
    return value


def _plain(value: str) -> str:
    return value


@dataclass(frozen=True)
class SettingDef:
    key: str
    group: str
    # The attribute of config.Settings that holds the .env value.
    env: str
    secret: bool = False
    # Whether the setting may be empty (meaning off or none).
    optional: bool = True
    check: Callable[[str], str] = _plain

    def clean(self, value: str) -> str:
        """The value to store: trimmed and checked. Raises ValueError, never echoing it."""
        value = value.strip()
        if len(value) > MAX_VALUE:
            raise ValueError(f"at most {MAX_VALUE} characters")
        if not value:
            if not self.optional:
                raise ValueError("needs a value")
            return ""
        return self.check(value)


HOME_ASSISTANT = "home-assistant"

DEFINITIONS: tuple[SettingDef, ...] = (
    SettingDef("mqtt_url", HOME_ASSISTANT, "mqtt_url", check=_mqtt_url),
    SettingDef("mqtt_user", HOME_ASSISTANT, "mqtt_user"),
    SettingDef("mqtt_password", HOME_ASSISTANT, "mqtt_password", secret=True),
    SettingDef(
        "ha_discovery_prefix", HOME_ASSISTANT, "ha_discovery_prefix", optional=False, check=_prefix
    ),
    SettingDef("ha_url", HOME_ASSISTANT, "ha_url", check=_ha_url),
    SettingDef("ha_token", HOME_ASSISTANT, "ha_token", secret=True),
)

BY_KEY = {d.key: d for d in DEFINITIONS}
GROUPS = frozenset(d.group for d in DEFINITIONS)


def group(name: str) -> tuple[SettingDef, ...]:
    return tuple(d for d in DEFINITIONS if d.group == name)
