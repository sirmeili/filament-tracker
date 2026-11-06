import ssl

import pytest
from pydantic import SecretStr, ValidationError

from filament_tracker.config import Settings
from filament_tracker.ha.broker import BrokerConfig, broker_config, parse_mqtt_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("mqtt://homeassistant.local", ("homeassistant.local", 1883, False)),
        ("mqtt://10.0.0.5:1884/", ("10.0.0.5", 1884, False)),
        ("mqtts://broker.example.com", ("broker.example.com", 8883, True)),
        ("mqtts://[fd00::5]:9000", ("fd00::5", 9000, True)),
    ],
)
def test_reads_host_port_and_tls(url: str, expected: tuple[str, int, bool]) -> None:
    assert parse_mqtt_url(url) == expected


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://host", "mqtt:// or mqtts://"),
        ("host:1883", "mqtt:// or mqtts://"),
        ("mqtt://user:hunter2@host", "MQTT_USER and MQTT_PASSWORD"),
        ("mqtt://:1883", "needs a host"),
        ("mqtt://host/topic", "path"),
        ("mqtt://host?x=1", "path"),
        ("mqtt://host:99999", "must look like"),
    ],
)
def test_refuses_bad_urls_without_repeating_them(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as error:
        parse_mqtt_url(url)
    assert "hunter2" not in str(error.value)


def test_no_url_means_no_broker() -> None:
    assert broker_config(None, "u", None) is None
    assert broker_config("", None, None) is None


def test_broker_config_and_tls() -> None:
    broker = broker_config("mqtts://broker.lan", "ha", SecretStr("pw"))
    assert broker == BrokerConfig("broker.lan", 8883, True, "ha", SecretStr("pw"))
    context = broker.tls_context()
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname and context.verify_mode is ssl.CERT_REQUIRED
    assert BrokerConfig("h", 1883, False).tls_context() is None


def test_settings_read_the_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_URL", " mqtt://homeassistant.local:1883 ")
    monkeypatch.setenv("MQTT_USER", " filament ")
    monkeypatch.setenv("MQTT_PASSWORD", "broker-secret")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.mqtt_url == "mqtt://homeassistant.local:1883"
    assert settings.mqtt_user == "filament"
    assert settings.mqtt_password is not None
    assert "broker-secret" not in repr(settings)
    assert settings.ha_discovery_prefix == "homeassistant"


def test_settings_default_to_no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MQTT_URL", "MQTT_USER", "MQTT_PASSWORD", "HA_DISCOVERY_PREFIX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MQTT_USER", "  ")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.mqtt_url is None and settings.mqtt_user is None


def test_a_blank_url_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_URL", " ")
    assert Settings(_env_file=None).mqtt_url is None  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MQTT_URL", "mqtt://user:hunter2@host"),
        ("HA_DISCOVERY_PREFIX", "home assistant"),
        ("HA_DISCOVERY_PREFIX", "/homeassistant"),
    ],
)
def test_bad_settings_are_refused_without_echoing(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert value not in str(error.value)
    assert "hunter2" not in str(error.value)
