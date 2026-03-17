import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import GlyphConfig
from app.routers import (
    binaries,
    config,
    models,
    predictions,
    status,
)
from app.services import TaskService
from app.sql_service import SQLUtil
from app.views import views


def create_app() -> FastAPI:
    app = FastAPI()

    app.mount("/static", StaticFiles(directory="static"), name="static")

    app.include_router(views.router)
    app.include_router(binaries.router, prefix="/binaries")
    app.include_router(predictions.router, prefix="/predictions")
    app.include_router(models.router, prefix="/models")
    app.include_router(status.router, prefix="/status")
    app.include_router(config.router, prefix="/config")

    return app


threading.Thread(target=TaskService().start_service, daemon=True).start()
GlyphConfig.load_config()
SQLUtil.init_db()
app = create_app()
