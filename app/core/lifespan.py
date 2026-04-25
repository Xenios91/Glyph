import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.settings import get_settings
from app.database.sql_service import SQLUtil
from app.database.session_handler import init_async_databases
from app.processing.task_management import EventWatcher
from app.services.task_service import TaskService
from app.utils.logging_config import get_logger, log_startup_summary, log_shutdown_summary

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown logic correctly."""
    logger.info("Starting up Glyph service...")

    try:
        get_settings()
        logger.info("Configuration loaded successfully.")
    except RuntimeError as e:
        logger.critical("Configuration failed: %s", e, exc_info=True)
        raise

    # Log startup summary
    log_startup_summary()

    try:
        SQLUtil.init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.exception("Failed to initialize database.")
        raise RuntimeError("Database initialization failed.") from e

    try:
        await init_async_databases()
        logger.info("Async databases initialized.")
    except Exception as e:
        logger.exception("Failed to initialize async databases.")
        raise RuntimeError("Async database initialization failed.") from e

    try:
        threading.Thread(target=TaskService.start_service, daemon=True).start()
        logger.info("Task service started in background thread.")
    except Exception as e:
        logger.exception("Failed to start TaskService.")
        raise RuntimeError("Task service startup failed.") from e

    event_watcher = EventWatcher()
    try:
        event_watcher.start_watching()
        logger.info("EventWatcher started.")
    except Exception as e:
        logger.exception("Failed to start EventWatcher.")
        raise RuntimeError("EventWatcher startup failed.") from e

    try:
        yield
    finally:
        logger.info("Shutting down Glyph service...")
        event_watcher.stop_watching()
        log_shutdown_summary()
