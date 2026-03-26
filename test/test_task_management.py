"""Unit tests for task management and queue operations."""
from app.request_handler import TrainingRequest
from app.services import TaskService
from app.task_management import TaskManager

import pytest


@pytest.fixture
def task_manager():
    """Provide a fresh TaskManager instance for each test."""
    return TaskManager()


@pytest.fixture
def sample_training_request():
    """Provide a standardized TrainingRequest object for testing."""
    return TrainingRequest(
        uuid="1234",
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
