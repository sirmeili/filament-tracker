"""Server settings, read from environment variables or a `.env` file.

The full list is in the Configuration table of docs/SPEC.md. Settings are added here in
the milestone that first uses them.
"""

from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Network = IPv4Network | IPv6Network
Networks = Annotated[tuple[Network, ...], NoDecode]

PRIVATE_NETWORKS = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128,fc00::/7,fe80::/10"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    @field_validator("trusted_networks", "forwarded_allow_ips", mode="before")
    @classmethod
    def _parse_networks(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(
                ip_network(part.strip(), strict=False) for part in value.split(",") if part.strip()
            )
        return value
