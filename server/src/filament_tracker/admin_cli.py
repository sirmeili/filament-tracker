"""`ft-admin`: manage web app accounts from the server's command line.

The first Admin is created here, so the app never has a default account. Passwords are
always prompted for, never passed as arguments, so they stay out of shell history.

    ft-admin create-user USERNAME [--role viewer|editor|admin]
    ft-admin reset-password USERNAME
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy import select

from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.db.models import User
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import (
    AccountError,
    check_password_rules,
    create_user,
    set_password,
)

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
    return parser


def _new_password(prompt: Prompt) -> str:
    password = prompt("Password: ")
    check_password_rules(password)
    if prompt("Repeat password: ") != password:
        raise AccountError("the passwords do not match")
    return password


def main(
    argv: Sequence[str] | None = None,
    *,
    prompt: Prompt = getpass.getpass,
    settings: Settings | None = None,
) -> int:
    args = _parser().parse_args(argv)
    settings = settings or Settings()
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
