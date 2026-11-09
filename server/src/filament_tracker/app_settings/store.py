"""Read and save settings: a value saved in the app wins over `.env`, which wins over the
default (see Settings and first start in docs/SPEC.md).

A saved row with an empty value means the setting was turned off in the app, even if
`.env` sets it. Deleting the row ("Use the .env value") goes back to `.env`. Secrets are
stored sealed; one that cannot be opened (the key changed) counts as not set and is
marked unreadable, so the Settings page can ask for it again.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox, Unreadable
from filament_tracker.app_settings.registry import BY_KEY, SettingDef, group
from filament_tracker.config import Settings
from filament_tracker.db.models import Setting
from filament_tracker.db.types import utcnow

logger = logging.getLogger(__name__)

DEFAULT_SESSION_DAYS = 30
DEFAULT_TIME_ZONE = "UTC"


class Source(StrEnum):
    APP = "app"
    ENV = "env"
    DEFAULT = "default"


@dataclass(frozen=True)
class Current:
    definition: SettingDef
    value: str | None
    source: Source
    has_env: bool
    unreadable: bool = False

    @property
    def key(self) -> str:
        return self.definition.key


class SettingsInvalid(ValueError):
    """Some values were refused, by key. The messages never repeat a value."""

    def __init__(self, problems: dict[str, str]) -> None:
        super().__init__("; ".join(f"{k}: {v}" for k, v in problems.items()))
        self.problems = problems


class UnknownSetting(KeyError):
    pass


def _plain(value: object) -> str | None:
    if value is None:
        return None
    text = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
    return text or None


class SettingsStore:
    def __init__(self, env: Settings, sessions: sessionmaker[Session], box: SecretBox) -> None:
        self._env = env
        self._sessions = sessions
        self._box = box

    def _env_value(self, definition: SettingDef) -> tuple[str | None, bool]:
        """The `.env` (or default) value, and whether `.env` set it."""
        value = _plain(getattr(self._env, definition.env))
        return value, definition.env in self._env.model_fields_set and value is not None

    def _current(self, definition: SettingDef, row: Setting | None) -> Current:
        env_value, has_env = self._env_value(definition)
        if row is None:
            source = Source.ENV if has_env else Source.DEFAULT
            return Current(definition, env_value, source, has_env)
        if not row.value:
            return Current(definition, None, Source.APP, has_env)
        if not row.secret:
            return Current(definition, row.value, Source.APP, has_env)
        try:
            return Current(
                definition, self._box.open(definition.key, row.value), Source.APP, has_env
            )
        except Unreadable:
            return Current(definition, None, Source.APP, has_env, unreadable=True)

    def current(self, key: str) -> Current:
        definition = BY_KEY.get(key)
        if definition is None:
            raise UnknownSetting(key)
        with self._sessions() as session:
            return self._current(definition, session.get(Setting, key))

    def group(self, name: str) -> list[Current]:
        with self._sessions() as session:
            return [self._current(d, session.get(Setting, d.key)) for d in group(name)]

    def text(self, key: str) -> str | None:
        return self.current(key).value

    def secret(self, key: str) -> SecretStr | None:
        value = self.current(key).value
        return None if value is None else SecretStr(value)

    def session_days(self) -> int:
        """How long a new sign-in lasts."""
        return int(self.text("session_days") or DEFAULT_SESSION_DAYS)

    def time_zone(self) -> str:
        """The time zone for every time the web app shows."""
        return self.text("tz") or DEFAULT_TIME_ZONE

    def check(self, values: dict[str, str], keys: Iterable[str] | None = None) -> dict[str, str]:
        """Cleaned values, or SettingsInvalid naming each refused key. `keys` limits which
        settings may be given (a group)."""
        allowed = set(BY_KEY if keys is None else keys)
        problems: dict[str, str] = {}
        cleaned: dict[str, str] = {}
        for key, value in values.items():
            if key not in allowed:
                problems[key] = "not a setting here"
                continue
            try:
                cleaned[key] = BY_KEY[key].clean(value)
            except ValueError as error:
                problems[key] = str(error)
        if problems:
            raise SettingsInvalid(problems)
        return cleaned

    def save(
        self,
        values: dict[str, str],
        clear: Iterable[str] = (),
        *,
        keys: Iterable[str] | None = None,
        user_id: int | None = None,
    ) -> list[str]:
        """Save values (an empty secret keeps the current one) and clear secrets. Returns
        the keys written. Nothing is written if any value is refused."""
        allowed = set(BY_KEY if keys is None else keys)
        clear = set(clear)
        bad = {k: "not a setting here" for k in clear if k not in allowed}
        if bad:
            raise SettingsInvalid(bad)
        cleaned = self.check(values, allowed)
        written: list[str] = []
        with self._sessions() as session:
            for key, value in cleaned.items():
                definition = BY_KEY[key]
                if definition.secret and (not value or key in clear):
                    continue  # blank keeps the current secret; Clear is handled below
                stored = self._box.seal(key, value) if definition.secret and value else value
                self._write(session, definition, stored, user_id)
                written.append(key)
            for key in sorted(clear):
                self._write(session, BY_KEY[key], "", user_id)
                written.append(key)
            session.commit()
        if written:
            logger.info("settings changed by user %s: %s", user_id, ", ".join(written))
        return written

    def reset(self, key: str, *, user_id: int | None = None) -> bool:
        """Go back to the `.env` value or the default. False if nothing was saved."""
        if key not in BY_KEY:
            raise UnknownSetting(key)
        with self._sessions() as session:
            row = session.get(Setting, key)
            if row is None:
                return False
            session.delete(row)
            session.commit()
        logger.info("setting reset to .env by user %s: %s", user_id, key)
        return True

    @staticmethod
    def _write(session: Session, definition: SettingDef, value: str, user_id: int | None) -> None:
        row = session.get(Setting, definition.key)
        if row is None:
            row = Setting(key=definition.key)
            session.add(row)
        row.value = value
        row.secret = definition.secret
        row.updated_at = utcnow()
        row.updated_by = user_id
