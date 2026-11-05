"""Run Alembic migrations from code; the server upgrades its database on startup."""

from alembic import command
from alembic.config import Config

SCRIPT_LOCATION = "filament_tracker:migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)
