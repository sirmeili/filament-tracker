"""Alembic environment.

The database URL comes from the caller (`filament_tracker.db.migrate`) or, when Alembic is
run from the command line, from the server settings. Batch mode lets SQLite alter tables.
"""

from alembic import context

from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine
from filament_tracker.db.models import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or Settings().database_url

engine = create_db_engine(url)
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
