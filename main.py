# main.py
import logging
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import GlyphConfig
from app.routers import binaries, config, models, predictions, status
from app.services import TaskService
from app.sql_service import SQLUtil
from app.views import views

# --- Configure logging early (before importing anything that might log) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("glyph_log.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown logic correctly."""
    logger.info("Starting up Glyph service...")

    # 1. Initialize config
    if not GlyphConfig.load_config():
        logger.critical("Configuration failed. Exiting.")
        raise RuntimeError("Configuration failed.")

    logger.info("✅ Configuration loaded successfully.")

    # 2. Initialize DB (with proper error handling)
    try:
        SQLUtil.init_db()
        logger.info("✅ Database initialized.")
    except Exception as e:
        logger.exception("❌ Failed to initialize database.")
        raise RuntimeError("Database initialization failed.") from e

    # 3. Start TaskService *after* DB/config are ready
    try:
        threading.Thread(target=TaskService.start_service, daemon=True).start()
        logger.info("✅ Task service started in background thread.")
    except Exception as e:
        logger.exception("❌ Failed to start TaskService.")
        raise RuntimeError("Task service startup failed.") from e

    try:
        yield
    finally:
        logger.info("Shutting down Glyph service...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Glyph API",
        description="Binary analysis and powered by machine learning",
        version="0.0.2",
        lifespan=lifespan,
    )

    # Mount static files (only after logging/db/config are prepped)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted at /static")
    except Exception as e:
        logger.warning("Static files mount failed: %s", e)

    # Include routers
    app.include_router(views.router)
    app.include_router(binaries.router, prefix="/binaries")
    app.include_router(predictions.router, prefix="/predictions")
    app.include_router(models.router, prefix="/models")
    app.include_router(status.router, prefix="/status")
    app.include_router(config.router, prefix="/config")

    logger.info("✅ All routers registered.")
    return app


app = create_app()
