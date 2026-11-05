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
