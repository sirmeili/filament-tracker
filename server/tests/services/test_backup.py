"""Nightly backups: the online backup, pruning to 14, and 03:00 in the time zone, with a
fake clock (Deployment in docs/SPEC.md)."""

import logging
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from filament_tracker.admin_cli import main as admin_main
from filament_tracker.config import Settings
from filament_tracker.main import _backups, create_app
from filament_tracker.services.backup import (
    CHECK_SECONDS,
    KEEP,
    BackupScheduler,
    backup_database,
    backup_name,
    backups,
    next_run,
    prune,
)


def _database(path: Path, rows: int = 3) -> Path:
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE spool (id INTEGER PRIMARY KEY, name TEXT)")
        db.executemany("INSERT INTO spool (name) VALUES (?)", [(f"s{i}",) for i in range(rows)])
    db.close()
    return path


def _count(path: Path) -> int:
    db = sqlite3.connect(path)
    try:
        return db.execute("SELECT count(*) FROM spool").fetchone()[0]
    finally:
        db.close()


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


# --- One backup -----------------------------------------------------------------------------


def test_a_backup_is_a_complete_copy_named_in_utc(tmp_path: Path) -> None:
    source = _database(tmp_path / "filament.db")

    path = backup_database(source, tmp_path / "backups", at("2026-11-10T03:00:00-06:00"))

    assert path.name == "filament-20261110T090000Z.db"
    assert _count(path) == 3
    assert not list((tmp_path / "backups").glob("*.partial"))


def test_a_backup_includes_writes_still_in_the_wal(tmp_path: Path) -> None:
    source = _database(tmp_path / "filament.db")
    writer = sqlite3.connect(source)
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO spool (name) VALUES ('new')")
    writer.commit()

    path = backup_database(source, tmp_path / "backups", at("2026-11-10T09:00:00Z"))
    writer.close()

    assert _count(path) == 4


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_backup_is_readable_only_by_the_server(tmp_path: Path) -> None:
    source = _database(tmp_path / "filament.db")

    path = backup_database(source, tmp_path / "backups", at("2026-11-10T09:00:00Z"))

    assert path.stat().st_mode & 0o777 == 0o600


def test_a_left_over_partial_file_is_replaced(tmp_path: Path) -> None:
    source = _database(tmp_path / "filament.db")
    folder = tmp_path / "backups"
    folder.mkdir()
    now = at("2026-11-10T09:00:00Z")
    (folder / (backup_name(now) + ".partial")).write_text("half")

    path = backup_database(source, folder, now)

    assert _count(path) == 3
    assert [p.name for p in folder.iterdir()] == [path.name]


# --- Keeping 14 -----------------------------------------------------------------------------


def test_prune_keeps_the_newest_and_leaves_other_files(tmp_path: Path) -> None:
    start = at("2026-11-01T09:00:00Z")
    names = [backup_name(start + timedelta(days=d)) for d in range(KEEP + 3)]
    for name in names:
        (tmp_path / name).write_text("x")
    (tmp_path / "notes.txt").write_text("mine")
    (tmp_path / "filament-old.db").write_text("mine")

    removed = prune(tmp_path)

    assert [p.name for p in removed] == names[:3]
    assert [p.name for p in backups(tmp_path)] == names[3:]
    assert (tmp_path / "notes.txt").exists()
    assert (tmp_path / "filament-old.db").exists()


def test_prune_handles_a_missing_folder_and_keep_zero(tmp_path: Path) -> None:
    assert prune(tmp_path / "missing") == []
    (tmp_path / backup_name(at("2026-11-01T09:00:00Z"))).write_text("x")

    assert len(prune(tmp_path, keep=0)) == 1


# --- 03:00 in the time zone -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        ("2026-11-10T08:59:00Z", "America/Chicago", "2026-11-10T09:00:00Z"),  # 02:59 CST
        ("2026-11-10T09:00:00Z", "America/Chicago", "2026-11-11T09:00:00Z"),  # exactly 03:00
        ("2026-11-10T12:00:00Z", "UTC", "2026-11-11T03:00:00Z"),
        ("2026-11-10T01:00:00Z", "UTC", "2026-11-10T03:00:00Z"),
        # Daylight saving time ends on 1 November 2026: 03:00 is CDT before, CST after.
        ("2026-10-31T12:00:00Z", "America/Chicago", "2026-11-01T09:00:00Z"),
        ("2026-10-30T12:00:00Z", "America/Chicago", "2026-10-31T08:00:00Z"),
        # It starts on 8 March 2026 (02:00 becomes 03:00, so 03:00 exists).
        ("2026-03-07T12:00:00Z", "America/Chicago", "2026-03-08T08:00:00Z"),
        ("2026-11-10T12:00:00Z", "Asia/Tokyo", "2026-11-10T18:00:00Z"),
    ],
)
def test_the_next_backup_is_at_three_local_time(now: str, zone: str, expected: str) -> None:
    assert next_run(at(now), zone) == at(expected)


# --- The scheduler, with a fake clock --------------------------------------------------------


class FakeTime:
    """A clock that moves only when the scheduler waits; stops after `nights` backups."""

    def __init__(self, start: str, scheduler_runs: list[datetime], nights: int) -> None:
        self.now = at(start)
        self.waits: list[float] = []
        self.runs = scheduler_runs
        self.nights = nights

    def clock(self) -> datetime:
        return self.now

    def wait(self, seconds: float) -> bool:
        if len(self.runs) >= self.nights:
            return True
        self.waits.append(seconds)
        self.now += timedelta(seconds=seconds)
        return False


def _scheduler(
    tmp_path: Path, start: str, nights: int, zone: list[str] | None = None
) -> tuple[BackupScheduler, FakeTime, list[datetime]]:
    runs: list[datetime] = []
    fake = FakeTime(start, runs, nights)
    zones = zone or ["America/Chicago"]
    scheduler = BackupScheduler(
        _database(tmp_path / "filament.db"),
        tmp_path / "backups",
        lambda: zones[0],
        keep=2,
        clock=fake.clock,
        wait=fake.wait,
    )
    real = scheduler.run_once

    def recorded(now: datetime) -> Path | None:
        runs.append(now)
        return real(now)

    scheduler.run_once = recorded  # type: ignore[method-assign]
    return scheduler, fake, runs


def test_backups_run_each_night_at_three_and_keep_the_newest(tmp_path: Path) -> None:
    scheduler, fake, runs = _scheduler(tmp_path, "2026-11-09T20:00:00Z", nights=3)

    scheduler.run()

    assert runs == [at(f"2026-11-{d}T09:00:00Z") for d in (10, 11, 12)]
    # It wakes at least hourly, to notice a new time zone.
    assert max(fake.waits) == CHECK_SECONDS
    assert [p.name for p in backups(tmp_path / "backups")] == [
        "filament-20261111T090000Z.db",
        "filament-20261112T090000Z.db",
    ]


def test_a_new_time_zone_moves_the_next_backup(tmp_path: Path) -> None:
    zone = ["America/Chicago"]
    scheduler, fake, runs = _scheduler(tmp_path, "2026-11-09T20:00:00Z", nights=1, zone=zone)
    original_wait = fake.wait

    def wait(seconds: float) -> bool:
        zone[0] = "UTC"  # saved on the Settings page while waiting
        return original_wait(seconds)

    scheduler._wait = wait  # noqa: SLF001 - the test swaps the fake wait

    scheduler.run()

    assert runs == [at("2026-11-10T03:00:00Z")]


def test_a_failed_backup_is_logged_and_tried_the_next_night(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    folder = tmp_path / "backups"
    folder.write_text("a file where the folder should be")
    scheduler = BackupScheduler(_database(tmp_path / "filament.db"), folder, lambda: "UTC")

    assert scheduler.run_once(at("2026-11-10T03:00:00Z")) is None
    assert "nightly backup failed" in caplog.text


def test_start_and_stop_run_a_real_thread(tmp_path: Path) -> None:
    scheduler = BackupScheduler(_database(tmp_path / "filament.db"), tmp_path, lambda: "UTC")

    scheduler.start()
    scheduler.stop()

    assert scheduler._thread is not None  # noqa: SLF001
    assert not scheduler._thread.is_alive()  # noqa: SLF001


# --- The server and ft-admin ----------------------------------------------------------------


def test_the_server_runs_backups_only_with_a_backup_dir(
    tmp_path: Path, db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="filament_tracker.services.backup")
    with TestClient(create_app(Settings(database_url=db_url, _env_file=None))):
        pass
    assert "nightly backups" not in caplog.text

    settings = Settings(database_url=db_url, backup_dir=tmp_path / "b", _env_file=None)
    with TestClient(create_app(settings)):
        pass

    assert "nightly backups at 03:00 (UTC)" in caplog.text


def test_in_memory_databases_are_not_backed_up(tmp_path: Path) -> None:
    settings = Settings(database_url="sqlite://", backup_dir=tmp_path, _env_file=None)

    assert _backups(settings, None) is None  # type: ignore[arg-type]


def test_ft_admin_backup_writes_one_now(
    tmp_path: Path, db_url: str, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(database_url=db_url, backup_dir=tmp_path / "b", _env_file=None)

    assert admin_main(["backup"], settings=settings) == 0

    assert "backup written" in capsys.readouterr().out
    assert len(backups(tmp_path / "b")) == 1


@pytest.mark.parametrize("problem", ["no backup dir", "no database file"])
def test_ft_admin_backup_needs_a_folder_and_a_database(
    tmp_path: Path, db_url: str, problem: str, capsys: pytest.CaptureFixture[str]
) -> None:
    if problem == "no backup dir":
        settings = Settings(database_url=db_url, _env_file=None)
    else:
        url = f"sqlite:///{(tmp_path / 'missing.db').as_posix()}"
        settings = Settings(database_url=url, backup_dir=tmp_path, _env_file=None)

    assert admin_main(["backup"], settings=settings) == 1
    assert "set BACKUP_DIR" in capsys.readouterr().err
