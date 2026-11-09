import base64
import json
from pathlib import Path
from typing import Any

import aiomqtt
import pytest
from pydantic import SecretStr
from sqlalchemy.orm import sessionmaker

from filament_tracker.app_settings import offline
from filament_tracker.app_settings.crypto import SecretBox
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.ha import cli
from filament_tracker.ha.diagnose import ENTITIES, config_topic
from filament_tracker.ha.entities import AVAILABILITY_TOPIC, LOW_STOCK_TOPIC, TOTALS_TOPIC

TOKEN = "ha-token-value-1234"  # noqa: S105 - test value
PASSWORD = "broker-pass-5678"  # noqa: S105 - test value
KEY = bytes(range(32))
HA_ENV = {
    "mqtt_url": "mqtt://broker.local:1883",
    "mqtt_user": "ha-user",
    "mqtt_password": PASSWORD,
    "ha_url": "http://ha.local:8123",
    "ha_token": TOKEN,
}
RETAINED = {config_topic("homeassistant", e): "{}" for e in ENTITIES} | {
    AVAILABILITY_TOPIC: "online",
    TOTALS_TOPIC: json.dumps({"spools": 2, "open": 1, "sealed": 1, "in_review": 0}),
    LOW_STOCK_TOPIC: json.dumps({"low": False, "count": 0}),
}
STATES = [
    {
        "entity_id": "sensor.a",
        "state": state,
        "attributes": {"friendly_name": f"Filament Tracker {name}"},
    }
    for name, state in [
        ("Total spools", "2"),
        ("Total open", "1"),
        ("Total sealed", "1"),
        ("Spools in review", "0"),
        ("Low filament", "off"),
    ]
]


def env_store(**env: Any) -> SettingsStore:
    settings = Settings(database_url="sqlite://", _env_file=None, **env)
    return SettingsStore(settings, offline.empty_sessions(), SecretBox(KEY))


class FakeHa:
    """Answers HaRest's requests by path; records them."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.seen: list[tuple[str, str]] = []

    def __call__(self, request: Any, timeout: float) -> Any:
        path = request.full_url.split("8123", 1)[1]
        self.seen.append((request.get_method(), path))
        answer = self.answers.get(path, b"{}")
        if isinstance(answer, BaseException):
            raise answer
        body = answer if isinstance(answer, bytes) else json.dumps(answer).encode()

        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def read(self, limit: int) -> bytes:
                return body[:limit]

        return Response()


@pytest.fixture
def ha(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    """Patch the broker read and the REST opener; returns the fake HA to adjust."""
    fake = FakeHa({"/api/": {"message": "API running."}, "/api/states": STATES})
    original = cli.ha_config

    def config(store: SettingsStore) -> Any:
        found = original(store)
        if found.rest is not None:
            object.__setattr__(found.rest, "opener", fake)
        return found

    monkeypatch.setattr(cli, "ha_config", config)
    monkeypatch.setattr(cli, "read_retained", lambda broker, prefix, seconds: dict(RETAINED))
    return fake


def run(store: SettingsStore, found_db: bool = True, **kwargs: Any) -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = cli.run_check(
        store, found_db, fire_event=kwargs.get("event", False), seconds=0.1, out=lines.append
    )
    return ok, lines


def test_everything_passes_and_no_secret_is_printed(ha: FakeHa) -> None:
    ok, lines = run(env_store(**HA_ENV), event=True)
    assert ok
    assert lines[0] == "Settings: 0 saved in the app, 5 from .env, 1 default"
    assert "Broker: connected" in lines
    assert "Home Assistant: token accepted" in lines
    assert "  Low filament: off (matches the broker)" in lines
    assert lines[-2] == "Event: filament_tracker_check fired (see Developer tools > Events)"
    assert lines[-1] == "Result: all checks passed"
    text = "\n".join(lines)
    for secret in (TOKEN, PASSWORD, "broker.local", "ha.local", "ha-user"):
        assert secret not in text
    assert ("POST", "/api/events/filament_tracker_check") in ha.seen


def test_nothing_set() -> None:
    ok, lines = run(env_store(), found_db=False)
    assert not ok
    assert lines[0] == (
        "Settings: 0 saved in the app, 0 from .env, 6 default"
        " (server database not found: .env only)"
    )
    assert "Broker: not set (entities are off)  <-- problem" in lines
    assert "Home Assistant: address or token not set (events are off)  <-- problem" in lines
    assert lines[-1] == "Result: problems found (marked above)"


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (aiomqtt.MqttCodeError(5, "not authorised"), "refused the user name or password"),
        (aiomqtt.MqttCodeError(2), "error"),
        (aiomqtt.MqttCodeError("odd"), "error"),
        (aiomqtt.MqttError("gone"), "unreachable"),
        (OSError("no route"), "unreachable"),
    ],
)
def test_broker_problems(
    ha: FakeHa, monkeypatch: pytest.MonkeyPatch, error: Exception, text: str
) -> None:
    def fail(*args: Any) -> dict[str, str]:
        raise error

    monkeypatch.setattr(cli, "read_retained", fail)
    ok, lines = run(env_store(**HA_ENV))
    assert not ok
    assert f"Broker: {text}  <-- problem" in lines
    # Without the broker, Home Assistant's states are listed without comparing.
    assert "  Total spools: 2" in lines


def test_home_assistant_unreachable(ha: FakeHa) -> None:
    ha.answers["/api/"] = OSError("down")
    ok, lines = run(env_store(**HA_ENV))
    assert not ok
    assert "Home Assistant: unreachable  <-- problem" in lines


def test_home_assistant_refuses_the_token(ha: FakeHa) -> None:
    import urllib.error

    ha.answers["/api/"] = urllib.error.HTTPError("u", 401, "no", {}, None)  # type: ignore[arg-type]
    ok, lines = run(env_store(**HA_ENV))
    assert "Home Assistant: refused the token  <-- problem" in lines
    ha.answers["/api/"] = urllib.error.HTTPError("u", 500, "no", {}, None)  # type: ignore[arg-type]
    assert "Home Assistant: error  <-- problem" in run(env_store(**HA_ENV))[1]


def test_states_or_event_fail(ha: FakeHa) -> None:
    ha.answers["/api/states"] = {"not": "a list"}
    ha.answers["/api/events/filament_tracker_check"] = OSError("down")
    ok, lines = run(env_store(**HA_ENV), event=True)
    assert not ok
    assert "  Could not read the entity states  <-- problem" in lines
    assert "Event: filament_tracker_check could not be fired  <-- problem" in lines


def test_states_skip_odd_entries(ha: FakeHa) -> None:
    ha.answers["/api/states"] = [*STATES, "odd"]
    assert run(env_store(**HA_ENV))[0]


# --- the settings in use -------------------------------------------------------------


def test_database_file() -> None:
    assert offline.database_file("sqlite://") is None
    assert offline.database_file("sqlite:///:memory:") is None
    assert offline.database_file("postgresql://h/db") is None
    assert offline.database_file("sqlite:///./data/x.db") == Path("./data/x.db")


def test_key_from_env_or_file_never_created(tmp_path: Path) -> None:
    text = base64.b64encode(KEY).decode()
    url = f"sqlite:///{tmp_path / 'db.sqlite'}"
    assert (
        offline.read_key(Settings(database_url=url, settings_key=SecretStr(text), _env_file=None))
        == KEY
    )
    plain = Settings(database_url=url, _env_file=None)
    assert offline.read_key(plain) is None
    assert not (tmp_path / "settings.key").exists()
    (tmp_path / "settings.key").write_text(text + "\n")
    assert offline.read_key(plain) == KEY
    assert offline.read_key(Settings(database_url="sqlite://", _env_file=None)) is None


def test_open_store_reads_the_servers_database(db_url: str, tmp_path: Path) -> None:
    # A value saved in the app, with the key file beside the database.
    key_dir = Path(db_url.removeprefix("sqlite:///")).parent
    (key_dir / "settings.key").write_text(base64.b64encode(KEY).decode())
    settings = Settings(database_url=db_url, _env_file=None, mqtt_url="mqtt://a:1883")
    sessions: sessionmaker = create_session_factory(create_db_engine(db_url))
    SettingsStore(settings, sessions, SecretBox(KEY)).save(
        {"mqtt_url": "mqtt://b:1883", "ha_token": TOKEN}, [], user_id=None
    )

    store, found = offline.open_store(settings)
    assert found
    assert store.text("mqtt_url") == "mqtt://b:1883"
    assert store.text("ha_token") == TOKEN

    # Without the key, the saved secret is reported as unreadable.
    (key_dir / "settings.key").unlink()
    store, _ = offline.open_store(settings)
    report = cli.settings_report(store, True)
    assert "  Saved secrets that can't be read (enter them again): ha_token  <-- problem" in (
        report.lines
    )
    assert not (key_dir / "settings.key").exists()


def test_open_store_without_a_database(tmp_path: Path) -> None:
    missing = Settings(database_url=f"sqlite:///{tmp_path / 'none.db'}", _env_file=None)
    store, found = offline.open_store(missing)
    assert not found
    assert not (tmp_path / "none.db").exists()
    # A database from before the settings table is treated the same way.
    old = tmp_path / "old.db"
    create_db_engine(f"sqlite:///{old}").connect().close()
    assert offline.open_store(Settings(database_url=f"sqlite:///{old}", _env_file=None))[1] is False


def test_main(ha: FakeHa, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'x.db'}", _env_file=None, **HA_ENV)
    assert cli.main(["check", "--seconds", "0.1"], settings=settings) == 0
    out = capsys.readouterr().out
    assert "Result: all checks passed" in out
    assert TOKEN not in out and PASSWORD not in out
    assert cli.main(["check"], settings=Settings(database_url="sqlite://", _env_file=None)) == 1
