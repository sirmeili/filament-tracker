from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import select

from filament_tracker.admin_cli import main
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.models import User
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import authenticate

PASSWORD = "correct horse battery"  # noqa: S105 - test value


def answers(*replies: str) -> Callable[[str], str]:
    queue: Iterator[str] = iter(replies)
    return lambda _prompt: next(queue)


@pytest.fixture
def settings(db_url: str) -> Settings:
    return Settings(database_url=db_url, _env_file=None)


def _users(settings: Settings) -> list[User]:
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as session:
        users = list(session.scalars(select(User)))
    engine.dispose()
    return users


def _signs_in(settings: Settings, username: str, password: str) -> bool:
    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as session:
        ok = authenticate(session, username, password) is not None
    engine.dispose()
    return ok


def test_create_user_defaults_to_admin(settings: Settings, capsys) -> None:
    code = main(["create-user", "Frank"], prompt=answers(PASSWORD, PASSWORD), settings=settings)

    assert code == 0
    assert "created frank (admin)" in capsys.readouterr().out
    [user] = _users(settings)
    assert user.role == Role.ADMIN
    assert _signs_in(settings, "frank", PASSWORD)


def test_create_user_with_a_role(settings: Settings) -> None:
    main(
        ["create-user", "eddie", "--role", "editor"],
        prompt=answers(PASSWORD, PASSWORD),
        settings=settings,
    )

    assert _users(settings)[0].role == Role.EDITOR


@pytest.mark.parametrize(
    ("replies", "message"),
    [
        (("short", "short"), "12 to 256"),
        ((PASSWORD, "something else entirely"), "do not match"),
    ],
)
def test_bad_passwords_are_refused(
    settings: Settings, capsys, replies: tuple[str, str], message: str
) -> None:
    code = main(["create-user", "frank"], prompt=answers(*replies), settings=settings)

    assert code == 1
    assert message in capsys.readouterr().err
    assert _users(settings) == []


def test_a_taken_username_is_refused(settings: Settings, capsys) -> None:
    main(["create-user", "frank"], prompt=answers(PASSWORD, PASSWORD), settings=settings)

    code = main(["create-user", "FRANK"], prompt=answers(PASSWORD, PASSWORD), settings=settings)

    assert code == 1
    assert "taken" in capsys.readouterr().err


def test_reset_password(settings: Settings, capsys) -> None:
    main(["create-user", "frank"], prompt=answers(PASSWORD, PASSWORD), settings=settings)
    new = "a different passphrase"

    code = main(["reset-password", "Frank"], prompt=answers(new, new), settings=settings)

    assert code == 0
    assert "updated frank (admin)" in capsys.readouterr().out
    assert _signs_in(settings, "frank", new)
    assert not _signs_in(settings, "frank", PASSWORD)


def test_reset_password_for_an_unknown_user(settings: Settings, capsys) -> None:
    code = main(["reset-password", "nobody"], prompt=answers(), settings=settings)

    assert code == 1
    assert "no user named 'nobody'" in capsys.readouterr().err


def test_a_command_is_required(settings: Settings) -> None:
    with pytest.raises(SystemExit):
        main([], settings=settings)
