"""Service module for Glyph application background tasks."""

import queue
from typing import Any

from loguru import logger
from app.utils.request_context import restore_request_context, clear_request_context


class TaskService:
    """Singleton service for managing background task queue.

    Queue items should be tuples of (request, captured_context) where
    captured_context is a CapturedContext snapshot taken on the request
    thread before queuing.
    """

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
            item: tuple[Any, Any] = cls.service_queue.get(block=True)
            task = item[0]
            captured_ctx = item[1]
            job_uuid: str = task.uuid
            # Restore request context from the snapshot captured on the request thread
            restore_request_context(captured_ctx, override_task_id=job_uuid)
            logger.debug(
                "Job queued: {}", job_uuid)
            clear_request_context()
