"""ft-ha: check the Home Assistant link against a real Home Assistant.

`ft-ha check` uses the Home Assistant settings the server uses (a value saved on the
Settings page wins over server/.env), reads the server's retained messages from the broker
and compares them with the entities Home Assistant shows. It prints counts and states only,
never an address, user name, password or token, and changes nothing unless `--event` asks
it to fire one test event.
"""

import argparse
import logging
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

import aiomqtt
from sqlalchemy import inspect as sql_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.app_settings.crypto import (
    KEY_BYTES,
    SecretBox,
    key_file_for,
    parse_key,
)
from filament_tracker.app_settings.registry import HOME_ASSISTANT, group
from filament_tracker.app_settings.store import SettingsStore, Source
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.models import Base
from filament_tracker.ha.check import REFUSED_CODES, CheckResult, check_rest
from filament_tracker.ha.diagnose import Report, broker_report, entities_report, read_retained
from filament_tracker.ha.link import ha_config
from filament_tracker.ha.rest import HaRestError

CHECK_EVENT = "filament_tracker_check"


def _database_file(url: str) -> Path | None:
    """The SQLite file the server uses, or None for an in-memory database."""
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or parsed.database in (None, "", ":memory:"):
        return None
    return Path(parsed.database)


def _key(settings: Settings) -> bytes | None:
    """The settings key, read but never created: no key means saved secrets can't be read."""
    if settings.settings_key is not None and settings.settings_key.get_secret_value().strip():
        return parse_key(settings.settings_key.get_secret_value())
    path = key_file_for(settings.database_url)
    if path is None or not path.exists():
        return None
    return parse_key(path.read_text(encoding="utf-8"))


def _empty_sessions() -> sessionmaker[Session]:
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def open_store(settings: Settings) -> tuple[SettingsStore, bool]:
    """The settings in use, and whether the server's database was found. Without it, only
    server/.env counts. The database is only read; nothing is created or upgraded."""
    path = _database_file(settings.database_url)
    sessions = None
    if path is not None and path.exists():
        engine = create_db_engine(settings.database_url)
        if sql_inspect(engine).has_table("setting"):
            sessions = create_session_factory(engine)
    key = _key(settings)
    box = SecretBox(key if key is not None else secrets.token_bytes(KEY_BYTES))
    return SettingsStore(settings, sessions or _empty_sessions(), box), sessions is not None


def settings_report(store: SettingsStore, found_db: bool) -> Report:
    report = Report()
    current = [store.current(d.key) for d in group(HOME_ASSISTANT)]
    counts = {source: sum(1 for c in current if c.source is source) for source in Source}
    report.add(
        "Settings: {app} saved in the app, {env} from .env, {default} default{note}".format(
            app=counts[Source.APP],
            env=counts[Source.ENV],
            default=counts[Source.DEFAULT],
            note="" if found_db else " (server database not found: .env only)",
        )
    )
    unreadable = [c.definition.key for c in current if c.unreadable]
    if unreadable:
        report.add(
            f"  Saved secrets that can't be read (enter them again): {', '.join(unreadable)}",
            False,
        )
    return report


def _broker_problem(error: Exception) -> str:
    if isinstance(error, aiomqtt.MqttCodeError):
        rc = getattr(error.rc, "value", error.rc)
        try:
            refused = int(rc) in REFUSED_CODES
        except (TypeError, ValueError):
            refused = False
        return "refused the user name or password" if refused else "error"
    return "unreachable"


def run_check(
    store: SettingsStore, found_db: bool, *, fire_event: bool, seconds: float, out=print
) -> bool:
    config = ha_config(store)
    report = settings_report(store, found_db)
    retained = None
    if config.broker is None:
        report.add("Broker: not set (entities are off)", False)
    else:
        try:
            retained = read_retained(config.broker, config.prefix, seconds)
        except (aiomqtt.MqttError, OSError, TimeoutError) as error:
            report.add(f"Broker: {_broker_problem(error)}", False)
        else:
            report.add("Broker: connected")
            sub = broker_report(retained, config.prefix)
            report.lines += sub.lines
            report.ok = report.ok and sub.ok
    rest_result = check_rest(config.rest)
    if config.rest is None:
        report.add("Home Assistant: address or token not set (events are off)", False)
    elif rest_result is not CheckResult.OK:
        text = {
            CheckResult.UNREACHABLE: "unreachable",
            CheckResult.REFUSED: "refused the token",
        }.get(rest_result, "error")
        report.add(f"Home Assistant: {text}", False)
    else:
        report.add("Home Assistant: token accepted")
        try:
            states = config.rest.states()
        except HaRestError:
            report.add("  Could not read the entity states", False)
        else:
            sub = entities_report(states, retained)
            report.lines += sub.lines
            report.ok = report.ok and sub.ok
        if fire_event:
            try:
                config.rest.fire(CHECK_EVENT, {"source": "ft-ha check"})
            except HaRestError:
                report.add(f"Event: {CHECK_EVENT} could not be fired", False)
            else:
                report.add(f"Event: {CHECK_EVENT} fired (see Developer tools > Events)")
    for line in report.lines:
        out(line)
    out("Result: all checks passed" if report.ok else "Result: problems found (marked above)")
    return report.ok


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ft-ha", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="compare the broker with Home Assistant")
    check.add_argument("--event", action="store_true", help=f"also fire one {CHECK_EVENT} event")
    check.add_argument(
        "--seconds", type=float, default=3.0, help="how long to read the broker (default 3)"
    )
    return parser


def main(argv: Sequence[str] | None = None, *, settings: Settings | None = None) -> int:
    args = _parser().parse_args(argv)
    # Warnings name a setting only; quieter than the server so the report stays readable.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    store, found_db = open_store(settings or Settings())
    ok = run_check(store, found_db, fire_event=args.event, seconds=args.seconds)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
