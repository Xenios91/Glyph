"""Application lifespan management for Glyph.

Handles startup and shutdown events including database initialization,
task service startup, event watcher configuration, and graceful cleanup.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.config.settings import get_settings
from app.database.session_handler import dispose_async_engines, init_async_databases
from app.processing.task_management import EventWatcher
from app.services.task_service import TaskService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup sequence:
        1. Load and validate configuration
        2. Initialize async database connections
        3. Start background task service
        4. Start event watcher for task completion callbacks

    On shutdown:
        1. Stop event watcher
        2. Dispose database engines
        3. Close loguru handlers

    Args:
        app: The FastAPI application instance.

    Yields:
        None while the application is running.

    Raises:
        RuntimeError: If any startup step fails.
    """
    logger.info("Starting up Glyph service")

    try:
        get_settings()
        logger.info("Configuration loaded successfully")
    except RuntimeError as e:
        logger.critical("Configuration load failed: {}", e)
        raise

    try:
        await init_async_databases()
        logger.info("Async databases initialized")
    except Exception as e:
        logger.exception("Failed to initialize async databases")
        raise RuntimeError("Async database initialization failed.") from e

    try:
        task = asyncio.create_task(TaskService.start_service())
        task.add_done_callback(
            lambda t: (
                logger.warning("Task service background task completed")
                if t.exception() is None
                else logger.error("Task service background task failed: %s", t.exception())
            )
        )
        logger.info("Task service started as async background task")
    except Exception as e:
        logger.exception("Failed to start TaskService")
        raise RuntimeError("Task service startup failed.") from e

    event_watcher = EventWatcher()
    try:
        event_watcher.start_watching()
    except Exception as e:
        logger.exception("Failed to start EventWatcher")
        raise RuntimeError("EventWatcher startup failed.") from e

    try:
        yield
    finally:
        logger.info("Shutting down Glyph service")
        event_watcher.stop_watching()
        try:
            await dispose_async_engines()
            logger.info("Async database engines disposed")
        except Exception:
            logger.exception("Failed to dispose async database engines")
        logger.complete()
