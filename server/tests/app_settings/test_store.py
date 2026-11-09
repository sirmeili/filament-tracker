import logging

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.app_settings.registry import HOME_ASSISTANT, group
from filament_tracker.app_settings.store import (
    SettingsInvalid,
    SettingsStore,
    Source,
    UnknownSetting,
)
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_session_factory
from filament_tracker.db.models import Setting

KEY = bytes(range(32))
TOKEN = "ha-token-value-1234"  # noqa: S105 - test value


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def store(sessions: sessionmaker[Session], key: bytes = KEY, **env: object) -> SettingsStore:
    settings = Settings(database_url="sqlite://", _env_file=None, **env)  # type: ignore[arg-type]
    return SettingsStore(settings, sessions, SecretBox(key))


def test_without_anything_saved_the_defaults_are_used(sessions: sessionmaker[Session]) -> None:
    current = {c.key: c for c in store(sessions).group(HOME_ASSISTANT)}

    assert [c for c in current] == [d.key for d in group(HOME_ASSISTANT)]
    assert current["ha_url"].value is None
    assert current["ha_url"].source is Source.DEFAULT
    assert current["ha_discovery_prefix"].value == "homeassistant"
    assert current["ha_discovery_prefix"].source is Source.DEFAULT
    assert not current["ha_discovery_prefix"].has_env


def test_env_values_are_the_starting_value(sessions: sessionmaker[Session]) -> None:
    s = store(sessions, ha_url="http://ha.local:8123", ha_token=SecretStr(TOKEN))

    assert s.current("ha_url").source is Source.ENV
    assert s.text("ha_url") == "http://ha.local:8123"
    assert s.secret("ha_token") == SecretStr(TOKEN)
    assert s.current("ha_token").has_env


def test_a_saved_value_wins_over_env_until_reset(sessions: sessionmaker[Session]) -> None:
    s = store(sessions, ha_url="http://ha.local:8123")

    assert s.save({"ha_url": " http://other:8123/ "}, user_id=None) == ["ha_url"]
    assert s.text("ha_url") == "http://other:8123"
    assert s.current("ha_url").source is Source.APP

    assert s.reset("ha_url") is True
    assert s.text("ha_url") == "http://ha.local:8123"
    assert s.current("ha_url").source is Source.ENV
    assert s.reset("ha_url") is False


def test_an_empty_value_turns_a_setting_off_in_the_app(sessions: sessionmaker[Session]) -> None:
    s = store(sessions, mqtt_url="mqtt://broker:1883")
    s.save({"mqtt_url": ""})
    current = s.current("mqtt_url")
    assert current.value is None
    assert current.source is Source.APP
    assert current.has_env


def test_secrets_are_stored_sealed(sessions: sessionmaker[Session]) -> None:
    s = store(sessions)
    s.save({"ha_token": TOKEN})

    with sessions() as session:
        row = session.get(Setting, "ha_token")
        assert row is not None and row.secret
        assert TOKEN not in row.value
    assert s.secret("ha_token") == SecretStr(TOKEN)


def test_a_blank_secret_keeps_the_saved_one_and_clear_removes_it(
    sessions: sessionmaker[Session],
) -> None:
    s = store(sessions, ha_token=SecretStr("env-token"))
    s.save({"ha_token": TOKEN})

    assert s.save({"ha_token": "  "}) == []
    assert s.text("ha_token") == TOKEN

    assert s.save({"ha_token": "ignored"}, clear=["ha_token"]) == ["ha_token"]
    current = s.current("ha_token")
    assert current.value is None
    assert current.source is Source.APP  # cleared in the app, even though .env sets it


def test_a_secret_from_another_key_needs_entering_again(sessions: sessionmaker[Session]) -> None:
    store(sessions).save({"ha_token": TOKEN})

    current = store(sessions, key=bytes(32)).current("ha_token")

    assert current.unreadable
    assert current.value is None


def test_refused_values_are_not_saved_or_repeated(sessions: sessionmaker[Session]) -> None:
    s = store(sessions)
    bad = "mqtt://user:hunter2@broker"
    with pytest.raises(SettingsInvalid) as error:
        s.save({"mqtt_url": bad, "ha_url": "http://ok:8123"})

    assert set(error.value.problems) == {"mqtt_url"}
    assert "hunter2" not in str(error.value)
    assert s.current("ha_url").source is Source.DEFAULT  # nothing written


@pytest.mark.parametrize(
    ("values", "key"),
    [
        ({"ha_discovery_prefix": ""}, "ha_discovery_prefix"),
        ({"ha_discovery_prefix": "bad prefix!"}, "ha_discovery_prefix"),
        ({"ha_url": "ftp://ha"}, "ha_url"),
        ({"mqtt_user": "x" * 2000}, "mqtt_user"),
        ({"database_url": "sqlite://"}, "database_url"),  # .env only
        ({"session_days": "0"}, "session_days"),
        ({"session_days": "366"}, "session_days"),
        ({"session_days": "two"}, "session_days"),
        ({"session_days": ""}, "session_days"),
        ({"tz": "Mars/Olympus"}, "tz"),
        ({"tz": ""}, "tz"),
        ({"bambu_kdf_salt": "abc"}, "bambu_kdf_salt"),
        ({"bambu_kdf_salt": "zz"}, "bambu_kdf_salt"),
    ],
)
def test_each_setting_is_checked(
    sessions: sessionmaker[Session], values: dict[str, str], key: str
) -> None:
    with pytest.raises(SettingsInvalid) as error:
        store(sessions).save(values)
    assert key in error.value.problems


def test_general_and_scanner_settings(sessions: sessionmaker[Session]) -> None:
    salt = "0a1b2c3d"  # test value, not the real constant
    s = store(sessions, session_days=7, tz="America/Chicago")
    assert (s.session_days(), s.time_zone()) == (7, "America/Chicago")
    assert s.secret("bambu_kdf_salt") is None

    s.save({"session_days": " 14 ", "tz": "Europe/Berlin", "bambu_kdf_salt": salt})
    assert (s.session_days(), s.time_zone()) == (14, "Europe/Berlin")
    assert s.secret("bambu_kdf_salt") == SecretStr(salt.upper())
    with sessions() as session:
        row = session.get(Setting, "bambu_kdf_salt")
        assert row is not None and row.secret and salt.upper() not in row.value


def test_defaults_without_env(sessions: sessionmaker[Session]) -> None:
    s = store(sessions)
    assert (s.session_days(), s.time_zone()) == (30, "UTC")
    assert s.current("tz").source is Source.DEFAULT


def test_a_bad_salt_is_refused_without_repeating_it(sessions: sessionmaker[Session]) -> None:
    with pytest.raises(SettingsInvalid) as error:
        store(sessions).save({"bambu_kdf_salt": "secretvalue"})
    assert "secretvalue" not in str(error.value)


def test_only_settings_of_the_group_are_accepted(sessions: sessionmaker[Session]) -> None:
    s = store(sessions)
    with pytest.raises(SettingsInvalid):
        s.save({"ha_url": "http://ha:8123"}, keys=["mqtt_url"])
    with pytest.raises(SettingsInvalid):
        s.save({}, clear=["ha_url"], keys=["mqtt_url"])
    with pytest.raises(UnknownSetting):
        s.current("nope")
    with pytest.raises(UnknownSetting):
        s.reset("nope")


def test_changes_are_logged_by_name_never_by_value(
    sessions: sessionmaker[Session], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    s = store(sessions)
    s.save({"ha_token": TOKEN, "ha_url": "http://ha.local:8123"})
    s.reset("ha_url")

    assert "ha_token" in caplog.text
    assert TOKEN not in caplog.text
    assert "ha.local" not in caplog.text


def test_who_changed_it_is_kept(sessions: sessionmaker[Session], engine: Engine) -> None:
    from filament_tracker.domain.enums import Role
    from filament_tracker.services.accounts import create_user

    with sessions() as session:
        user = create_user(session, "admin1", "a-long-password-1", Role.ADMIN)
        session.commit()
        user_id = user.id
    store(sessions).save({"ha_url": "http://ha:8123"}, user_id=user_id)
    with sessions() as session:
        assert session.get(Setting, "ha_url").updated_by == user_id  # type: ignore[union-attr]
