import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import get_settings
from app.database.sql_service import SQLUtil
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown logic correctly."""
    logger.info("Starting up Glyph service...")

    # 1. Initialize config
    try:
        get_settings()  # This will load and validate config
        logger.info("✅ Configuration loaded successfully.")
    except RuntimeError as e:
        logger.critical("Configuration failed: %s", e)
        raise

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