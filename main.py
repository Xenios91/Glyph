import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import GlyphConfig
from app.routers import (
    binaries_api,
    config_api,
    models_api,
    predictions_api,
    status_api,
    views,
)
from app.services import TaskService
from app.sql_service import SQLUtil


def create_app() -> FastAPI:
    app = FastAPI()

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(views.router, prefix="")
    app.include_router(binaries_api.router, prefix="binaries")
    app.include_router(predictions_api.router, prefix="predictions")
    app.include_router(models_api.router, prefix="models")
    app.include_router(status_api.router, prefix="status")
    app.include_router(config_api.router, prefix="config")

    return app


threading.Thread(target=TaskService().start_service, daemon=True).start()
GlyphConfig.load_config()
SQLUtil.init_db()
app = create_app()
