"""Tests for models API v1 endpoints."""

from typing import Any

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.api.v1.endpoints.models import router as models_router
from tests.conftest import set_dependency_override, clear_dependency_overrides


class TestModelsRouter:
    """Tests for models router endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with models router."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        app = FastAPI()
        # Mount static files for templates to work
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except Exception:
            pass
        app.include_router(models_router, prefix="/models")
        return TestClient(app)

    @staticmethod
    def mock_current_user() -> Mock:
        """Mock function that returns a mock user for authentication."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "test_user"
        mock_user.is_active = True
        return mock_user

    @patch("app.api.v1.endpoints.models.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.models.PredictionPersistanceUtil")
    def test_delete_model_success(self, mock_pred_persistance: Any, mock_ml_persistance: Any, client: TestClient) -> None:
        """Test deleting a model successfully."""
        from app.auth.dependencies import get_current_active_user
        mock_ml_persistance.delete_model = AsyncMock()
        mock_pred_persistance.delete_model_predictions = AsyncMock()
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete("/models/deleteModel", params={"model_name": "test_model"})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Model deleted successfully" in data["message"]
            mock_ml_persistance.delete_model.assert_awaited_once_with("test_model")
            mock_pred_persistance.delete_model_predictions.assert_awaited_once_with("test_model")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.models.PredictionPersistanceUtil")
    def test_delete_model_error(self, mock_pred_persistance: Any, mock_ml_persistance: Any, client: TestClient) -> None:
        """Test deleting a model that raises an error."""
        from app.auth.dependencies import get_current_active_user
        mock_ml_persistance.delete_model = AsyncMock(side_effect=Exception("Database error"))
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete("/models/deleteModel", params={"model_name": "test_model"})

            assert response.status_code == 500
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "DELETE_MODEL_ERROR" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_function_success_json(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting a function successfully with JSON response."""
        from app.auth.dependencies import get_current_active_user
        # The endpoint expects an object with attributes: id, function_name, entrypoint, tokens
        mock_func = Mock()
        mock_func.id = 1
        mock_func.function_name = "test_func"
        mock_func.entrypoint = "0x1000"
        mock_func.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_func)
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": "test_func"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            mock_func_persistance.get_function.assert_awaited_once_with("test_model", "test_func")
        finally:
            clear_dependency_overrides(client)

    def test_get_function_empty_function_name(self, client: TestClient) -> None:
        """Test getting a function with empty function_name returns 400."""
        from app.auth.dependencies import get_current_active_user
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": ""},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_FUNCTION_NAME" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    def test_get_function_empty_model_name(self, client: TestClient) -> None:
        """Test getting a function with empty model_name returns 400."""
        from app.auth.dependencies import get_current_active_user
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunction",
                params={"model_name": "", "function_name": "test_func"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_MODEL_NAME" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_function_not_found(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting a function that doesn't exist returns 404."""
        from app.auth.dependencies import get_current_active_user
        mock_func_persistance.get_function = AsyncMock(return_value=None)
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": "nonexistent"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 404
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "FUNCTION_NOT_FOUND" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_functions_success_json(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting all functions successfully with JSON response."""
        from app.auth.dependencies import get_current_active_user
        # The endpoint expects objects with attributes: id, function_name, entrypoint, tokens
        mock_func1 = Mock()
        mock_func1.id = 1
        mock_func1.function_name = "func1"
        mock_func1.entrypoint = "0x1000"
        mock_func1.tokens = "tokens1"
        mock_func2 = Mock()
        mock_func2.id = 2
        mock_func2.function_name = "func2"
        mock_func2.entrypoint = "0x2000"
        mock_func2.tokens = "tokens2"
        mock_func_persistance.get_functions = AsyncMock(return_value=[mock_func1, mock_func2])
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["functions"]) == 2
            mock_func_persistance.get_functions.assert_awaited_once_with("test_model")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_functions_empty(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting functions when none exist."""
        from app.auth.dependencies import get_current_active_user
        mock_func_persistance.get_functions = AsyncMock(return_value=[])
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["functions"] == []
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_prediction_details_success_json(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting prediction details successfully with JSON response."""
        from app.auth.dependencies import get_current_active_user
        # model_info needs .tokens attribute
        mock_model_info = Mock()
        mock_model_info.tokens = "model tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        # prediction_data uses .get("tokens")
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getPredictionDetails",
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
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_prediction_details_function_not_found(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting prediction details when function not found returns 404."""
        from app.auth.dependencies import get_current_active_user
        mock_func_persistance.get_function = AsyncMock(return_value=None)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getPredictionDetails",
                params={
                    "model_name": "test_model",
                    "function_name": "nonexistent",
                    "task_name": "test_task",
                },
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 404
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "FUNCTION_NOT_FOUND" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_prediction_details_prediction_not_found(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting prediction details when prediction not found returns 404."""
        from app.auth.dependencies import get_current_active_user
        mock_func_persistance.get_function = AsyncMock(return_value={
            "model_name": "test_model",
            "function_name": "test_func",
            "entrypoint": "0x1000",
            "tokens": "model tokens",
        })
        mock_func_persistance.get_prediction_function = AsyncMock(return_value=None)
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getPredictionDetails",
                params={
                    "model_name": "test_model",
                    "function_name": "test_func",
                    "task_name": "test_task",
                },
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 404
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "PREDICTION_NOT_FOUND" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_prediction_details_retrieval_error(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting prediction details when retrieval fails returns 400."""
        from app.auth.dependencies import get_current_active_user
        mock_func_persistance.get_function = AsyncMock(side_effect=TypeError("Invalid data type"))
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getPredictionDetails",
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
            assert "RETRIEVAL_ERROR" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_function_html_response(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting a function returns HTML for browsers."""
        from app.auth.dependencies import get_current_active_user
        mock_func = Mock()
        mock_func.id = 1
        mock_func.function_name = "test_func"
        mock_func.entrypoint = "0x1000"
        mock_func.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_func)
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": "test_func"},
                headers={"Accept": "text/html"},
            )

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_functions_html_response(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting functions returns HTML for browsers."""
        from app.auth.dependencies import get_current_active_user
        mock_func1 = Mock()
        mock_func1.id = 1
        mock_func1.function_name = "func1"
        mock_func1.entrypoint = "0x1000"
        mock_func1.tokens = "tokens1"
        mock_func_persistance.get_functions = AsyncMock(return_value=[mock_func1])
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
                headers={"Accept": "text/html"},
            )

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.FunctionPersistanceUtil")
    def test_get_prediction_details_html_response(self, mock_func_persistance: Any, client: TestClient) -> None:
        """Test getting prediction details returns HTML for browsers."""
        from app.auth.dependencies import get_current_active_user
        mock_model_info = Mock()
        mock_model_info.tokens = "model tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.get(
                "/models/getPredictionDetails",
                params={
                    "model_name": "test_model",
                    "function_name": "test_func",
                    "task_name": "test_task",
                },
                headers={"Accept": "text/html"},
            )

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.models.PredictionPersistanceUtil")
    def test_delete_models_success(self, mock_pred_persistance: Any, mock_ml_persistance: Any, client: TestClient) -> None:
        """Test deleting multiple models successfully."""
        from app.auth.dependencies import get_current_active_user
        mock_ml_persistance.delete_model = AsyncMock()
        mock_pred_persistance.delete_model_predictions = AsyncMock()
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete(
                "/models/deleteModels",
                params={"model_names": "model1,model2,model3"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["deleted"] == ["model1", "model2", "model3"]
            assert data["data"]["failed"] == []
            assert mock_ml_persistance.delete_model.call_count == 3
        finally:
            clear_dependency_overrides(client)

    @patch("app.api.v1.endpoints.models.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.models.PredictionPersistanceUtil")
    def test_delete_models_partial_failure(self, mock_pred_persistance: Any, mock_ml_persistance: Any, client: TestClient) -> None:
        """Test deleting multiple models with some failures."""
        from app.auth.dependencies import get_current_active_user
        # First call succeeds, second raises, third succeeds
        mock_ml_persistance.delete_model = AsyncMock(side_effect=[None, Exception("DB error"), None])
        mock_pred_persistance.delete_model_predictions = AsyncMock()
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete(
                "/models/deleteModels",
                params={"model_names": "model1,model2,model3"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "model1" in data["data"]["deleted"]
            assert "model3" in data["data"]["deleted"]
            assert "model2" in data["data"]["failed"]
        finally:
            clear_dependency_overrides(client)

    def test_delete_models_empty_names(self, client: TestClient) -> None:
        """Test deleting models with empty name list returns 400."""
        from app.auth.dependencies import get_current_active_user
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete(
                "/models/deleteModels",
                params={"model_names": ""},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_MODEL_NAMES" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)

    def test_delete_models_whitespace_only_names(self, client: TestClient) -> None:
        """Test deleting models with whitespace-only names returns 400."""
        from app.auth.dependencies import get_current_active_user
        set_dependency_override(client, get_current_active_user, self.mock_current_user)

        try:
            response = client.delete(
                "/models/deleteModels",
                params={"model_names": "  ,  ,  "},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_MODEL_NAMES" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(client)
