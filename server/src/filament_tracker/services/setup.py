"""First-start setup (Settings and first start in docs/SPEC.md).

Setup is open while no Admin account exists. While it is open, each start of the server
makes a new random setup code and writes it to the log, so only someone who can read the
log can finish setup. Creating the first Admin closes setup for good.
"""

import hmac
import logging
import secrets
import threading

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, sessionmaker

from filament_tracker.db.models import User
from filament_tracker.domain.enums import Role

logger = logging.getLogger(__name__)

# No I, L, O, U, 0 or 1, so the code is easy to read from a log and type.
ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
GROUPS = 3
GROUP_LENGTH = 4


def new_code() -> str:
    """A code like `K7QM-X3RD-9PTA` (about 59 bits)."""
    groups = ("".join(secrets.choice(ALPHABET) for _ in range(GROUP_LENGTH)) for _ in range(GROUPS))
    return "-".join(groups)


def normalize(code: str) -> str:
    """Upper case, without spaces or dashes, so a code typed either way matches."""
    return "".join(ch for ch in code.upper() if ch not in " -")


def setup_open(session: Session) -> bool:
    """True until the first Admin account exists."""
    return not session.scalar(select(exists().where(User.role == Role.ADMIN)))


class SetupGate:
    """Holds this start's setup code. `lock` keeps two setups from running at once."""

    def __init__(self) -> None:
        self._code: str | None = None
        self.lock = threading.Lock()

    def start(self, sessions: sessionmaker[Session]) -> None:
        """Make a new code and write it to the log, if setup is open."""
        with sessions() as session:
            if not setup_open(session):
                self._code = None
                return
        self._code = new_code()
        # A warning, so it shows with the server's default log level.
        logger.warning(
            "First-start setup is open. Open the web app from your LAN and enter the "
            "setup code: %s",
            self._code,
        )

    def matches(self, entered: str) -> bool:
        if self._code is None:
            return False
        return hmac.compare_digest(normalize(entered).encode(), normalize(self._code).encode())

    def close(self) -> None:
        self._code = None
