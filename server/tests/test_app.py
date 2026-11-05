from fastapi.testclient import TestClient
from sqlalchemy import inspect

from filament_tracker.config import Settings
from filament_tracker.main import create_app


def test_startup_migrates_the_database_and_opens_sessions(db_url: str) -> None:
    app = create_app(Settings(database_url=db_url, _env_file=None))

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        with app.state.session_factory() as session:
            assert "spool" in inspect(session.get_bind()).get_table_names()
