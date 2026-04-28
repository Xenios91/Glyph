"""Tests for predictions API v1 endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints.predictions import router as predictions_router, PredictTokensRequest
from app.auth.dependencies import get_current_active_user, get_optional_user


class TestPredictTokensRequest:
    """Tests for PredictTokensRequest model."""

    def test_predict_tokens_request_minimal(self):
        """Test PredictTokensRequest with minimal fields."""
        request = PredictTokensRequest(modelName="test_model")
        assert request.modelName == "test_model"
        assert request.uuid is None

    def test_predict_tokens_request_with_uuid(self):
        """Test PredictTokensRequest with UUID."""
        request = PredictTokensRequest(modelName="test_model", uuid="test-uuid")
        assert request.modelName == "test_model"
        assert request.uuid == "test-uuid"

    def test_predict_tokens_request_extra_fields(self):
        """Test PredictTokensRequest allows extra fields."""
        request = PredictTokensRequest(
            modelName="test_model",
            taskName="test_task",
            extra_field="extra_value",
        )
        assert request.modelName == "test_model"
        # Extra fields are accessible via model_dump() due to extra: "allow"
        dumped = request.model_dump()
        assert dumped.get("taskName") == "test_task"
        assert dumped.get("extra_field") == "extra_value"


class TestPredictionsRouter:
    """Tests for predictions router endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with predictions router."""
        app = FastAPI()
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except Exception:
            pass
        app.include_router(predictions_router, prefix="/predictions")
        return TestClient(app)

    @staticmethod
    def mock_current_user():
        """Mock function that returns a mock user."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.is_superuser = False
        return mock_user

    @patch("app.api.v1.endpoints.predictions._run_prediction_task")
    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_success(
        self,
        mock_prediction_request,
        mock_task_manager,
        mock_pred_persistance,
        mock_run_prediction_task,
        client,
    ):
        """Test creating a prediction task successfully."""
        mock_pred_persistance.is_task_name_unique = AsyncMock(return_value=True)
        mock_task_manager_instance = Mock()
        mock_task_manager_instance.get_uuid.return_value = "test-uuid-123"
        mock_task_manager.return_value = mock_task_manager_instance
        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "test-uuid-123"
        mock_prediction_request.return_value = mock_pred_req_instance
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
                "data": {"tokens": "test tokens"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "uuid" in data["data"]
        assert "Prediction task created successfully" in data["message"]

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_task_name_exists(
        self,
        mock_prediction_request,
        mock_task_manager,
        mock_pred_persistance,
        client,
    ):
        """Test prediction with existing task name returns 409."""
        mock_pred_persistance.is_task_name_unique = AsyncMock(return_value=False)
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "existing_task",
                "data": {"tokens": "test tokens"},
            },
        )

        assert response.status_code == 409
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "TASK_NAME_EXISTS" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions._run_prediction_task")
    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_with_custom_uuid(
        self,
        mock_prediction_request,
        mock_task_manager,
        mock_pred_persistance,
        mock_run_prediction_task,
        client,
    ):
        """Test creating a prediction task with custom UUID."""
        mock_pred_persistance.is_task_name_unique = AsyncMock(return_value=True)
        mock_task_manager_instance = Mock()
        mock_task_manager_instance.get_uuid.return_value = "custom-uuid-456"
        mock_task_manager.return_value = mock_task_manager_instance
        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "custom-uuid-456"
        mock_prediction_request.return_value = mock_pred_req_instance
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
                "uuid": "custom-uuid-456",
                "data": {"tokens": "test tokens"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["uuid"] == "custom-uuid-456"

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.TaskManager")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    def test_predict_tokens_error(
        self,
        mock_prediction_request,
        mock_task_manager,
        mock_pred_persistance,
        client,
    ):
        """Test prediction task creation error."""
        mock_pred_persistance.is_task_name_unique = AsyncMock(side_effect=Exception("Test error"))
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "taskName": "test_task",
                "data": {"tokens": "test tokens"},
            },
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "PREDICTION_ERROR" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_get_prediction_success_json(self, mock_pred_persistance, client):
        """Test getting a prediction successfully with JSON response."""
        class SimplePrediction:
            def __init__(self):
                self.task_name = "test_task"
                self.model_name = "test_model"

        mock_prediction = SimplePrediction()
        mock_pred_persistance.get_predictions = AsyncMock(return_value=mock_prediction)
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
            "/predictions/getPrediction",
            params={"task_name": "test_task", "model_name": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["prediction"]["task_name"] == "test_task"
        assert data["data"]["prediction"]["model_name"] == "test_model"

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_get_prediction_not_found(self, mock_pred_persistance, client):
        """Test getting a prediction that doesn't exist."""
        mock_pred_persistance.get_predictions = AsyncMock(return_value=None)
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
            "/predictions/getPrediction",
            params={"task_name": "nonexistent_task", "model_name": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "PREDICTION_NOT_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_delete_prediction_success(self, mock_pred_persistance, client):
        """Test deleting a prediction successfully."""
        mock_pred_persistance.delete_prediction = AsyncMock()
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.delete(
            "/predictions/deletePrediction",
            params={"task_name": "test_task"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Prediction deleted successfully" in data["message"]

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_success_json(self, mock_func_persistance, client):
        """Test getting prediction details successfully with JSON response."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "test tokens",
            "prediction": "test_prediction",
        })
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
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

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_retrieval_error(self, mock_func_persistance, client):
        """Test getting prediction details with retrieval error."""
        mock_func_persistance.get_function = AsyncMock(side_effect=IndexError("Test error"))
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
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

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_html_response(self, mock_func_persistance, client):
        """Test getting prediction with HTML response."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "test tokens",
            "prediction": "test_prediction",
        })
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_html_response(self, mock_func_persistance, client):
        """Test getting prediction details with HTML response."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "test tokens",
            "prediction": "test_prediction",
        })
        client.app.dependency_overrides[get_current_active_user] = self.mock_current_user

        response = client.get(
            "/predictions/getPredictionDetails",
            params={
                "task_name": "test_task",
                "model_name": "test_model",
                "function_name": "test_func",
            },
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
