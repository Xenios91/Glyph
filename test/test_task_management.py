import pytest
from app.request_handler import TrainingRequest
from app.services import TaskService
from app.task_management import TaskManager

# --- Fixtures (Setup Logic) ---

@pytest.fixture
def task_manager():
    """Provides a fresh TaskManager instance for each test."""
    return TaskManager()

@pytest.fixture
def sample_training_request():
    """Provides a standardized TrainingRequest object."""
    return TrainingRequest(
        uuid="1234",
        model_name="test_model",
        data={
            "binaryName": "testBin",
            "functionsMap": {"functions": [{"tokenList": ["testToken"]}]},
        },
    )

# --- Tests ---

def test_get_uuid(task_manager):
    uuid = task_manager.get_uuid()

    # Simple, readable assertions
    assert len(uuid) == 36
    assert isinstance(uuid, str)

def test_get_status(task_manager, sample_training_request):
    # Setup the state
    TaskService().service_queue.put(sample_training_request)

    # Execution
    status = task_manager.get_status("1234")

    # Assertion
    assert status == "starting"
