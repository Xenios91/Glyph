"""Tests for predictions API v1 endpoints."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.auth.dependencies import get_current_active_user
from tests.conftest import set_dependency_override
from tests.factories import make_mock_user

MODEL_REPO_PATH = "app.api.v1.endpoints.predictions.ModelRepository"


def _mock_owned_model(user_id: int = 1) -> Any:
    """Return a mock model row owned by the given user (for ModelRepository.get)."""
    model_row = Mock()
    model_row.user_id = user_id
    return model_row


class TestPredictionsRouter:
    """Tests for predictions router endpoints."""

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions._run_prediction_task")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_success(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_run_prediction_task: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test creating a prediction task successfully."""
        mock_model_repo.get = AsyncMock(return_value=_mock_owned_model(1))
        mock_pred_repo.check_task_name_unique = AsyncMock(return_value=False)
        mock_task_manager_instance = Mock()
        mock_task_manager_instance.get_uuid.return_value = "test-uuid-123"
        mock_task_manager.return_value = mock_task_manager_instance
        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "test-uuid-123"
        mock_prediction_request.return_value = mock_pred_req_instance
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "uuid" in data["data"]
        assert "Prediction task created successfully" in data["message"]

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_task_name_exists(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction with existing task name returns 409."""
        mock_model_repo.get = AsyncMock(return_value=_mock_owned_model(1))
        mock_pred_repo.check_task_name_unique = AsyncMock(return_value=True)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "existing_task",
            },
        )

        assert response.status_code == 409
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "TASK_NAME_EXISTS" in detail.get("error", {}).get("code", "")

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions._run_prediction_task")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_with_custom_uuid(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_run_prediction_task: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test creating a prediction task with custom UUID."""
        mock_model_repo.get = AsyncMock(return_value=_mock_owned_model(1))
        mock_pred_repo.check_task_name_unique = AsyncMock(return_value=False)
        mock_task_manager_instance = Mock()
        mock_task_manager_instance.get_uuid.return_value = "custom-uuid-456"
        mock_task_manager.return_value = mock_task_manager_instance
        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "custom-uuid-456"
        mock_prediction_request.return_value = mock_pred_req_instance
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
                "uuid": "custom-uuid-456",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["uuid"] == "custom-uuid-456"

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_error(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction task creation error."""
        mock_model_repo.get = AsyncMock(return_value=_mock_owned_model(1))
        mock_pred_repo.check_task_name_unique = AsyncMock(side_effect=Exception("Test error"))
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
            },
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "PREDICTION_ERROR" in detail.get("error", {}).get("code", "")

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_model_not_found(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test predicting with a nonexistent model returns 404 MODEL_NOT_FOUND."""
        mock_model_repo.get = AsyncMock(return_value=None)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "missing_model",
                "taskName": "test_task",
            },
        )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "MODEL_NOT_FOUND" in detail.get("error", {}).get("code", "")
        # The uniqueness check must never run when the model is missing.
        mock_pred_repo.check_task_name_unique.assert_not_called()

    @patch(MODEL_REPO_PATH)
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_other_users_model(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        mock_model_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test predicting with another user's model returns 404 (existence not leaked)."""
        mock_model_repo.get = AsyncMock(return_value=_mock_owned_model(99))
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "other_model",
                "taskName": "test_task",
            },
        )

        assert response.status_code == 404
        mock_pred_repo.check_task_name_unique.assert_not_called()

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_get_prediction_success_json(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test getting a prediction successfully with JSON response."""

        class SimplePrediction:
            def __init__(self) -> None:
                self.task_name = "test_task"
                self.model_name = "test_model"
                self.predictions = [{"functionName": "test_func", "predictedLabel": "test_label"}]

        mock_prediction = SimplePrediction()
        mock_pred_repo.get_prediction = AsyncMock(return_value=mock_prediction)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPrediction",
            params={"task_name": "test_task", "model_name": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["prediction"]["task_name"] == "test_task"
        assert data["data"]["prediction"]["model_name"] == "test_model"

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_get_prediction_not_found(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test getting a prediction that doesn't exist."""
        mock_pred_repo.get_prediction = AsyncMock(return_value=None)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPrediction",
            params={"task_name": "nonexistent_task", "model_name": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "PREDICTION_NOT_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_prediction_success(
        self,
        mock_pred_service: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test deleting a prediction the caller owns succeeds and is scoped."""
        mock_pred_service.delete_prediction = AsyncMock()
        # The scoped lookup returns the caller's id only when they own the task.
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePrediction",
            params={"task_name": "test_task"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Prediction deleted successfully" in data["message"]
        # The delete is scoped to the caller (regression: unscoped delete).
        mock_pred_service.delete_prediction.assert_awaited_once_with("test_task", user_id=1)

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_prediction_not_owned_returns_404(
        self,
        mock_pred_service: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Deleting a task the caller does not own 404s (no unscoped delete)."""
        mock_pred_service.delete_prediction = AsyncMock()
        # Scoped lookup returns None: the caller has no prediction with this name.
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=None)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePrediction",
            params={"task_name": "someone_else_task"},
        )

        assert response.status_code == 404
        # The delete must NOT run for a task the caller does not own.
        mock_pred_service.delete_prediction.assert_not_awaited()

    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_success_json(
        self,
        mock_func_repo: Any,
        mock_pred_repo: Any,
        mock_service_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test getting prediction details successfully with JSON response."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_model_info.user_id = None
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_service_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            },
        )
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_name" in data["data"]
        assert data["data"]["task_name"] == "test_task"

    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_retrieval_error(self, mock_func_repo: Any, predictions_client: Any) -> None:
        """Test getting prediction details with retrieval error."""
        mock_func_repo.get = AsyncMock(side_effect=IndexError("Test error"))
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "RETRIEVAL_ERROR" in detail.get("error", {}).get("code", "")

    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_json_response(
        self,
        mock_func_repo: Any,
        mock_pred_repo: Any,
        mock_service_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test getting prediction details returns JSON (no HTML content negotiation)."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_model_info.user_id = None
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_service_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            },
        )
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        data = response.json()
        assert data["data"]["task_name"] == "test_task"

    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_json_data(
        self,
        mock_func_repo: Any,
        mock_pred_repo: Any,
        mock_service_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test getting prediction details returns correct JSON data."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_model_info.user_id = None
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_service_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            },
        )
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        data = response.json()
        assert data["data"]["model_name"] == "test_model"

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_empty_task_name(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction with empty taskName raises 400."""
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "",
            },
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "TASK_NAME_REQUIRED" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_whitespace_task_name(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction with whitespace-only taskName raises 400."""
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "   ",
            },
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "TASK_NAME_REQUIRED" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_get_prediction_json_response(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test getting a prediction returns JSON (no HTML content negotiation)."""

        class SimplePrediction:
            def __init__(self) -> None:
                self.task_name = "test_task"
                self.model_name = "test_model"
                self.predictions = [{"functionName": "test_func", "predictedLabel": "test_label"}]

        mock_prediction = SimplePrediction()
        mock_pred_repo.get_prediction = AsyncMock(return_value=mock_prediction)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPrediction",
            params={"task_name": "test_task", "model_name": "test_model"},
        )

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        data = response.json()
        assert data["data"]["prediction"]["task_name"] == "test_task"

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_predictions_success(
        self,
        mock_pred_service: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test batch deleting predictions successfully."""
        mock_pred_service.delete_prediction = AsyncMock()
        # The caller owns each named task, so the scoped lookup returns their id.
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePredictions",
            params={"task_names": "task1,task2,task3"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted"] == ["task1", "task2", "task3"]
        assert data["data"]["failed"] == []
        assert "Deleted 3 prediction(s)" in data["message"]

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_predictions_empty_task_names(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test batch delete with empty task names raises 400."""
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePredictions",
            params={"task_names": "   "},
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "INVALID_TASK_NAMES" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_predictions_partial_failure(
        self,
        mock_pred_service: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test batch delete with some failures."""

        def side_effect(name: str, user_id: int | None = None) -> None:
            if name == "bad_task":
                raise RuntimeError("DB error")

        mock_pred_service.delete_prediction = AsyncMock(side_effect=side_effect)
        # The caller owns each named task; the failure comes from the service, not ownership.
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePredictions",
            params={"task_names": "good_task,bad_task,another_good"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "good_task" in data["data"]["deleted"]
        assert "another_good" in data["data"]["deleted"]
        assert "bad_task" in data["data"]["failed"]
        assert "failed to delete 1" in data["message"]

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_function_not_found(
        self,
        mock_func_repo: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test getting prediction details when function doesn't exist."""
        mock_func_repo.get = AsyncMock(return_value=None)
        mock_pred_repo.get_prediction_function = AsyncMock(return_value=None)
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.predictions.format_code") as mock_format:
            mock_format.return_value = ""
            response = predictions_client.get(
                "/predictions/getPredictionDetails",
                params={
                    "task_name": "test_task",
                    "model_name": "test_model",
                    "function_name": "missing_func",
                },
                headers={"Accept": "application/json"},
            )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "FUNCTION_NOT_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_type_error(
        self,
        mock_func_repo: Any,
        mock_pred_repo: Any,
        mock_service_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test getting prediction details with TypeError."""
        mock_func_repo.get = AsyncMock(return_value=Mock(tokens="tokens", user_id=None))
        # The caller owns the task so the request reaches the (failing) service call.
        mock_pred_repo.get_owner_by_task = AsyncMock(return_value=1)
        mock_service_pred_repo.get_prediction_function = AsyncMock(side_effect=TypeError("bad data"))
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "RETRIEVAL_ERROR" in detail.get("error", {}).get("code", "")

    # Tests for _execute_prediction and _run_prediction_task
    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.processing.pipeline_configs.ML_PREDICTION_ONLY_PIPELINE")
    def test_execute_prediction_success(
        self,
        mock_pipeline: Any,
        mock_pred_repo: Any,
    ) -> None:
        """Test _execute_prediction with successful pipeline execution."""
        from app.api.v1.endpoints.predictions import _execute_prediction  # pyright: ignore[reportPrivateUsage]
        from app.processing.pipeline import PipelineContext

        mock_pred_repo.save = AsyncMock()

        mock_result = PipelineContext(
            uuid="test-uuid",
            binary_path="",
            pipeline_type="ml_prediction",
        )
        mock_result.set("predictions", [{"functionName": "f1", "predictedLabel": "malicious"}])

        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        pred_request = Mock()
        pred_request.uuid = "test-uuid"
        pred_request.model_name = "test_model"
        pred_request.task_name = "test_task"
        pred_request.get_functions.return_value = [{"functionName": "f1", "tokens": ["int", "main"]}]

        import asyncio

        asyncio.run(_execute_prediction(pred_request))

        mock_pred_repo.save.assert_called_once()

    @patch("app.processing.pipeline_configs.ML_PREDICTION_ONLY_PIPELINE")
    def test_execute_prediction_no_predictions(
        self,
        mock_pipeline: Any,
    ) -> None:
        """Test _execute_prediction when pipeline returns no predictions."""
        from app.api.v1.endpoints.predictions import _execute_prediction  # pyright: ignore[reportPrivateUsage]
        from app.processing.pipeline import PipelineContext

        mock_result = PipelineContext(
            uuid="test-uuid",
            binary_path="",
            pipeline_type="ml_prediction",
        )
        mock_result.set("predictions", None)

        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        pred_request = Mock()
        pred_request.uuid = "test-uuid"
        pred_request.model_name = "test_model"
        pred_request.task_name = "test_task"
        pred_request.get_functions.return_value = [{"functionName": "f1", "tokens": ["int"]}]

        import asyncio

        asyncio.run(_execute_prediction(pred_request))

    @patch("app.processing.pipeline_configs.ML_PREDICTION_ONLY_PIPELINE")
    def test_execute_prediction_pipeline_error(
        self,
        mock_pipeline: Any,
    ) -> None:
        """Test _execute_prediction raises RuntimeError when pipeline has error."""
        from app.api.v1.endpoints.predictions import _execute_prediction  # pyright: ignore[reportPrivateUsage]
        from app.processing.pipeline import PipelineContext

        mock_result = PipelineContext(
            uuid="test-uuid",
            binary_path="",
            pipeline_type="ml_prediction",
        )
        mock_result.error = "Pipeline failed"

        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        pred_request = Mock()
        pred_request.uuid = "test-uuid"
        pred_request.model_name = "test_model"
        pred_request.task_name = "test_task"
        pred_request.get_functions.return_value = [{"functionName": "f1", "tokens": ["int"]}]

        import asyncio

        with pytest.raises(RuntimeError, match="Pipeline failed"):
            asyncio.run(_execute_prediction(pred_request))

    @patch("app.services.prediction_service.PredictionRepository")
    @patch("app.processing.pipeline_configs.ML_PREDICTION_ONLY_PIPELINE")
    def test_execute_prediction_with_captured_context(
        self,
        mock_pipeline: Any,
        mock_pred_repo: Any,
    ) -> None:
        """Test _execute_prediction restores captured request context."""
        from app.api.v1.endpoints.predictions import _execute_prediction  # pyright: ignore[reportPrivateUsage]
        from app.processing.pipeline import PipelineContext
        from app.utils.request_context import CapturedContext

        mock_pred_repo.save = AsyncMock()

        mock_result = PipelineContext(
            uuid="test-uuid",
            binary_path="",
            pipeline_type="ml_prediction",
        )
        mock_result.set("predictions", [{"functionName": "f1", "predictedLabel": "malicious"}])

        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        pred_request = Mock()
        pred_request.uuid = "test-uuid"
        pred_request.model_name = "test_model"
        pred_request.task_name = "test_task"
        pred_request.get_functions.return_value = [{"functionName": "f1", "tokens": ["int"]}]

        captured_ctx = CapturedContext(
            request_id="req-123",
            user_id=1,
            username="testuser",
            task_id="task-123",
        )

        import asyncio

        asyncio.run(_execute_prediction(pred_request, captured_ctx))

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_get_predictions_list_pagination(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Page 2 of size 10 requests offset=10/limit=10 and returns the slice + total."""
        mock_pred_repo.get_predictions_list = AsyncMock(
            return_value=([{"task_name": "t11", "model_name": "m"}, {"task_name": "t12", "model_name": "m"}], 25)
        )
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.get(
            "/predictions/getPredictionsList", params={"page": 2, "page_size": 10}
        )

        assert response.status_code == 200
        # The endpoint must push pagination down to the service (no in-memory slice).
        mock_pred_repo.get_predictions_list.assert_awaited_once_with(user_id=1, offset=10, limit=10)
        data = response.json()["data"]
        assert data["total"] == 25
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total_pages"] == 3
        assert [item["task_name"] for item in data["items"]] == ["t11", "t12"]
