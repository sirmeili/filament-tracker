"""Where Home Assistant's MQTT broker is, from MQTT_URL, MQTT_USER and MQTT_PASSWORD."""

import ssl
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import SecretStr

DEFAULT_PORTS = {"mqtt": 1883, "mqtts": 8883}


@dataclass(frozen=True)
class BrokerConfig:
    host: str
    port: int
    tls: bool
    username: str | None = None
    password: SecretStr | None = None

    def tls_context(self) -> ssl.SSLContext | None:
        """For mqtts://, the system's trusted certificates with hostname checks."""
        return ssl.create_default_context() if self.tls else None


def parse_mqtt_url(url: str) -> tuple[str, int, bool]:
    """Host, port and whether to use TLS. Errors never repeat the URL, which could hold a
    password someone pasted into it."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ValueError("MQTT_URL must look like mqtt://host:1883 or mqtts://host:8883") from None
    if parts.scheme not in DEFAULT_PORTS:
        raise ValueError("MQTT_URL must start with mqtt:// or mqtts://")
    if parts.username is not None or parts.password is not None:
        raise ValueError("put the MQTT user and password in MQTT_USER and MQTT_PASSWORD")
    if not parts.hostname:
        raise ValueError("MQTT_URL needs a host, such as mqtt://homeassistant.local:1883")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ValueError("MQTT_URL must not have a path, ? or #")
    return parts.hostname, port or DEFAULT_PORTS[parts.scheme], parts.scheme == "mqtts"


def broker_config(
    url: str | None, username: str | None, password: SecretStr | None
) -> BrokerConfig | None:
    """The broker to publish to, or None when MQTT_URL is not set."""
    if not url:
        return None
    host, port, tls = parse_mqtt_url(url)
    return BrokerConfig(host, port, tls, username, password)
