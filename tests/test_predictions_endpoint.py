"""Tests for predictions API v1 endpoints."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.auth.dependencies import get_current_active_user
from tests.conftest import set_dependency_override
from tests.factories import make_mock_user


class TestPredictionsRouter:
    """Tests for predictions router endpoints."""

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
        predictions_client: Any,
    ) -> None:
        """Test creating a prediction task successfully."""
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

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_task_name_exists(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction with existing task name returns 409."""
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
        predictions_client: Any,
    ) -> None:
        """Test creating a prediction task with custom UUID."""
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

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_error(
        self,
        mock_prediction_request: Any,
        mock_task_manager: Any,
        mock_pred_repo: Any,
        predictions_client: Any,
    ) -> None:
        """Test prediction task creation error."""
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

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_prediction_success(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test deleting a prediction successfully."""
        mock_pred_repo.delete_prediction = AsyncMock()
        set_dependency_override(predictions_client, get_current_active_user, make_mock_user)

        response = predictions_client.delete(
            "/predictions/deletePrediction",
            params={"task_name": "test_task"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Prediction deleted successfully" in data["message"]

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_success_json(
        self, mock_func_repo: Any, mock_pred_repo: Any, predictions_client: Any
    ) -> None:
        """Test getting prediction details successfully with JSON response."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            }
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

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_json_response(
        self, mock_func_repo: Any, mock_pred_repo: Any, predictions_client: Any
    ) -> None:
        """Test getting prediction details returns JSON (no HTML content negotiation)."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            }
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

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_json_data(
        self, mock_func_repo: Any, mock_pred_repo: Any, predictions_client: Any
    ) -> None:
        """Test getting prediction details returns correct JSON data."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "test tokens",
                "prediction": "test_prediction",
            }
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

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_predictions_success(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test batch deleting predictions successfully."""
        mock_pred_repo.delete_prediction = AsyncMock()
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

    @patch("app.api.v1.endpoints.predictions.PredictionService")
    def test_delete_predictions_partial_failure(self, mock_pred_repo: Any, predictions_client: Any) -> None:
        """Test batch delete with some failures."""

        def side_effect(name: str) -> None:
            if name == "bad_task":
                raise RuntimeError("DB error")

        mock_pred_repo.delete_prediction = AsyncMock(side_effect=side_effect)
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
        self, mock_func_repo: Any, mock_pred_repo: Any, predictions_client: Any
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

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
    @patch("app.api.v1.endpoints.predictions.FunctionRepository")
    def test_get_prediction_details_type_error(
        self, mock_func_repo: Any, mock_pred_repo: Any, predictions_client: Any
    ) -> None:
        """Test getting prediction details with TypeError."""
        mock_func_repo.get = AsyncMock(return_value=Mock(tokens="tokens"))
        mock_pred_repo.get_prediction_function = AsyncMock(side_effect=TypeError("bad data"))
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
    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
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

    @patch("app.api.v1.endpoints.predictions.PredictionRepository")
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
