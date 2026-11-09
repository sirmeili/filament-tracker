"""`ft-admin`: manage web app accounts from the server's command line.

The first Admin is created here, so the app never has a default account. Passwords are
always prompted for, never passed as arguments, so they stay out of shell history.

    ft-admin create-user USERNAME [--role viewer|editor|admin]
    ft-admin reset-password USERNAME
    ft-admin backup
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy import select

from filament_tracker.app_settings.offline import database_file
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.db.models import User
from filament_tracker.db.types import utcnow
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import (
    AccountError,
    check_password_rules,
    create_user,
    set_password,
)
from filament_tracker.services.backup import backup_database, prune

Prompt = Callable[[str], str]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ft-admin", description="Manage web app accounts.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create an account")
    create.add_argument("username")
    create.add_argument("--role", choices=[r.value for r in Role], default=Role.ADMIN.value)
    reset = commands.add_parser(
        "reset-password", help="set a new password and sign the user out everywhere"
    )
    reset.add_argument("username")
    commands.add_parser(
        "backup", help="back the database up to BACKUP_DIR now, like the nightly backup"
    )
    return parser


def _new_password(prompt: Prompt) -> str:
    password = prompt("Password: ")
    check_password_rules(password)
    if prompt("Repeat password: ") != password:
        raise AccountError("the passwords do not match")
    return password


def _backup(settings: Settings) -> int:
    source = database_file(settings.database_url)
    if settings.backup_dir is None or source is None or not source.exists():
        print("ft-admin: set BACKUP_DIR, and use a database file that exists", file=sys.stderr)
        return 1
    path = backup_database(source, settings.backup_dir, utcnow())
    removed = prune(settings.backup_dir)
    print(f"backup written: {path} ({len(removed)} old removed)")
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    prompt: Prompt = getpass.getpass,
    settings: Settings | None = None,
) -> int:
    args = _parser().parse_args(argv)
    settings = settings or Settings()
    if args.command == "backup":
        return _backup(settings)
    upgrade(settings.database_url)
    engine = create_db_engine(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            if args.command == "create-user":
                user = create_user(session, args.username, _new_password(prompt), Role(args.role))
                verb = "created"
            else:
                name = args.username.strip().lower()
                found = session.scalar(select(User).where(User.username == name))
                if found is None:
                    raise AccountError(f"no user named {name!r}")
                user = found
                set_password(session, user, _new_password(prompt))
                verb = "updated"
            session.commit()
            print(f"{verb} {user.username} ({user.role.value})")
    except AccountError as exc:
        print(f"ft-admin: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
