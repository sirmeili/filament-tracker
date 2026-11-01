from fastapi.testclient import TestClient

from filament_tracker.main import create_app


def test_health_is_ok_without_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_exists_only_under_the_versioned_prefix() -> None:
    client = TestClient(create_app())

    assert client.get("/health").status_code == 404
