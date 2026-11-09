"""ft-ha: check the Home Assistant link against a real Home Assistant.

`ft-ha check` uses the Home Assistant settings the server uses (a value saved on the
Settings page wins over server/.env), reads the server's retained messages from the broker
and compares them with the entities Home Assistant shows. It prints counts and states only,
never an address, user name, password or token, and changes nothing unless `--event` asks
it to fire one test event.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

import aiomqtt

from filament_tracker.app_settings.offline import open_store
from filament_tracker.app_settings.registry import HOME_ASSISTANT, group
from filament_tracker.app_settings.store import SettingsStore, Source
from filament_tracker.config import Settings
from filament_tracker.ha.check import REFUSED_CODES, CheckResult, check_rest
from filament_tracker.ha.diagnose import Report, broker_report, entities_report, read_retained
from filament_tracker.ha.link import ha_config
from filament_tracker.ha.rest import HaRestError

CHECK_EVENT = "filament_tracker_check"


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
