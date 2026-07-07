"""Shared utilities for managing background asyncio tasks.

Provides helpers to create fire-and-forget background tasks that are
protected from garbage collection, and to schedule delayed task cleanup.
"""

import asyncio
from typing import Any

from app.processing.task_management import TaskManager

# Global tracker to prevent garbage collection of fire-and-forget tasks
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


def create_background_task(coro: Any) -> asyncio.Task[None]:
    """Create a background task that won't be garbage-collected.

    Args:
        coro: The coroutine to run in the background.

    Returns:
        The created asyncio.Task.

    """
    task: asyncio.Task[None] = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def remove_task_delayed(task_uuid: str) -> None:
    """Remove a task from TaskManager after a delay.

    Args:
        task_uuid: The task UUID to remove.

    """
    await asyncio.sleep(10)
    TaskManager.remove_task(task_uuid)
