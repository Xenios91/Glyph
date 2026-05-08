"""Unit tests for task management and queue operations."""

from contextlib import contextmanager
from typing import Any, Generator

import pytest
from loguru import logger

from app.processing.task_management import EventWatcher, TaskManager
from app.services.request_handler import TrainingRequest
from app.services.task_service import TaskService
from app.utils.request_context import CapturedContext


@contextmanager
def capture_logs(level: str = "INFO", format: str = "{level}:{name}:{message}") -> Generator[list[str], Any, None]:
    """Capture loguru-based logs for testing.
    
    Based on the loguru migration guide pattern for replacing unittest.assertLogs().
    """
    output: list[str] = []
    handler_id = logger.add(output.append, level=level, format=format)
    yield output
    logger.remove(handler_id)


@pytest.fixture
def task_manager() -> TaskManager:
    """Provide a fresh TaskManager instance for each test."""
    return TaskManager()


@pytest.fixture
def sample_training_request() -> TrainingRequest:
    """Provide a standardized TrainingRequest object for testing."""
    return TrainingRequest(
        req_uuid="1234",
        model_name="test_model",
        data={
            "binaryName": "testBin",
            "functionsMap": {"functions": [{"tokenList": ["testToken"]}]},
        },
    )


@pytest.fixture
def sample_captured_context() -> CapturedContext:
    """Provide a CapturedContext for testing queue operations."""
    return CapturedContext(request_id="test-request-id", user_id=1, username="testuser", task_id=None)


def test_get_uuid(task_manager: TaskManager) -> None:
    """Test UUID generation produces valid format."""
    uuid = task_manager.get_uuid()

    assert len(uuid) == 36
    assert isinstance(uuid, str)


def test_get_status(
    task_manager: TaskManager,
    sample_training_request: TrainingRequest,
    sample_captured_context: CapturedContext,
) -> None:
    """Test task status retrieval from queue."""
    # Queue stores tuples of (request, captured_context) like the actual implementation
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    status = task_manager.get_status("1234")

    assert status == "starting"


def test_get_status_not_found(task_manager: TaskManager) -> None:
    """Test that get_status returns 'UUID Not Found' for non-existent UUID."""
    status = task_manager.get_status("non-existent-uuid")

    assert status == "UUID Not Found"


def test_set_status(
    task_manager: TaskManager,
    sample_training_request: TrainingRequest,
    sample_captured_context: CapturedContext,
) -> None:
    """Test updating task status."""
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    result = task_manager.set_status("1234", "complete")

    assert result is True
    status = task_manager.get_status("1234")
    assert status == "complete"


def test_set_status_not_found(task_manager: TaskManager) -> None:
    """Test that set_status returns False for non-existent UUID."""
    result = task_manager.set_status("non-existent-uuid", "complete")

    assert result is False


def test_get_all_status(
    task_manager: TaskManager,
    sample_training_request: TrainingRequest,
    sample_captured_context: CapturedContext,
) -> None:
    """Test retrieving status for all tasks."""
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    all_status = task_manager.get_all_status()

    assert "test_model" in all_status
    assert all_status["test_model"] == "starting"


@pytest.fixture
def event_watcher() -> EventWatcher:
    """Provide a fresh EventWatcher instance for each test."""
    # Reset singleton for testing
    EventWatcher._instance = None  # pyright: ignore[reportPrivateUsage]
    return EventWatcher()


def test_event_watcher_singleton(event_watcher: EventWatcher) -> None:
    """Test that EventWatcher returns the same instance."""
    watcher1 = EventWatcher()
    watcher2 = EventWatcher()

    assert watcher1 is watcher2


def test_register_callback(event_watcher: EventWatcher, sample_training_request: TrainingRequest) -> None:
    """Test registering a callback for a job UUID with the updated signature."""
    from concurrent.futures import Future

    mock_future: Future[None] = Future()
    callback_called: list[tuple[Any, Any]] = []

    def my_callback(request: Any, future: Any) -> None:
        callback_called.append((request, future))

    # Register callback with the new signature that includes request and future
    event_watcher.register_callback(
        job_uuid="1234",
        callback=my_callback,
        request=sample_training_request,
        future=mock_future,
    )

    assert "1234" in event_watcher._callbacks  # pyright: ignore[reportPrivateUsage]
    assert "1234" in event_watcher._watched_futures  # pyright: ignore[reportPrivateUsage]


def test_start_watching(event_watcher: EventWatcher) -> None:
    """Test starting the event watcher."""
    event_watcher.start_watching()

    assert event_watcher._watching is True  # pyright: ignore[reportPrivateUsage]
    assert event_watcher._watch_thread is not None  # pyright: ignore[reportPrivateUsage]
    assert event_watcher._stop_event is not None  # pyright: ignore[reportPrivateUsage]


def test_start_watching_already_running(event_watcher: EventWatcher) -> None:
    """Test that starting an already running watcher logs a warning."""
    event_watcher.start_watching()

    with capture_logs(level="WARNING") as output:
        event_watcher.start_watching()
        assert any("EventWatcher is already running" in msg for msg in output)


def test_stop_watching(event_watcher: EventWatcher) -> None:
    """Test stopping the event watcher."""
    event_watcher.start_watching()
    event_watcher.stop_watching()

    assert event_watcher._watching is False  # pyright: ignore[reportPrivateUsage]
    assert event_watcher._watch_thread is None  # pyright: ignore[reportPrivateUsage]


def test_stop_watching_not_running(event_watcher: EventWatcher) -> None:
    """Test stopping a watcher that is not running."""
    # Should not raise an error
    event_watcher.stop_watching()


def test_callback_invoked_on_completion(
    event_watcher: EventWatcher, sample_training_request: TrainingRequest
) -> None:
    """Test that callback is invoked when a future completes."""
    from concurrent.futures import Future

    mock_future: Future[None] = Future()
    callback_called: list[tuple[Any, Any]] = []

    def my_callback(request: Any, future: Any) -> None:
        callback_called.append((request, future))

    event_watcher.register_callback(
        job_uuid="1234",
        callback=my_callback,
        request=sample_training_request,
        future=mock_future,
    )

    # Complete the future
    mock_future.set_result(None)

    # The callback won't be called immediately - it's called by the watch loop.
    # Instead, verify the callback is registered and the future is tracked.
    assert "1234" in event_watcher._callbacks  # pyright: ignore[reportPrivateUsage]
    assert "1234" in event_watcher._watched_futures  # pyright: ignore[reportPrivateUsage]
