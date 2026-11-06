from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from filament_tracker.api import (
    activity,
    auth,
    devices,
    edits,
    events,
    health,
    printers,
    review,
    scans,
    stock,
    users,
)
from filament_tracker.api.limits import BodySizeLimitMiddleware
from filament_tracker.api.security import SecurityHeadersMiddleware
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.printer.manager import PrinterManager
from filament_tracker.services.throttle import LoginThrottle
from filament_tracker.webapp import default_web_dir, mount_web_app

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        upgrade(settings.database_url)
        engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        printer_links = PrinterManager(settings.printers, app.state.session_factory)
        app.state.printers = printer_links
        printer_links.start()
        try:
            yield
        finally:
            printer_links.stop()
            engine.dispose()

    app = FastAPI(title="Filament Tracker", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_throttle = LoginThrottle()
    app.add_middleware(BodySizeLimitMiddleware)
    # Added last, so it runs first: headers go on every response, including a 413.
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    for module in (
        health,
        auth,
        scans,
        stock,
        edits,
        activity,
        review,
        devices,
        printers,
        events,
        users,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    mount_web_app(app, settings.web_dir or default_web_dir())
    return app
