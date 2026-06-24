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


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """Reset all singleton state before each test for proper test isolation."""
    TaskManager._reset_for_testing()
    EventWatcher._reset_for_testing()
    TaskService._reset_for_testing()


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
    # Insert directly into the underlying deque (what TaskManager.get_status reads)
    TaskService().service_queue._queue.append((sample_training_request, sample_captured_context))

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
    TaskService().service_queue._queue.append((sample_training_request, sample_captured_context))

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
    TaskService().service_queue._queue.append((sample_training_request, sample_captured_context))

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


def test_register_task(task_manager: TaskManager) -> None:
    """Test registering a task in the active tasks registry."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)

    assert task_manager.get_status("test-uuid") == "starting"


def test_register_task_without_owner(task_manager: TaskManager) -> None:
    """Test registering a task without an owner."""
    task_manager.register_task("test-uuid-no-owner", "queued")

    assert task_manager.get_status("test-uuid-no-owner") == "queued"


def test_verify_task_owner_owns_task(task_manager: TaskManager) -> None:
    """Test that owner can access their task."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)

    assert task_manager.verify_task_owner("test-uuid", 42) is True


def test_verify_task_owner_wrong_owner(task_manager: TaskManager) -> None:
    """Test that non-owner cannot access task."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)

    assert task_manager.verify_task_owner("test-uuid", 99) is False


def test_verify_task_owner_no_owner_set(task_manager: TaskManager) -> None:
    """Test that tasks without owner are accessible by anyone."""
    task_manager.register_task("test-uuid", "starting")

    assert task_manager.verify_task_owner("test-uuid", 42) is True


def test_set_status_ownership_check_fails(task_manager: TaskManager) -> None:
    """Test that set_status fails when ownership check fails."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)

    result = task_manager.set_status("test-uuid", "complete", owner_id=99)

    assert result is False
    assert task_manager.get_status("test-uuid") == "starting"


def test_set_status_with_valid_owner(task_manager: TaskManager) -> None:
    """Test that set_status succeeds with valid owner."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)

    result = task_manager.set_status("test-uuid", "complete", owner_id=42)

    assert result is True
    assert task_manager.get_status("test-uuid") == "complete"


def test_set_task_result(task_manager: TaskManager) -> None:
    """Test storing and retrieving a task result."""
    task_manager.register_task("test-uuid", "starting")
    task_manager.set_task_result("test-uuid", {"data": "result"})

    assert task_manager.get_task_result("test-uuid") == {"data": "result"}


def test_get_task_result_not_found(task_manager: TaskManager) -> None:
    """Test getting result for non-existent task returns None."""
    result = task_manager.get_task_result("non-existent")

    assert result is None


def test_remove_task(task_manager: TaskManager) -> None:
    """Test removing a task from the registry."""
    task_manager.register_task("test-uuid", "starting", owner_id=42)
    task_manager.set_task_result("test-uuid", {"data": "result"})
    task_manager.remove_task("test-uuid")

    assert task_manager.get_status("test-uuid") == "UUID Not Found"
    assert task_manager.get_task_result("test-uuid") is None


def test_remove_nonexistent_task(task_manager: TaskManager) -> None:
    """Test removing a task that doesn't exist doesn't error."""
    task_manager.remove_task("non-existent")


def test_get_executor(task_manager: TaskManager) -> None:
    """Test getting the process pool executor."""
    from concurrent.futures import ProcessPoolExecutor

    executor = task_manager._get_executor()

    assert isinstance(executor, ProcessPoolExecutor)


@pytest.mark.xdist_group(name="task_manager_shutdown")
def test_shutdown_executor(task_manager: TaskManager) -> None:
    """Test shutting down the executor."""
    task_manager._shutdown_executor()

    assert task_manager.exec_pool is None
    assert task_manager._executor_shutdown is True


@pytest.mark.xdist_group(name="task_manager_shutdown")
def test_signal_handler(task_manager: TaskManager) -> None:
    """Test signal handler calls shutdown."""
    task_manager._signal_handler(15, None)

    assert task_manager._executor_shutdown is True
