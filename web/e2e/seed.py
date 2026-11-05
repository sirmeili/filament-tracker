"""Create the end-to-end test database with one user per role.

Run with the server's environment: uv run --project ../server python e2e/seed.py <db-url>
"""

import sys

from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.domain.enums import Role
from filament_tracker.services.accounts import create_user

PASSWORD = "e2e password 123"  # noqa: S105 - test value for a throwaway database


def main(url: str) -> None:
    upgrade(url)
    engine = create_db_engine(url)
    with create_session_factory(engine)() as session:
        for role in Role:
            create_user(session, f"e2e-{role.value}", PASSWORD, role)
        session.commit()
    engine.dispose()


if __name__ == "__main__":
    main(sys.argv[1])
