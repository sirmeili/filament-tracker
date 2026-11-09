"""Nightly database backups (Deployment in docs/SPEC.md).

At 03:00 in the server's time zone (the app's saved TZ, else `.env`), the database is
copied to BACKUP_DIR with SQLite's online backup API, so the server keeps running and the
copy is consistent. The newest 14 are kept. File names use UTC, like
`filament-20261110T080000Z.db`, so they sort in order whatever the time zone.

The settings key is never copied into the backups: a backup holds the saved secrets only in
their encrypted form. Keep the key (or SETTINGS_KEY) somewhere else.
"""

import logging
import os
import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from filament_tracker.db.types import utcnow

logger = logging.getLogger(__name__)

BACKUP_TIME = time(3, 0)
KEEP = 14
# How often the scheduler wakes to notice a changed time zone.
CHECK_SECONDS = 3600.0
NAME = re.compile(r"^filament-\d{8}T\d{6}Z\.db$")


def backup_name(now: datetime) -> str:
    return f"filament-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}.db"


def backup_database(source: Path, folder: Path, now: datetime) -> Path:
    """Copy the database to `folder` while it stays in use. The copy is written under a
    temporary name and renamed when complete, so a backup file is never half written."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / backup_name(now)
    partial = target.with_name(target.name + ".partial")
    partial.unlink(missing_ok=True)
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(partial)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    # It holds password hashes and sealed secrets: readable only by the server's user.
    os.chmod(partial, 0o600)
    partial.replace(target)
    return target


def backups(folder: Path) -> list[Path]:
    """The backups in `folder`, oldest first. Other files are left alone."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and NAME.fullmatch(p.name))


def prune(folder: Path, keep: int = KEEP) -> list[Path]:
    """Delete all but the newest `keep` backups; returns those deleted."""
    old = backups(folder)[:-keep] if keep > 0 else backups(folder)
    for path in old:
        path.unlink()
    return old


def next_run(now: datetime, time_zone: str) -> datetime:
    """The next 03:00 in `time_zone` after `now`, in UTC."""
    zone = ZoneInfo(time_zone)
    local = now.astimezone(zone)
    due = datetime.combine(local.date(), BACKUP_TIME, tzinfo=zone)
    if due <= local:
        due = datetime.combine(local.date() + timedelta(days=1), BACKUP_TIME, tzinfo=zone)
    return due.astimezone(UTC)


class BackupScheduler:
    """Runs `backup_database` and `prune` at each 03:00, in a background thread."""

    def __init__(
        self,
        source: Path,
        folder: Path,
        time_zone: Callable[[], str],
        *,
        keep: int = KEEP,
        clock: Callable[[], datetime] = utcnow,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self.source, self.folder, self.keep = source, folder, keep
        self._time_zone = time_zone
        self._clock = clock
        self._stopped = threading.Event()
        # Waits up to the given seconds; True means stop.
        self._wait = wait or self._stopped.wait
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="backups", daemon=True)
        self._thread.start()
        logger.info("nightly backups at 03:00 (%s) to %s", self._time_zone(), self.folder)

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(5)

    def run(self) -> None:
        while True:
            now = self._clock()
            due = next_run(now, self._time_zone())
            while now < due:
                if self._wait(min((due - now).total_seconds(), CHECK_SECONDS)):
                    return
                now = self._clock()
                if now < due:
                    # A time zone saved meanwhile moves the next backup.
                    due = next_run(now, self._time_zone())
            self.run_once(now)

    def run_once(self, now: datetime) -> Path | None:
        """One backup and prune. A failure is logged and retried the next night."""
        try:
            path = backup_database(self.source, self.folder, now)
            removed = prune(self.folder, self.keep)
        except (OSError, sqlite3.Error) as error:
            logger.error("nightly backup failed: %s", error)
            return None
        logger.info("backup written: %s (%d old removed)", path.name, len(removed))
        return path
