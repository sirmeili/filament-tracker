from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

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
    setup,
    stock,
    tokens,
    users,
)
from filament_tracker.api import settings as app_settings
from filament_tracker.api.errors import validation_error
from filament_tracker.api.limits import BodySizeLimitMiddleware
from filament_tracker.api.security import SecurityHeadersMiddleware
from filament_tracker.api.session_renewal import SessionRenewalMiddleware
from filament_tracker.app_settings.crypto import SecretBox, load_key
from filament_tracker.app_settings.offline import database_file
from filament_tracker.app_settings.store import SettingsStore
from filament_tracker.config import Settings
from filament_tracker.db.engine import create_db_engine, create_session_factory
from filament_tracker.db.migrate import upgrade
from filament_tracker.ha.link import HomeAssistantLink
from filament_tracker.printer.manager import PrinterManager
from filament_tracker.services.backup import BackupScheduler
from filament_tracker.services.printers import seed_printers
from filament_tracker.services.setup import SetupGate
from filament_tracker.services.throttle import LoginThrottle
from filament_tracker.webapp import default_web_dir, mount_web_app

API_PREFIX = "/api/v1"


def _backups(settings: Settings, store: SettingsStore) -> BackupScheduler | None:
    """Start the nightly backups, if BACKUP_DIR is set and the database is a file."""
    source = database_file(settings.database_url)
    if settings.backup_dir is None or source is None:
        return None
    scheduler = BackupScheduler(source, settings.backup_dir, store.time_zone)
    scheduler.start()
    return scheduler


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        upgrade(settings.database_url)
        engine = create_db_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)
        box = SecretBox(load_key(settings.settings_key, settings.database_url))
        app.state.secret_box = box
        with app.state.session_factory() as session:
            seed_printers(session, box, settings.printers)
        printer_links = PrinterManager(app.state.session_factory, box)
        app.state.printers = printer_links
        printer_links.start()
        store = SettingsStore(settings, app.state.session_factory, box)
        app.state.settings_store = store
        home_assistant = HomeAssistantLink(store, app.state.session_factory)
        app.state.home_assistant = home_assistant
        home_assistant.start()
        app.state.setup_gate.start(app.state.session_factory)
        backups = _backups(settings, store)
        try:
            yield
        finally:
            if backups is not None:
                backups.stop()
            home_assistant.stop()
            printer_links.stop()
            engine.dispose()

    app = FastAPI(title="RollCall", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_throttle = LoginThrottle()
    # Wrong setup codes are throttled like sign-ins, but apart from them.
    app.state.setup_throttle = LoginThrottle()
    app.state.setup_gate = SetupGate()
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SessionRenewalMiddleware)
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
        tokens,
        setup,
        app_settings,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    mount_web_app(app, settings.web_dir or default_web_dir())
    return app
