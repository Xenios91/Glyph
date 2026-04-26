import threading
from contextlib import asynccontextmanager

from loguru import logger

from fastapi import FastAPI

from app.config.settings import get_settings
from app.database.sql_service import SQLUtil
from app.database.session_handler import init_async_databases
from app.processing.task_management import EventWatcher
from app.services.task_service import TaskService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown logic correctly."""
    logger.info("Starting up Glyph service...")

    try:
        get_settings()
        logger.info("Configuration loaded successfully.")
    except RuntimeError as e:
        logger.critical("Configuration failed: {}", e)
        raise

    logger.bind(event="startup").info("Logging initialized")

    try:
        SQLUtil.init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.exception("Failed to initialize database")
        raise RuntimeError("Database initialization failed.") from e

    try:
        await init_async_databases()
        logger.info("Async databases initialized.")
    except Exception as e:
        logger.exception("Failed to initialize async databases")
        raise RuntimeError("Async database initialization failed.") from e

    try:
        threading.Thread(target=TaskService.start_service, daemon=True).start()
        logger.info("Task service started in background thread.")
    except Exception as e:
        logger.exception("Failed to start TaskService")
        raise RuntimeError("Task service startup failed.") from e

    event_watcher = EventWatcher()
    try:
        event_watcher.start_watching()
        logger.info("EventWatcher started.")
    except Exception as e:
        logger.exception("Failed to start EventWatcher")
        raise RuntimeError("EventWatcher startup failed.") from e

    try:
        yield
    finally:
        logger.info("Shutting down Glyph service...")
        event_watcher.stop_watching()
        logger.bind(event="shutdown").info("Logging shutdown summary")
