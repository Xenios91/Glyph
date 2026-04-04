"""Tests for predictions API v1 endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.api.v1.endpoints.predictions import router as predictions_router, PredictTokensRequest


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
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(predictions_router, prefix="/predictions")
        return TestClient(app)

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.Trainer")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    @patch("app.api.v1.endpoints.predictions.Predictor")
    def test_predict_tokens_success(
        self,
        mock_predictor,
        mock_prediction_request,
        mock_trainer,
        mock_pred_persistance,
        client,
    ):
        """Test creating a prediction task successfully."""
        # Mock task name uniqueness check
        mock_pred_persistance.is_task_name_unique.return_value = True

        # Mock Trainer
        mock_trainer_instance = Mock()
        mock_trainer_instance.get_uuid.return_value = "test-uuid-123"
        mock_trainer.return_value = mock_trainer_instance

        # Mock PredictionRequest
        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "test-uuid-123"
        mock_prediction_request.return_value = mock_pred_req_instance

        # Mock Predictor
        mock_predictor_instance = Mock()
        mock_predictor.return_value = mock_predictor_instance

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
    @patch("app.api.v1.endpoints.predictions.Trainer")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    @patch("app.api.v1.endpoints.predictions.Predictor")
    def test_predict_tokens_task_name_exists(
        self,
        mock_predictor,
        mock_prediction_request,
        mock_trainer,
        mock_pred_persistance,
        client,
    ):
        """Test prediction with existing task name returns 409."""
        # Mock task name uniqueness check to return False
        mock_pred_persistance.is_task_name_unique.return_value = False

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
        assert "TASK_NAME_EXISTS" in detail.get("error_code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.Trainer")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    @patch("app.api.v1.endpoints.predictions.Predictor")
    def test_predict_tokens_with_custom_uuid(
        self,
        mock_predictor,
        mock_prediction_request,
        mock_trainer,
        mock_pred_persistance,
        client,
    ):
        """Test prediction with custom UUID."""
        mock_pred_persistance.is_task_name_unique.return_value = True

        mock_pred_req_instance = Mock()
        mock_pred_req_instance.uuid = "custom-uuid-456"
        mock_prediction_request.return_value = mock_pred_req_instance

        mock_predictor_instance = Mock()
        mock_predictor.return_value = mock_predictor_instance

        response = client.post(
            "/predictions/predict",
            json={
                "modelName": "test_model",
                "uuid": "custom-uuid-456",
                "taskName": "test_task",
                "data": {"tokens": "test tokens"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["uuid"] == "custom-uuid-456"

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    @patch("app.api.v1.endpoints.predictions.Trainer")
    @patch("app.api.v1.endpoints.predictions.PredictionRequest")
    @patch("app.api.v1.endpoints.predictions.Predictor")
    def test_predict_tokens_error(
        self,
        mock_predictor,
        mock_prediction_request,
        mock_trainer,
        mock_pred_persistance,
        client,
    ):
        """Test prediction that raises an error returns 400."""
        mock_pred_persistance.is_task_name_unique.return_value = True

        mock_prediction_request.side_effect = Exception("Invalid request data")

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
        assert "PREDICTION_ERROR" in detail.get("error_code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_get_prediction_success_json(self, mock_pred_persistance, client):
        """Test getting a prediction successfully with JSON response."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = [{"func": "func1", "pred": "label1"}]
        mock_pred_persistance.get_predictions.return_value = mock_prediction

        response = client.get(
            "/predictions/getPrediction",
            params={"model_name": "test_model", "task_name": "test_task"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "prediction" in data["data"]
        mock_pred_persistance.get_predictions.assert_called_once_with("test_task", "test_model")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_get_prediction_not_found(self, mock_pred_persistance, client):
        """Test getting a prediction that doesn't exist returns 404."""
        mock_pred_persistance.get_predictions.return_value = None

        response = client.get(
            "/predictions/getPrediction",
            params={"model_name": "test_model", "task_name": "nonexistent"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "PREDICTION_NOT_FOUND" in detail.get("error_code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_delete_prediction_success(self, mock_pred_persistance, client):
        """Test deleting a prediction successfully."""
        response = client.get("/predictions/deletePrediction", params={"task_name": "test_task"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Prediction deleted successfully" in data["message"]
        mock_pred_persistance.delete_prediction.assert_called_once_with("test_task")

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_success_json(self, mock_func_persistance, client):
        """Test getting prediction details successfully with JSON response."""
        mock_func_persistance.get_function.return_value = [
            "model_name",
            "function_name",
            "0x1000",
            "model tokens",
        ]
        mock_func_persistance.get_prediction_function.return_value = {
            "tokens": "prediction tokens",
        }

        response = client.get(
            "/predictions/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_name" in data["data"]
        assert "model_tokens" in data["data"]
        assert "prediction_tokens" in data["data"]

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_retrieval_error(self, mock_func_persistance, client):
        """Test getting prediction details when retrieval fails returns 400."""
        mock_func_persistance.get_function.side_effect = TypeError("Invalid data type")

        response = client.get(
            "/predictions/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "RETRIEVAL_ERROR" in detail.get("error_code", "")

    @patch("app.api.v1.endpoints.predictions.PredictionPersistanceUtil")
    def test_get_prediction_html_response(self, mock_pred_persistance, client):
        """Test getting a prediction returns HTML for browsers."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = []
        mock_pred_persistance.get_predictions.return_value = mock_prediction

        response = client.get(
            "/predictions/getPrediction",
            params={"model_name": "test_model", "task_name": "test_task"},
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch("app.api.v1.endpoints.predictions.FunctionPersistanceUtil")
    def test_get_prediction_details_html_response(self, mock_func_persistance, client):
        """Test getting prediction details returns HTML for browsers."""
        mock_func_persistance.get_function.return_value = [
            "model_name",
            "function_name",
            "0x1000",
            "model tokens",
        ]
        mock_func_persistance.get_prediction_function.return_value = {
            "tokens": "prediction tokens",
        }

        response = client.get(
            "/predictions/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
