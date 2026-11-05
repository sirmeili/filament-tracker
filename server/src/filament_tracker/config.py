"""Server settings, read from environment variables or a `.env` file.

The full list is in the Configuration table of docs/SPEC.md. Settings are added here in
the milestone that first uses them.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/filament.db"
    admin_token: SecretStr | None = None
