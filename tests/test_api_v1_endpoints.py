"""Tests for API v1 endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router as config_router, ConfigPayload
from app.api.v1.endpoints.status import router as status_router, StatusUpdatePayload
from app.api.v1.endpoints.predictions import PredictTokensRequest


def _mock_current_user():
    """Mock current active user for testing."""
    mock_user = Mock()
    mock_user.id = 1
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


class TestConfigPayload:
    """Tests for ConfigPayload model."""

    def test_config_payload_minimal(self):
        """Test ConfigPayload with no fields."""
        payload = ConfigPayload()
        assert payload.max_file_size_mb is None
        assert payload.cpu_cores is None

    def test_config_payload_with_fields(self):
        """Test ConfigPayload with all fields."""
        payload = ConfigPayload(max_file_size_mb=100, cpu_cores=8)
        assert payload.max_file_size_mb == 100
        assert payload.cpu_cores == 8

    def test_config_payload_partial(self):
        """Test ConfigPayload with partial fields."""
        payload = ConfigPayload(max_file_size_mb=50)
        assert payload.max_file_size_mb == 50
        assert payload.cpu_cores is None


class TestStatusUpdatePayload:
    """Tests for StatusUpdatePayload model."""

    def test_status_update_payload(self):
        """Test StatusUpdatePayload with valid data."""
        payload = StatusUpdatePayload(status="running", uuid="test-uuid")
        assert payload.status == "running"
        assert payload.uuid == "test-uuid"

    def test_status_update_payload_with_whitespace(self):
        """Test StatusUpdatePayload strips whitespace."""
        payload = StatusUpdatePayload(status="  running  ", uuid="  test-uuid  ")
        assert payload.status == "running"
        assert payload.uuid == "test-uuid"


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


class TestConfigRouter:
    """Tests for config router endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with config router and auth override."""
        from fastapi import FastAPI
        from app.auth.dependencies import get_current_active_user

        app = FastAPI()
        app.include_router(config_router, prefix="/config")
        app.dependency_overrides[get_current_active_user] = _mock_current_user
        return TestClient(app)

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_success(self, mock_get_settings, client):
        """Test saving config successfully."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = client.post(
            "/config/save",
            json={"max_file_size_mb": 100, "cpu_cores": 4},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Configuration saved successfully" in data["message"]

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_invalid_cpu_cores(self, mock_get_settings, client):
        """Test saving config with invalid CPU cores."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = client.post(
            "/config/save",
            json={"cpu_cores": 100},  # Invalid: exceeds MAX_CPU_CORES
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "INVALID_CPU_CORES" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_partial_update(self, mock_get_settings, client):
        """Test saving config with partial update."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = client.post(
            "/config/save",
            json={"max_file_size_mb": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestStatusRouter:
    """Tests for status router endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with status router and auth override."""
        from fastapi import FastAPI
        from app.auth.dependencies import get_current_active_user

        app = FastAPI()
        app.include_router(status_router, prefix="/status")
        app.dependency_overrides[get_current_active_user] = _mock_current_user
        return TestClient(app)

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_get_status_success(self, mock_task_manager, client):
        """Test getting status successfully."""
        mock_instance = Mock()
        mock_instance.get_status.return_value = "running"
        mock_task_manager.return_value = mock_instance

        response = client.get("/status/getStatus", params={"uuid": "test-uuid"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_get_status_not_found(self, mock_task_manager, client):
        """Test getting status for non-existent UUID."""
        mock_instance = Mock()
        mock_instance.get_status.return_value = "UUID Not Found"
        mock_task_manager.return_value = mock_instance

        response = client.get("/status/getStatus", params={"uuid": "non-existent"})

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "UUID_NOT_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_update_status_success(self, mock_task_manager, client):
        """Test updating status successfully."""
        mock_instance = Mock()
        mock_instance.set_status.return_value = True
        mock_task_manager.return_value = mock_instance

        response = client.post(
            "/status/statusUpdate",
            json={"status": "completed", "uuid": "test-uuid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_status_empty_fields(self, client):
        """Test updating status with empty fields."""
        # Pydantic's StringConstraints with strip_whitespace=True and min_length=1
        # will reject empty strings after stripping, returning a 422 validation error
        response = client.post(
            "/status/statusUpdate",
            json={"status": "   ", "uuid": "   "},
        )

        # Pydantic validation error returns 422
        assert response.status_code == 422
        data = response.json()
        # Check that detail contains validation errors
        assert "detail" in data

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_update_status_not_found(self, mock_task_manager, client):
        """Test updating status for non-existent UUID."""
        mock_instance = Mock()
        mock_instance.set_status.return_value = False
        mock_task_manager.return_value = mock_instance

        response = client.post(
            "/status/statusUpdate",
            json={"status": "running", "uuid": "non-existent"},
        )

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "UUID_NOT_FOUND" in detail.get("error", {}).get("code", "")
