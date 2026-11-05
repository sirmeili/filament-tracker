from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from filament_tracker.api import health
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        upgrade(settings.database_url)
        engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Filament Tracker", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router, prefix=API_PREFIX)
    return app
