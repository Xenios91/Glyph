"""Tests for web endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.web.endpoints.web import router, templates


class TestWebEndpoints:
    """Tests for web endpoint routes."""

    @pytest.fixture
    def client(self):
        """Create test client with web router."""
        from fastapi import FastAPI
        app = FastAPI()
        
        # Mount static files for templates to work
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except Exception:
            pass
        
        app.include_router(router)
        return TestClient(app)

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_home_json_response(self, mock_ml_persistance, client):
        """Test home endpoint returns JSON for API clients."""
        mock_ml_persistance.get_models_list.return_value = set()

        response = client.get("/", headers={"Accept": "application/json"})

        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_home_html_response(self, mock_ml_persistance, client):
        """Test home endpoint returns HTML for browsers."""
        mock_ml_persistance.get_models_list.return_value = set()

        response = client.get(
            "/",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch("app.web.endpoints.web.get_settings")
    def test_config_endpoint(self, mock_get_settings, client):
        """Test config endpoint."""
        mock_settings = Mock()
        mock_settings.cpu_cores = 4
        mock_settings.max_file_size_mb = 100
        mock_get_settings.return_value = mock_settings

        response = client.get(
            "/config",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    def test_error_endpoint_default(self, client):
        """Test error endpoint with default message."""
        response = client.get(
            "/error",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "unknown error" in response.text.lower()

    def test_error_endpoint_upload_error(self, client):
        """Test error endpoint with upload error type."""
        response = client.get(
            "/error?type=uploadError",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "ELF" in response.text

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_upload_binary_json_response(self, mock_ml_persistance, client):
        """Test upload binary endpoint returns JSON for API clients."""
        mock_ml_persistance.get_models_list.return_value = set()

        response = client.get(
            "/uploadBinary",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_upload_binary_html_no_models(self, mock_ml_persistance, client):
        """Test upload binary endpoint with no models."""
        mock_ml_persistance.get_models_list.return_value = set()

        response = client.get(
            "/uploadBinary",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_upload_binary_html_with_models(self, mock_ml_persistance, client):
        """Test upload binary endpoint with models available."""
        mock_ml_persistance.get_models_list.return_value = {"model1", "model2"}

        response = client.get(
            "/uploadBinary",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    @patch("app.web.endpoints.web.TaskManager")
    def test_get_models_json_response(self, mock_task_manager, mock_ml_persistance, client):
        """Test get models endpoint returns JSON for API clients."""
        mock_ml_persistance.get_models_list.return_value = {"model1", "model2"}
        mock_task_manager.get_all_status.return_value = {}

        response = client.get(
            "/getModels",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert set(data["models"]) == {"model1", "model2"}

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    @patch("app.web.endpoints.web.TaskManager")
    def test_get_models_html_response(self, mock_task_manager, mock_ml_persistance, client):
        """Test get models endpoint returns HTML for browsers."""
        mock_ml_persistance.get_models_list.return_value = {"model1", "model2"}
        mock_task_manager.get_all_status.return_value = {}

        response = client.get(
            "/getModels",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_predictions_json_response(self, mock_pred_persistance, client):
        """Test get predictions endpoint returns JSON for API clients."""
        mock_pred_persistance.get_predictions_list.return_value = []

        response = client.get(
            "/getPredictions",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_predictions_html_response(self, mock_pred_persistance, client):
        """Test get predictions endpoint returns HTML for browsers."""
        mock_pred_persistance.get_predictions_list.return_value = []

        response = client.get(
            "/getPredictions",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_json_success(self, mock_func_persistance, client):
        """Test get prediction details returns JSON on success."""
        mock_func_persistance.get_function.return_value = {
            "model_name": "test_model",
            "function_name": "test_func",
            "entrypoint": "0x1000",
            "tokens": "test tokens",
        }
        mock_func_persistance.get_prediction_function.return_value = {
            "tokens": "prediction tokens",
        }

        response = client.get(
            "/getPredictionDetails",
            params={
                "modelName": "test_model",
                "functionName": "test_func",
                "taskName": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_name" in data
        assert "model_name" in data

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_function_not_found(self, mock_func_persistance, client):
        """Test get prediction details returns 404 when function not found."""
        mock_func_persistance.get_function.return_value = None

        response = client.get(
            "/getPredictionDetails",
            params={
                "modelName": "test_model",
                "functionName": "test_func",
                "taskName": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_prediction_not_found(self, mock_func_persistance, client):
        """Test get prediction details returns 404 when prediction not found."""
        mock_func_persistance.get_function.return_value = {
            "model_name": "test_model",
            "function_name": "test_func",
            "entrypoint": "0x1000",
            "tokens": "test tokens",
        }
        mock_func_persistance.get_prediction_function.return_value = None

        response = client.get(
            "/getPredictionDetails",
            params={
                "modelName": "test_model",
                "functionName": "test_func",
                "taskName": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_prediction_json_response(self, mock_pred_persistance, client):
        """Test get prediction returns JSON for API clients."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = []
        mock_pred_persistance.get_predictions.return_value = mock_prediction

        response = client.get(
            "/getPrediction",
            params={"taskName": "test_task", "modelName": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_name" in data
        assert "model_name" in data

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_prediction_html_response(self, mock_pred_persistance, client):
        """Test get prediction returns HTML for browsers."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = []
        mock_pred_persistance.get_predictions.return_value = mock_prediction

        response = client.get(
            "/getPrediction",
            params={"taskName": "test_task", "modelName": "test_model"},
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
