"""Server settings, read from environment variables or a `.env` file.

The full list is in the Configuration table of docs/SPEC.md. Settings are added here in
the milestone that first uses them.
"""

import re
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Network = IPv4Network | IPv6Network
Networks = Annotated[tuple[Network, ...], NoDecode]

PRIVATE_NETWORKS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128,fc00::/7,fe80::/10"


class PrinterConfig(BaseModel):
    """One entry of PRINTERS: a printer, or an MQTT proxy in front of it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=8883, ge=1, le=65535)
    # The printer's serial, or the alias a proxy uses in its topics.
    serial: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    access_code: SecretStr = Field(min_length=1, max_length=64)


class Settings(BaseSettings):
    # Errors never echo the input, which may be a secret (the salt, an access code).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: str = "sqlite:///./data/filament.db"
    admin_token: SecretStr | None = None
    # LAN ranges allowed to use bearer tokens, scanner routes and the API docs.
    trusted_networks: Networks = Field(default=PRIVATE_NETWORKS, validate_default=True)
    # Reverse proxies whose X-Forwarded-For header is believed. Empty: none.
    forwarded_allow_ips: Networks = Field(default="", validate_default=True)
    session_days: int = Field(default=30, ge=1, le=365)
    # Only for local development over plain HTTP; production sits behind HTTPS.
    cookie_secure: bool = True
    # The built web app. Unset: web/build in a source checkout, if it has been built.
    web_dir: Path | None = None
    # Printers to watch over MQTT, as a JSON list (see PrinterConfig).
    printers: list[PrinterConfig] = Field(default_factory=list)
    # The tag key-derivation constant (hex), served to devices at /devices/provisioning.
    # Never in the repo, never logged.
    bambu_kdf_salt: SecretStr | None = None
    # Home Assistant's MQTT broker, for discovery entities: mqtt://host[:port] or
    # mqtts://host[:port]. Unset: no entities are published.
    mqtt_url: str | None = None
    mqtt_user: str | None = None
    mqtt_password: SecretStr | None = None
    # Home Assistant's MQTT discovery prefix (its default is "homeassistant").
    ha_discovery_prefix: str = Field(
        default="homeassistant", pattern=r"^[A-Za-z0-9_-]{1,64}(/[A-Za-z0-9_-]{1,64}){0,3}$"
    )

    @field_validator("mqtt_url")
    @classmethod
    def _mqtt_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        # Parsing checks the value; the messages do not repeat it.
        from filament_tracker.ha.broker import parse_mqtt_url

        parse_mqtt_url(value.strip())
        return value.strip()

    @field_validator("mqtt_user")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("bambu_kdf_salt")
    @classmethod
    def _hex_salt(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        text = value.get_secret_value().strip()
        if not text:
            return None
        # The message must not echo the value.
        if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}){1,64}", text):
            raise ValueError("BAMBU_KDF_SALT must be hex (an even number of digits, at most 128)")
        return SecretStr(text.upper())

    @field_validator("printers")
    @classmethod
    def _unique_serials(cls, value: list[PrinterConfig]) -> list[PrinterConfig]:
        serials = [p.serial for p in value]
        if len(set(serials)) != len(serials):
            raise ValueError("each printer needs its own serial")
        return value

    @field_validator("trusted_networks", "forwarded_allow_ips", mode="before")
    @classmethod
    def _parse_networks(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(
                ip_network(part.strip(), strict=False) for part in value.split(",") if part.strip()
            )
        return value
