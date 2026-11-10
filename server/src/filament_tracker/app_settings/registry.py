"""The settings that can be saved in the app, by group.

Each one names its `.env` setting (the starting value), whether it is a secret, and how a
value is checked. Check errors never repeat the value, which may be a secret or hold one.
Printers are not here: they have their own table and page.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from zoneinfo import available_timezones

from filament_tracker.ha.broker import parse_mqtt_url
from filament_tracker.ha.rest import parse_ha_url

MAX_VALUE = 1024
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}(/[A-Za-z0-9_-]{1,64}){0,3}$")
SALT_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}){1,64}")
ACCESS_ID_PATTERN = re.compile(r"[A-Za-z0-9]{16,64}\.access")
ACCESS_SECRET_PATTERN = re.compile(r"[A-Za-z0-9]{32,128}")
MIN_SESSION_DAYS, MAX_SESSION_DAYS = 1, 365


def _mqtt_url(value: str) -> str:
    parse_mqtt_url(value)
    return value


def _ha_url(value: str) -> str:
    return parse_ha_url(value)


def _prefix(value: str) -> str:
    if not PREFIX_PATTERN.fullmatch(value):
        raise ValueError("use letters, digits, - and _, with up to three / between parts")
    return value


@cache
def time_zones() -> frozenset[str]:
    """IANA time zone names (from tzdata, so the same on every platform)."""
    return frozenset(available_timezones())


def time_zone(value: str) -> str:
    """An IANA time zone name such as America/New_York. The error never repeats it."""
    if value not in time_zones():
        raise ValueError("use a time zone name such as America/New_York or UTC")
    return value


def session_days(value: str) -> str:
    try:
        days = int(value)
    except ValueError:
        raise ValueError("use a whole number of days") from None
    if not MIN_SESSION_DAYS <= days <= MAX_SESSION_DAYS:
        raise ValueError(f"use {MIN_SESSION_DAYS} to {MAX_SESSION_DAYS} days")
    return str(days)


def kdf_salt(value: str) -> str:
    """The key-derivation constant as upper-case hex. The error never repeats it."""
    if not SALT_PATTERN.fullmatch(value):
        raise ValueError("use hex: an even number of digits, at most 128")
    return value.upper()


def access_client_id(value: str) -> str:
    """A Cloudflare Access service token's Client ID. The error never repeats it."""
    if not ACCESS_ID_PATTERN.fullmatch(value):
        raise ValueError("use the service token's Client ID from Cloudflare, ending in .access")
    return value


def access_client_secret(value: str) -> str:
    """A Cloudflare Access service token's Client Secret. The error never repeats it."""
    if not ACCESS_SECRET_PATTERN.fullmatch(value):
        raise ValueError("use the service token's Client Secret from Cloudflare")
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


GENERAL = "general"
HOME_ASSISTANT = "home-assistant"
SCANNERS = "scanners"

DEFINITIONS: tuple[SettingDef, ...] = (
    SettingDef("tz", GENERAL, "tz", optional=False, check=time_zone),
    SettingDef("session_days", GENERAL, "session_days", optional=False, check=session_days),
    SettingDef("mqtt_url", HOME_ASSISTANT, "mqtt_url", check=_mqtt_url),
    SettingDef("mqtt_user", HOME_ASSISTANT, "mqtt_user"),
    SettingDef("mqtt_password", HOME_ASSISTANT, "mqtt_password", secret=True),
    SettingDef(
        "ha_discovery_prefix", HOME_ASSISTANT, "ha_discovery_prefix", optional=False, check=_prefix
    ),
    SettingDef("ha_url", HOME_ASSISTANT, "ha_url", check=_ha_url),
    SettingDef("ha_token", HOME_ASSISTANT, "ha_token", secret=True),
    SettingDef("bambu_kdf_salt", SCANNERS, "bambu_kdf_salt", secret=True, check=kdf_salt),
    SettingDef("cf_access_client_id", SCANNERS, "cf_access_client_id", check=access_client_id),
    SettingDef(
        "cf_access_client_secret",
        SCANNERS,
        "cf_access_client_secret",
        secret=True,
        check=access_client_secret,
    ),
)

BY_KEY = {d.key: d for d in DEFINITIONS}
GROUPS = frozenset(d.group for d in DEFINITIONS)


def group(name: str) -> tuple[SettingDef, ...]:
    return tuple(d for d in DEFINITIONS if d.group == name)
