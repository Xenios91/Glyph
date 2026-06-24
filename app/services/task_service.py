"""Service module for Glyph application background tasks."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from loguru import logger

from app.utils.request_context import clear_request_context, restore_request_context


class _TaskRequest(Protocol):
    """Protocol for objects that have a uuid attribute used as task identifier."""

    uuid: str


class TaskService:
    """Singleton service for managing background task queue.

    Queue items should be tuples of (request, captured_context) where
    captured_context is a CapturedContext snapshot taken on the request
    thread before queuing.

    The service loop runs as an asyncio task, consuming items from an
    async queue and restoring the captured request context for each job.
    """

    _service_queue: asyncio.Queue[tuple[_TaskRequest, Any]] | None = None
    __instance: TaskService | None = None

    def __new__(cls) -> TaskService:
        """Create or return the singleton instance of TaskService."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        """Initialize the async service queue (idempotent)."""
        if self._service_queue is None:
            self._service_queue = asyncio.Queue()

    @property
    def service_queue(self) -> asyncio.Queue[tuple[_TaskRequest, Any]]:
        """Return the async service queue."""
        return self._service_queue  # type: ignore[return-value]

    @classmethod
    async def start_service(cls) -> None:
        """Start the service loop to process tasks from the queue.

        Note: This service no longer calls .result() on futures. The EventWatcher
        is responsible for monitoring futures and invoking callbacks when they complete.
        This method simply manages the queue lifecycle.
        """
        instance = cls()
        queue = instance.service_queue
        while True:  # pragma: no cover
            try:
                item: tuple[_TaskRequest, Any] = await queue.get()
                task = item[0]
                captured_ctx = item[1]
                job_uuid: str = task.uuid
                restore_request_context(captured_ctx, override_task_id=job_uuid)
                logger.debug("Job queued: {}", job_uuid)
                clear_request_context()
            finally:
                queue.task_done()

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Reset singleton state and clear the service queue for test isolation."""
        cls.__instance = None
        old_queue = cls._service_queue
        cls._service_queue = asyncio.Queue()
        # Drain the old queue to avoid leaving items
        if old_queue is not None:
            while not old_queue.empty():
                try:
                    old_queue.get_nowait()
                    try:
                        old_queue.task_done()
                    except ValueError:
                        pass  # Items added via _queue.append() don't increment unfinished_tasks
                except asyncio.QueueEmpty:
                    break
        logger.debug("TaskService state reset for testing")
