"""Values shared by the database, the state machine and the API."""

from enum import StrEnum


class SpoolState(StrEnum):
    SEALED = "sealed"
    OPEN = "open"
    EMPTY = "empty"


class EventType(StrEnum):
    RECEIVED = "received"
    OPENED = "opened"
    EMPTY = "empty"
    REVERT = "revert"


class EventSource(StrEnum):
    SCANNER = "scanner"
    UI = "ui"
    AMS = "ams"


class Role(StrEnum):
    """Web app roles. Each role can do everything the roles before it can."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return list(Role).index(self)

    def allows(self, needed: "Role") -> bool:
        return self.rank >= needed.rank
