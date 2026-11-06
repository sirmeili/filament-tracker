import socket

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from filament_tracker.config import PrinterConfig, Settings
from filament_tracker.db.models import Printer
from filament_tracker.main import create_app


def test_startup_migrates_the_database_and_opens_sessions(db_url: str) -> None:
    app = create_app(Settings(database_url=db_url, _env_file=None))

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        with app.state.session_factory() as session:
            assert "spool" in inspect(session.get_bind()).get_table_names()


def test_configured_printers_are_watched_while_the_app_runs(db_url: str) -> None:
    with socket.create_server(("127.0.0.1", 0)) as unused:
        port = unused.getsockname()[1]  # nothing listens here, so the link keeps retrying
    printer = PrinterConfig(
        name="P1S", host="127.0.0.1", port=port, serial="01P00A1", access_code="x"
    )
    app = create_app(Settings(database_url=db_url, printers=[printer], _env_file=None))

    with TestClient(app):
        manager = app.state.printers
        assert len(manager.links) == 1
        with app.state.session_factory() as session:
            assert session.query(Printer).one().serial == "01P00A1"

    assert not manager._thread.is_alive()
