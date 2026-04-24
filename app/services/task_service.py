"""Service module for Glyph application background tasks."""

import queue
from typing import Any

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class TaskService:
    """Singleton service for managing background task queue."""

    service_queue: queue.Queue[tuple[Any, Any]] = queue.Queue()
    __instance: Any = None

    def __new__(cls) -> "TaskService":
        """Create or return the singleton instance of TaskService."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_service(cls) -> None:
        """Start the service loop to process tasks from the queue.

        Note: This service no longer calls .result() on futures. The EventWatcher
        is responsible for monitoring futures and invoking callbacks when they complete.
        This method simply manages the queue lifecycle.
        """
        while True:
            task: tuple[Any, Any] = cls.service_queue.get(block=True)
            job_uuid: str = task[0].uuid
            logger.info("Job queued: job_uuid=%s", job_uuid)
