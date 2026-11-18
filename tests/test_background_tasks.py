"""Unit tests for the background-task GC guard in ``app.utils.background_tasks``.

``create_background_task`` is the fire-and-forget guard for every background
task in the app: while a task runs it must be retained in ``_BACKGROUND_TASKS``
(or it can be garbage-collected mid-run), and it must be discarded on
completion. ``remove_task_delayed`` must wait the configured grace period
before removing the task from the ``TaskManager`` registry.
"""

import asyncio
from typing import Any
from unittest import mock

import pytest
from app.processing.task_management import TaskManager
from app.utils import background_tasks


class TestCreateBackgroundTask:
    """create_background_task tracking and discard behavior."""

    @pytest.mark.asyncio
    async def test_create_background_task_tracks_and_discards(self) -> None:
        """Task is tracked while running and discarded after completion."""
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(0.01)

        task = background_tasks.create_background_task(work())

        # While running, the task must be retained in the GC guard set.
        await started.wait()
        assert task in background_tasks._BACKGROUND_TASKS  # pyright: ignore[reportPrivateUsage]

        await task
        # After completion the done-callback must have discarded it.
        assert task not in background_tasks._BACKGROUND_TASKS  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_create_background_task_discards_on_exception(self) -> None:
        """A task that raises is still discarded from the guard set."""

        async def boom() -> None:
            raise RuntimeError("expected failure")

        task = background_tasks.create_background_task(boom())
        with pytest.raises(RuntimeError, match="expected failure"):
            await task
        assert task not in background_tasks._BACKGROUND_TASKS  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_create_background_task_returns_asyncio_task(self) -> None:
        """The helper returns a real asyncio.Task."""

        async def work() -> None:
            return None

        task = background_tasks.create_background_task(work())
        assert isinstance(task, asyncio.Task)
        await task


class TestRemoveTaskDelayed:
    """remove_task_delayed sleep-then-remove behavior."""

    @pytest.mark.asyncio
    async def test_remove_task_delayed_waits_then_removes(self) -> None:
        """Must sleep the configured delay, then call TaskManager.remove_task."""
        with (
            mock.patch.object(background_tasks.asyncio, "sleep", new=mock.AsyncMock()) as mock_sleep,
            mock.patch.object(TaskManager, "remove_task") as mock_remove,
        ):
            await background_tasks.remove_task_delayed("task-uuid-123")

        mock_sleep.assert_awaited_once_with(background_tasks.TASK_REMOVAL_DELAY_SECONDS)
        mock_remove.assert_called_once_with("task-uuid-123")

    @pytest.mark.asyncio
    async def test_remove_task_delayed_uses_configured_constant(self, monkeypatch: Any) -> None:
        """The delay must come from TASK_REMOVAL_DELAY_SECONDS, not a literal."""
        monkeypatch.setattr(background_tasks, "TASK_REMOVAL_DELAY_SECONDS", 0)
        with (
            mock.patch.object(background_tasks.asyncio, "sleep", new=mock.AsyncMock()) as mock_sleep,
            mock.patch.object(TaskManager, "remove_task") as mock_remove,
        ):
            await background_tasks.remove_task_delayed("task-uuid-456")

        mock_sleep.assert_awaited_once_with(0)
        mock_remove.assert_called_once_with("task-uuid-456")
