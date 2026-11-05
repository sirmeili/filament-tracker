import pytest

from filament_tracker.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./data/filament.db"
    assert settings.admin_token is None


def test_values_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///elsewhere.db")
    monkeypatch.setenv("ADMIN_TOKEN", "secret-value")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///elsewhere.db"
    assert settings.admin_token is not None
    assert settings.admin_token.get_secret_value() == "secret-value"


def test_admin_token_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "secret-value")

    settings = Settings(_env_file=None)

    assert "secret-value" not in repr(settings)
    assert "secret-value" not in str(settings.model_dump())
