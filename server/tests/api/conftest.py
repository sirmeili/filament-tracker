from collections.abc import Iterator

import pytest
from api_helpers import ADMIN_TOKEN, BASE_URL, LAN_CLIENT, register
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from filament_tracker.config import Settings
from filament_tracker.main import create_app


@pytest.fixture
def app(db_url: str) -> FastAPI:
    return create_app(Settings(database_url=db_url, admin_token=ADMIN_TOKEN, _env_file=None))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A browser or scanner on the LAN, over HTTPS (so Secure cookies are sent)."""
    with TestClient(app, base_url=BASE_URL, client=LAN_CLIENT) as client:
        yield client


@pytest.fixture
def db(app: FastAPI, client: TestClient) -> Iterator[Session]:
    """A separate session for checking what the API stored."""
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def token(client: TestClient) -> str:
    return register(client)
