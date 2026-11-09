from ipaddress import ip_network

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

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


def test_printers_come_from_a_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "PRINTERS",
        '[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A1", "access_code": "12345678"},'
        ' {"name": "Via proxy", "host": "proxy.lan", "port": 18883, "serial": "garage",'
        ' "access_code": "abc"}]',
    )

    printers = Settings(_env_file=None).printers

    assert [(p.name, p.host, p.port, p.serial) for p in printers] == [
        ("P1S", "192.168.1.40", 8883, "01P00A1"),
        ("Via proxy", "proxy.lan", 18883, "garage"),
    ]
    assert printers[0].access_code.get_secret_value() == "12345678"
    assert "12345678" not in repr(printers)


def test_no_printers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRINTERS", raising=False)

    assert Settings(_env_file=None).printers == []


@pytest.mark.parametrize(
    "printers",
    [
        '[{"name": "P1S", "host": "h", "serial": "bad serial!", "access_code": "x"}]',
        '[{"name": "P1S", "host": "h", "serial": "s", "access_code": ""}]',
        '[{"name": "P1S", "host": "h", "port": 70000, "serial": "s", "access_code": "x"}]',
        '[{"name": "P1S", "host": "h", "serial": "s", "access_code": "x", "extra": 1}]',
        '[{"name": "A", "host": "h", "serial": "s", "access_code": "x"},'
        ' {"name": "B", "host": "h", "serial": "s", "access_code": "y"}]',
        "not json",
    ],
)
def test_bad_printers_are_refused(monkeypatch: pytest.MonkeyPatch, printers: str) -> None:
    monkeypatch.setenv("PRINTERS", printers)

    with pytest.raises((ValidationError, SettingsError)):
        Settings(_env_file=None)


SALT = "00112233445566778899aabbccddeeff"  # made up; the real constant is never in the repo


def test_the_kdf_salt_is_hex_normalised_and_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAMBU_KDF_SALT", f" {SALT} ")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.bambu_kdf_salt is not None
    assert settings.bambu_kdf_salt.get_secret_value() == SALT.upper()
    assert SALT.upper() not in repr(settings) and SALT not in repr(settings)


def test_an_empty_kdf_salt_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAMBU_KDF_SALT", "")

    assert Settings(_env_file=None).bambu_kdf_salt is None  # type: ignore[call-arg]


@pytest.mark.parametrize("value", ["xyz123", "abc", "ab" * 65])
def test_a_bad_kdf_salt_is_refused_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("BAMBU_KDF_SALT", value)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert "must be hex" in str(error.value)
    assert value not in str(error.value)


def test_a_bad_printer_entry_does_not_echo_the_access_code(monkeypatch: pytest.MonkeyPatch) -> None:
    code = "secret-access-code"
    monkeypatch.setenv(
        "PRINTERS",
        f'[{{"name": "P1S", "host": "h", "serial": "bad serial!", "access_code": "{code}"}}]',
    )

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert code not in str(error.value)


def test_the_time_zone_defaults_to_utc_and_is_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TZ", raising=False)
    assert Settings(_env_file=None).tz == "UTC"  # type: ignore[call-arg]
    monkeypatch.setenv("TZ", " America/New_York ")
    assert Settings(_env_file=None).tz == "America/New_York"  # type: ignore[call-arg]
    monkeypatch.setenv("TZ", "")
    assert Settings(_env_file=None).tz == "UTC"  # type: ignore[call-arg]
    monkeypatch.setenv("TZ", "Mars/Olympus")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "Mars/Olympus" not in str(error.value)
