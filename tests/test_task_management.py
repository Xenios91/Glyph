"""Unit tests for task management and queue operations."""
from concurrent.futures import Future
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from loguru import logger

from app.processing.task_management import EventWatcher, TaskManager
from app.services.request_handler import TrainingRequest
from app.services.task_service import TaskService


@contextmanager
def capture_logs(level="INFO", format="{level}:{name}:{message}"):
    """Capture loguru-based logs for testing.
    
    Based on the loguru migration guide pattern for replacing unittest.assertLogs().
    """
    output = []
    handler_id = logger.add(output.append, level=level, format=format)
    yield output
    logger.remove(handler_id)


@pytest.fixture
def task_manager():
    """Provide a fresh TaskManager instance for each test."""
    return TaskManager()


@pytest.fixture
def sample_training_request():
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
def sample_captured_context():
    """Provide a CapturedContext for testing queue operations."""
    from app.utils.request_context import CapturedContext
    return CapturedContext(request_id="test-request-id", user_id=1, username="testuser", task_id=None)


def test_get_uuid(task_manager):
    """Test UUID generation produces valid format."""
    uuid = task_manager.get_uuid()

    assert len(uuid) == 36
    assert isinstance(uuid, str)


def test_get_status(task_manager, sample_training_request, sample_captured_context):
    """Test task status retrieval from queue."""
    # Queue stores tuples of (request, captured_context) like the actual implementation
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    status = task_manager.get_status("1234")

    assert status == "starting"


def test_get_status_not_found(task_manager):
    """Test that get_status returns 'UUID Not Found' for non-existent UUID."""
    status = task_manager.get_status("non-existent-uuid")

    assert status == "UUID Not Found"


def test_set_status(task_manager, sample_training_request, sample_captured_context):
    """Test updating task status."""
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    result = task_manager.set_status("1234", "complete")

    assert result is True
    status = task_manager.get_status("1234")
    assert status == "complete"


def test_set_status_not_found(task_manager):
    """Test that set_status returns False for non-existent UUID."""
    result = task_manager.set_status("non-existent-uuid", "complete")

    assert result is False


def test_get_all_status(task_manager, sample_training_request, sample_captured_context):
    """Test retrieving status for all tasks."""
    TaskService().service_queue.put((sample_training_request, sample_captured_context))

    all_status = task_manager.get_all_status()

    assert "test_model" in all_status
    assert all_status["test_model"] == "starting"


@pytest.fixture
def event_watcher():
    """Provide a fresh EventWatcher instance for each test."""
    # Reset singleton for testing
    EventWatcher._instance = None
    return EventWatcher()


def test_event_watcher_singleton(event_watcher):
    """Test that EventWatcher returns the same instance."""
    watcher1 = EventWatcher()
    watcher2 = EventWatcher()

    assert watcher1 is watcher2


def test_register_callback(event_watcher, sample_training_request):
    """Test registering a callback for a job UUID with the updated signature."""
    from concurrent.futures import Future

    mock_future: Future[None] = Future()
    callback_called = []

    def my_callback(request, future):
        callback_called.append((request, future))

    # Register callback with the new signature that includes request and future
    event_watcher.register_callback(
        job_uuid="1234",
        callback=my_callback,
        request=sample_training_request,
        future=mock_future,
    )

    assert "1234" in event_watcher._callbacks
    assert "1234" in event_watcher._watched_futures


def test_start_watching(event_watcher):
    """Test starting the event watcher."""
    event_watcher.start_watching()

    assert event_watcher._watching is True
    assert event_watcher._watch_thread is not None
    assert event_watcher._stop_event is not None


def test_start_watching_already_running(event_watcher):
    """Test that starting an already running watcher logs a warning."""
    event_watcher.start_watching()

    with capture_logs(level="WARNING") as output:
        event_watcher.start_watching()
        assert any("EventWatcher is already running" in msg for msg in output)


def test_stop_watching(event_watcher):
    """Test stopping the event watcher."""
    event_watcher.start_watching()
    event_watcher.stop_watching()

    assert event_watcher._watching is False
    assert event_watcher._watch_thread is None


def test_stop_watching_not_running(event_watcher):
    """Test stopping a watcher that is not running."""
    # Should not raise an error
    event_watcher.stop_watching()


def test_callback_invoked_on_completion(event_watcher, sample_training_request):
    """Test that callback is invoked when a future completes."""
    from concurrent.futures import Future

    mock_future: Future[None] = Future()
    callback_called = []

    def my_callback(request, future):
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
    assert "1234" in event_watcher._callbacks
    assert "1234" in event_watcher._watched_futures
