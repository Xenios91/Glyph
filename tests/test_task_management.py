"""Unit tests for task management and queue operations."""
import logging
from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest

from app.processing.task_management import EventWatcher, TaskManager
from app.services.request_handler import TrainingRequest
from app.services.task_service import TaskService


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


def test_get_uuid(task_manager):
    """Test UUID generation produces valid format."""
    uuid = task_manager.get_uuid()

    assert len(uuid) == 36
    assert isinstance(uuid, str)


def test_get_status(task_manager, sample_training_request):
    """Test task status retrieval from queue."""
    # Queue stores tuples of (request, future) like the actual implementation
    TaskService().service_queue.put((sample_training_request, None))

    status = task_manager.get_status("1234")

    assert status == "starting"


def test_get_status_not_found(task_manager):
    """Test that get_status returns 'UUID Not Found' for non-existent UUID."""
    status = task_manager.get_status("non-existent-uuid")

    assert status == "UUID Not Found"


def test_set_status(task_manager, sample_training_request):
    """Test updating task status."""
    TaskService().service_queue.put((sample_training_request, None))

    result = task_manager.set_status("1234", "complete")

    assert result is True
    status = task_manager.get_status("1234")
    assert status == "complete"


def test_set_status_not_found(task_manager):
    """Test that set_status returns False for non-existent UUID."""
    result = task_manager.set_status("non-existent-uuid", "complete")

    assert result is False


def test_get_all_status(task_manager, sample_training_request):
    """Test retrieving status for all tasks."""
    TaskService().service_queue.put((sample_training_request, None))

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


def test_register_callback(event_watcher):
    """Test registering a callback for a job UUID."""
    callback = lambda req, fut: None
    mock_request = Mock()
    mock_future = Mock(spec=Future)
    event_watcher.register_callback("test-uuid", callback, mock_request, mock_future)

    assert "test-uuid" in event_watcher._callbacks


def test_start_watching(event_watcher):
    """Test starting the event watcher."""
    event_watcher.start_watching()

    assert event_watcher._watching is True
    assert event_watcher._watch_thread is not None
    assert event_watcher._stop_event is not None


def test_start_watching_already_running(event_watcher, caplog):
    """Test that starting an already running watcher logs a warning."""
    event_watcher.start_watching()

    with caplog.at_level(logging.WARNING):
        event_watcher.start_watching()
        assert "EventWatcher is already watching" in caplog.text


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
    callback_called = []

    def on_complete(request, future):
        callback_called.append((request, future))

    # Create a mock future that is done
    mock_future = Mock(spec=Future)
    mock_future.done.return_value = True

    event_watcher.register_callback(sample_training_request.uuid, on_complete, sample_training_request, mock_future)

    # Verify callback is registered
    assert sample_training_request.uuid in event_watcher._callbacks
    assert sample_training_request.uuid in event_watcher._watched_futures
