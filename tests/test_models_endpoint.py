"""Tests for models API v1 endpoints."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from tests.conftest import clear_dependency_overrides, set_dependency_override
from tests.factories import make_mock_user


class TestModelsRouter:
    """Tests for models router endpoints."""

    @patch("app.api.v1.endpoints.models.ModelRepository")
    @patch("app.api.v1.endpoints.models.PredictionService")
    def test_delete_model_success(self, mock_pred_service: Any, mock_model_repo: Any, models_client: Any) -> None:
        """Test deleting a model successfully."""
        from app.auth.dependencies import get_current_active_user

        mock_model_repo.delete = AsyncMock()
        mock_pred_service.delete_predictions_for_model = AsyncMock()
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete("/models/deleteModel", params={"model_name": "test_model"})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Model deleted successfully" in data["message"]
            mock_model_repo.delete.assert_awaited_once_with("test_model")
            mock_pred_service.delete_predictions_for_model.assert_awaited_once_with("test_model")
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.ModelRepository")
    @patch("app.api.v1.endpoints.models.PredictionService")
    def test_delete_model_error(self, mock_pred_service: Any, mock_model_repo: Any, models_client: Any) -> None:
        """Test deleting a model that raises an error."""
        from app.auth.dependencies import get_current_active_user

        mock_model_repo.delete = AsyncMock(side_effect=Exception("Database error"))
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete("/models/deleteModel", params={"model_name": "test_model"})

            assert response.status_code == 500
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "DELETE_MODEL_ERROR" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_function_success_json(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting a function successfully with JSON response."""
        from app.auth.dependencies import get_current_active_user

        # The endpoint expects an object with attributes: id, function_name, entrypoint, tokens
        mock_func = Mock()
        mock_func.id = 1
        mock_func.function_name = "test_func"
        mock_func.entrypoint = "0x1000"
        mock_func.tokens = "test tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_func)
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": "test_func"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            mock_func_repo.get.assert_awaited_once_with("test_model", "test_func")
        finally:
            clear_dependency_overrides(models_client)

    def test_get_function_empty_function_name(self, models_client: Any) -> None:
        """Test getting a function with empty function_name returns 422 (validation error).

        FastAPI's pydantic validation rejects empty strings for FunctionName
        (which has min_length=1 via StringConstraints), returning 422 before
        the endpoint handler runs its own validation logic.
        """
        from app.auth.dependencies import get_current_active_user

        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": ""},
                headers={"Accept": "application/json"},
            )

            # FastAPI returns 422 for pydantic validation failures on query parameters
            assert response.status_code == 422
        finally:
            clear_dependency_overrides(models_client)

    def test_get_function_empty_model_name(self, models_client: Any) -> None:
        """Test getting a function with empty model_name returns 422 (validation error).

        FastAPI's pydantic validation rejects empty strings for ModelName
        (which has min_length=1 via StringConstraints), returning 422 before
        the endpoint handler runs its own validation logic.
        """
        from app.auth.dependencies import get_current_active_user

        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunction",
                params={"model_name": "", "function_name": "test_func"},
                headers={"Accept": "application/json"},
            )

            # FastAPI returns 422 for pydantic validation failures on query parameters
            assert response.status_code == 422
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_function_not_found(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting a function that doesn't exist returns 404."""
        from app.auth.dependencies import get_current_active_user

        mock_func_repo.get = AsyncMock(return_value=None)
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
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
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_functions_success_json(self, mock_func_repo: Any, models_client: Any) -> None:
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
        mock_func_repo.get_functions = AsyncMock(return_value=[mock_func1, mock_func2])
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]["functions"]) == 2
            mock_func_repo.get_functions.assert_awaited_once_with("test_model")
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_functions_empty(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting functions when none exist."""
        from app.auth.dependencies import get_current_active_user

        mock_func_repo.get_functions = AsyncMock(return_value=[])
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
                headers={"Accept": "application/json"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["functions"] == []
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.PredictionRepository")
    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_prediction_details_success_json(
        self, mock_func_repo: Any, mock_pred_repo: Any, models_client: Any,
    ) -> None:
        """Test getting prediction details successfully with JSON response."""
        from app.auth.dependencies import get_current_active_user

        # model_info needs .tokens attribute
        mock_model_info = Mock()
        mock_model_info.tokens = "model tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        # prediction_data uses .get("tokens")
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "prediction tokens",
            },
        )
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
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
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.PredictionRepository")
    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_prediction_details_model_function_not_found(
        self, mock_func_repo: Any, mock_pred_repo: Any, models_client: Any,
    ) -> None:
        """Test getting prediction details when model function not found still returns 200.

        The model function lookup is optional - the binary may not have been used
        during model training, so the function may not exist in the functions DB.
        Prediction details should still be displayed.
        """
        from app.auth.dependencies import get_current_active_user

        mock_func_repo.get = AsyncMock(return_value=None)
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "prediction tokens",
            },
        )
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
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
            assert "model_tokens" in data["data"]
            assert "prediction_tokens" in data["data"]
            assert "Model function not found" in data["data"]["model_tokens"]
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.PredictionRepository")
    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_prediction_details_prediction_not_found(
        self, mock_func_repo: Any, mock_pred_repo: Any, models_client: Any,
    ) -> None:
        """Test getting prediction details when prediction not found returns 404."""
        from app.auth.dependencies import get_current_active_user

        mock_func_repo.get = AsyncMock(
            return_value={
                "model_name": "test_model",
                "function_name": "test_func",
                "entrypoint": "0x1000",
                "tokens": "model tokens",
            },
        )
        mock_pred_repo.get_prediction_function = AsyncMock(return_value=None)
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
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
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_prediction_details_retrieval_error(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting prediction details when retrieval fails returns 400."""
        from app.auth.dependencies import get_current_active_user

        mock_func_repo.get = AsyncMock(side_effect=TypeError("Invalid data type"))
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
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
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_function_json_response(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting a function returns JSON (no HTML content negotiation)."""
        from app.auth.dependencies import get_current_active_user

        mock_func = Mock()
        mock_func.id = 1
        mock_func.function_name = "test_func"
        mock_func.entrypoint = "0x1000"
        mock_func.tokens = "test tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_func)
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunction",
                params={"model_name": "test_model", "function_name": "test_func"},
            )

            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type", "")
            data = response.json()
            assert data["data"]["function_name"] == "test_func"
            assert data["data"]["entrypoint"] == "0x1000"
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_functions_json_response(self, mock_func_repo: Any, models_client: Any) -> None:
        """Test getting functions returns JSON (no HTML content negotiation)."""
        from app.auth.dependencies import get_current_active_user

        mock_func1 = Mock()
        mock_func1.id = 1
        mock_func1.function_name = "func1"
        mock_func1.entrypoint = "0x1000"
        mock_func1.tokens = "tokens1"
        mock_func_repo.get_functions = AsyncMock(return_value=[mock_func1])
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getFunctions",
                params={"model_name": "test_model"},
            )

            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type", "")
            data = response.json()
            assert len(data["data"]["functions"]) == 1
            assert data["data"]["functions"][0]["function_name"] == "func1"
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.PredictionRepository")
    @patch("app.api.v1.endpoints.models.FunctionRepository")
    def test_get_prediction_details_json_response(
        self, mock_func_repo: Any, mock_pred_repo: Any, models_client: Any,
    ) -> None:
        """Test getting prediction details returns JSON (no HTML content negotiation)."""
        from app.auth.dependencies import get_current_active_user

        mock_model_info = Mock()
        mock_model_info.tokens = "model tokens"
        mock_func_repo.get = AsyncMock(return_value=mock_model_info)
        mock_pred_repo.get_prediction_function = AsyncMock(
            return_value={
                "tokens": "prediction tokens",
            },
        )
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.get(
                "/models/getPredictionDetails",
                params={
                    "model_name": "test_model",
                    "function_name": "test_func",
                    "task_name": "test_task",
                },
            )

            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type", "")
            data = response.json()
            assert data["data"]["task_name"] == "test_task"
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.ModelRepository")
    @patch("app.api.v1.endpoints.models.PredictionService")
    def test_delete_models_success(self, mock_pred_service: Any, mock_model_repo: Any, models_client: Any) -> None:
        """Test deleting multiple models successfully."""
        from app.auth.dependencies import get_current_active_user

        mock_model_repo.delete = AsyncMock()
        mock_pred_service.delete_predictions_for_model = AsyncMock()
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete(
                "/models/deleteModels",
                params={"model_names": "model1,model2,model3"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["deleted"] == ["model1", "model2", "model3"]
            assert data["data"]["failed"] == []
            assert mock_model_repo.delete.call_count == 3
        finally:
            clear_dependency_overrides(models_client)

    @patch("app.api.v1.endpoints.models.ModelRepository")
    @patch("app.api.v1.endpoints.models.PredictionService")
    def test_delete_models_partial_failure(
        self, mock_pred_service: Any, mock_model_repo: Any, models_client: Any,
    ) -> None:
        """Test deleting multiple models with some failures."""
        from app.auth.dependencies import get_current_active_user

        # First call succeeds, second raises, third succeeds
        mock_model_repo.delete = AsyncMock(side_effect=[None, Exception("DB error"), None])
        mock_pred_service.delete_predictions_for_model = AsyncMock()
        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete(
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
            clear_dependency_overrides(models_client)

    def test_delete_models_empty_names(self, models_client: Any) -> None:
        """Test deleting models with empty name list returns 400."""
        from app.auth.dependencies import get_current_active_user

        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete(
                "/models/deleteModels",
                params={"model_names": ""},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_MODEL_NAMES" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(models_client)

    def test_delete_models_whitespace_only_names(self, models_client: Any) -> None:
        """Test deleting models with whitespace-only names returns 400."""
        from app.auth.dependencies import get_current_active_user

        set_dependency_override(models_client, get_current_active_user, make_mock_user)

        try:
            response = models_client.delete(
                "/models/deleteModels",
                params={"model_names": "  ,  ,  "},
            )

            assert response.status_code == 400
            data = response.json()
            detail = data.get("detail", data)
            assert detail["success"] is False
            assert "INVALID_MODEL_NAMES" in detail.get("error", {}).get("code", "")
        finally:
            clear_dependency_overrides(models_client)
