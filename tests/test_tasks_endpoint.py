"""Endpoint-level tests for tasks API v1.

Covers the execute_task, get_task_results, and start_similarity_computation
endpoints, including authz checks, validation branches, and the success path
that registers a task in the TaskManager registry.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.api.v1.endpoints import tasks as tasks_mod
from app.auth.dependencies import get_current_active_user
from app.processing.task_management import TaskManager

from tests.conftest import create_app_client
from tests.factories import make_mock_user


def _client(user: Any) -> Any:
    """Create a test client with the tasks router and auth override."""
    return create_app_client(
        routers=[(tasks_mod.router, "/api/v1/tasks")],
        dependency_overrides={get_current_active_user: lambda: user},
    )


def _owned_binary(owner_id: int = 1) -> Mock:
    """Create a mock Binary ORM object owned by the given user."""
    binary = Mock()
    binary.id = 1
    binary.name = "test.elf"
    binary.uploaded_by = owner_id
    return binary


@pytest.fixture(autouse=True)
def _reset_task_manager() -> Any:
    """Reset TaskManager state before and after each test."""
    TaskManager._reset_for_testing()
    yield
    TaskManager._reset_for_testing()


# ---------------------------------------------------------------------------
# POST /execute
# ---------------------------------------------------------------------------


class TestExecuteTask:
    """Tests for the POST /execute endpoint."""

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_binary_not_found(self, mock_repo: Any) -> None:
        """Non-existent binary should return 404 BINARY_NOT_FOUND."""
        user = make_mock_user()  # id=1
        mock_repo.get = AsyncMock(return_value=None)
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/execute",
            json={"binary_id": 99, "task_type": "code_reuse", "task_name": "t"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "BINARY_NOT_FOUND"

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_other_user_binary_denied(self, mock_repo: Any) -> None:
        """Binary owned by another user should return 403 ACCESS_DENIED."""
        user = make_mock_user()  # id=1
        mock_repo.get = AsyncMock(return_value=_owned_binary(owner_id=2))
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/execute",
            json={"binary_id": 1, "task_type": "code_reuse", "task_name": "t"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "ACCESS_DENIED"

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_ml_training_missing_model_name(self, mock_repo: Any) -> None:
        """ML training without model_name should return 400 MISSING_MODEL_NAME."""
        user = make_mock_user()
        mock_repo.get = AsyncMock(return_value=_owned_binary())
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/execute",
            json={"binary_id": 1, "task_type": "ml_training", "task_name": "t"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "MISSING_MODEL_NAME"

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_ml_training_missing_class_type(self, mock_repo: Any) -> None:
        """ML training without ml_class_type should return 400 MISSING_ML_CLASS_TYPE."""
        user = make_mock_user()
        mock_repo.get = AsyncMock(return_value=_owned_binary())
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/execute",
            json={
                "binary_id": 1,
                "task_type": "ml_training",
                "task_name": "t",
                "model_name": "m",
            },
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "MISSING_ML_CLASS_TYPE"

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_similarity_rejected(self, mock_repo: Any) -> None:
        """similarity_computation via /execute should return 400 UNSUPPORTED_TASK_TYPE."""
        user = make_mock_user()
        mock_repo.get = AsyncMock(return_value=_owned_binary())
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/execute",
            json={"binary_id": 1, "task_type": "similarity_computation", "task_name": "t"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["error"]["code"] == "UNSUPPORTED_TASK_TYPE"

    @patch("app.database.binary_repository.BinaryRepository")
    def test_execute_code_reuse_queues_task(self, mock_repo: Any) -> None:
        """Valid code_reuse request should return 200 and register the task."""
        user = make_mock_user()  # id=1
        mock_repo.get = AsyncMock(return_value=_owned_binary(owner_id=1))
        client = _client(user)

        with patch.object(tasks_mod, "run_code_reuse_task", new=AsyncMock()) as mock_runner:
            r = client.post(
                "/api/v1/tasks/execute",
                json={"binary_id": 1, "task_type": "code_reuse", "task_name": "t"},
            )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "starting"
        assert data["task_type"] == "code_reuse"
        assert data["binary_id"] == 1
        # The task should be registered in TaskManager with status "starting"
        assert TaskManager.get_status(data["task_uuid"]) == "starting"
        # The correct runner should have been queued as a background task.
        mock_runner.assert_called_once()


# ---------------------------------------------------------------------------
# GET /{task_uuid}/results
# ---------------------------------------------------------------------------


class TestGetTaskResults:
    """Tests for the GET /{task_uuid}/results endpoint."""

    def test_get_task_results_not_found(self) -> None:
        """Unknown task UUID should return 404 TASK_NOT_FOUND."""
        user = make_mock_user()
        client = _client(user)

        r = client.get("/api/v1/tasks/nonexistent-uuid/results")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "TASK_NOT_FOUND"

    def test_get_task_results_other_owner(self) -> None:
        """Task owned by another user should return 403 ACCESS_DENIED."""
        user = make_mock_user()  # id=1
        TaskManager.register_task("owned-by-2", "completed", owner_id=2)
        client = _client(user)

        r = client.get("/api/v1/tasks/owned-by-2/results")
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "ACCESS_DENIED"

    def test_get_task_results_completed_without_result(self) -> None:
        """Completed task with no stored result should return 404 TASK_RESULTS_NOT_AVAILABLE."""
        user = make_mock_user()  # id=1
        TaskManager.register_task("no-result", "completed", owner_id=1)
        client = _client(user)

        r = client.get("/api/v1/tasks/no-result/results")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "TASK_RESULTS_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# POST /similarity-computation
# ---------------------------------------------------------------------------


class TestStartSimilarityComputation:
    """Tests for the POST /similarity-computation endpoint."""

    @patch("app.database.binary_repository.BinaryRepository")
    def test_start_similarity_computation_binary_not_found(self, mock_repo: Any) -> None:
        """Non-existent binary in the list should return 404."""
        user = make_mock_user()
        mock_repo.get = AsyncMock(return_value=None)
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/similarity-computation",
            json={"task_name": "compare", "binary_ids": [1, 2]},
        )
        assert r.status_code == 404

    @patch("app.database.binary_repository.BinaryRepository")
    def test_start_similarity_computation_other_user(self, mock_repo: Any) -> None:
        """Binary owned by another user should return 403 ACCESS_DENIED."""
        user = make_mock_user()  # id=1
        mock_repo.get = AsyncMock(return_value=_owned_binary(owner_id=2))
        client = _client(user)

        r = client.post(
            "/api/v1/tasks/similarity-computation",
            json={"task_name": "compare", "binary_ids": [1, 2]},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["error"]["code"] == "ACCESS_DENIED"
