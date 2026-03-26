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
    TaskService().service_queue.put(sample_training_request)

    status = task_manager.get_status("1234")

    assert status == "starting"