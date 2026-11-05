from ipaddress import ip_network

import pytest
from pydantic import ValidationError

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


def test_network_defaults_are_the_private_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TRUSTED_NETWORKS", "FORWARDED_ALLOW_IPS", "SESSION_DAYS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert ip_network("192.168.0.0/16") in settings.trusted_networks
    assert ip_network("::1/128") in settings.trusted_networks
    assert settings.forwarded_allow_ips == ()
    assert settings.session_days == 30
    assert settings.cookie_secure is True


def test_networks_are_read_as_comma_separated_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_NETWORKS", " 10.1.0.0/16 , 192.168.1.7 ")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "192.168.1.5")

    settings = Settings(_env_file=None)

    assert settings.trusted_networks == (ip_network("10.1.0.0/16"), ip_network("192.168.1.7/32"))
    assert settings.forwarded_allow_ips == (ip_network("192.168.1.5/32"),)


@pytest.mark.parametrize(
    ("name", "value"),
    [("TRUSTED_NETWORKS", "not-a-network"), ("SESSION_DAYS", "0"), ("SESSION_DAYS", "400")],
)
def test_bad_values_are_refused(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
