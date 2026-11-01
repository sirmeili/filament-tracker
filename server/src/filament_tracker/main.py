from fastapi import FastAPI

from filament_tracker.api import health

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="Filament Tracker")
    app.include_router(health.router, prefix=API_PREFIX)
    return app
