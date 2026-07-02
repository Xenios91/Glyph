"""Tests for API v1 endpoints."""

from typing import Any
from unittest.mock import patch

import pytest
from app.api.v1.endpoints.config import ConfigPayload
from app.api.v1.endpoints.predictions import PredictTokensRequest
from app.api.v1.endpoints.status import StatusUpdatePayload
from fastapi.testclient import TestClient
from pydantic import ValidationError


class TestConfigPayload:
    """Tests for ConfigPayload model."""

    def test_config_payload_minimal(self) -> None:
        """Test ConfigPayload with no fields."""
        payload = ConfigPayload()
        assert payload.max_file_size_mb is None
        assert payload.cpu_cores is None

    def test_config_payload_with_fields(self) -> None:
        """Test ConfigPayload with all fields."""
        payload = ConfigPayload(max_file_size_mb=100, cpu_cores=8)
        assert payload.max_file_size_mb == 100
        assert payload.cpu_cores == 8

    def test_config_payload_partial(self) -> None:
        """Test ConfigPayload with partial fields."""
        payload = ConfigPayload(max_file_size_mb=50)
        assert payload.max_file_size_mb == 50
        assert payload.cpu_cores is None


class TestStatusUpdatePayload:
    """Tests for StatusUpdatePayload model."""

    def test_status_update_payload(self) -> None:
        """Test StatusUpdatePayload with valid data."""
        payload = StatusUpdatePayload(status="running", uuid="test-uuid")
        assert payload.status == "running"
        assert payload.uuid == "test-uuid"

    def test_status_update_payload_with_whitespace(self) -> None:
        """Test StatusUpdatePayload strips whitespace."""
        payload = StatusUpdatePayload(status="  running  ", uuid="  test-uuid  ")
        assert payload.status == "running"
        assert payload.uuid == "test-uuid"


class TestPredictTokensRequest:
    """Tests for PredictTokensRequest model."""

    def test_predict_tokens_request_minimal(self) -> None:
        """Test PredictTokensRequest with minimal fields."""
        request = PredictTokensRequest(modelName="test_model", taskName="test_task")
        assert request.modelName == "test_model"
        assert request.taskName == "test_task"
        assert request.uuid is None

    def test_predict_tokens_request_with_uuid(self) -> None:
        """Test PredictTokensRequest with UUID."""
        request = PredictTokensRequest(modelName="test_model", taskName="test_task", uuid="test-uuid")
        assert request.modelName == "test_model"
        assert request.taskName == "test_task"
        assert request.uuid == "test-uuid"

    def test_predict_tokens_request_extra_fields(self) -> None:
        """Test PredictTokensRequest rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            PredictTokensRequest(modelName="test_model", **{"taskName": "test_task", "extra_field": "extra_value"})
        assert "Extra" in str(exc_info.value)


class TestConfigRouter:
    """Tests for config router endpoints."""

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_success(self, mock_get_settings: Any, config_client: TestClient) -> None:
        """Test saving config successfully."""
        from unittest.mock import Mock

        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = config_client.post(
            "/config/save",
            json={"max_file_size_mb": 100, "cpu_cores": 4},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Configuration saved successfully" in data["message"]

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_invalid_cpu_cores(self, mock_get_settings: Any, config_client: TestClient) -> None:
        """Test saving config with invalid CPU cores."""
        from unittest.mock import Mock

        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = config_client.post(
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
    @patch("app.api.v1.endpoints.config._persist_config_changes")
    def test_save_config_partial_update(
        self, mock_persist: Any, mock_get_settings: Any, config_client: TestClient
    ) -> None:
        """Test saving config with partial update."""
        from unittest.mock import Mock

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_get_settings.return_value = mock_settings
        mock_persist.return_value = None

        response = config_client.post(
            "/config/save",
            json={"max_file_size_mb": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestStatusRouter:
    """Tests for status router endpoints."""

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_get_status_success(self, mock_task_manager: Any, status_client: TestClient) -> None:
        """Test getting status successfully."""
        from unittest.mock import Mock

        mock_instance = Mock()
        mock_instance.get_status.return_value = "running"
        mock_task_manager.return_value = mock_instance

        response = status_client.get("/status/getStatus", params={"uuid": "test-uuid"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_get_status_not_found(self, mock_task_manager: Any, status_client: TestClient) -> None:
        """Test getting status for non-existent UUID."""
        from unittest.mock import Mock

        mock_instance = Mock()
        mock_instance.get_status.return_value = "UUID Not Found"
        mock_task_manager.return_value = mock_instance

        response = status_client.get("/status/getStatus", params={"uuid": "non-existent"})

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "UUID_NOT_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_update_status_success(self, mock_task_manager: Any, status_client: TestClient) -> None:
        """Test updating status successfully."""
        from unittest.mock import Mock

        mock_instance = Mock()
        mock_instance.set_status.return_value = True
        mock_task_manager.return_value = mock_instance

        response = status_client.post(
            "/status/statusUpdate",
            json={"status": "completed", "uuid": "test-uuid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_status_empty_fields(self, status_client: TestClient) -> None:
        """Test updating status with empty fields."""
        # Pydantic's StringConstraints with strip_whitespace=True and min_length=1
        # will reject empty strings after stripping, returning a 422 validation error
        response = status_client.post(
            "/status/statusUpdate",
            json={"status": "   ", "uuid": "   "},
        )

        # Pydantic validation error returns 422
        assert response.status_code == 422
        data = response.json()
        # Check that detail contains validation errors
        assert "detail" in data

    @patch("app.api.v1.endpoints.status.TaskManager")
    def test_update_status_not_found(self, mock_task_manager: Any, status_client: TestClient) -> None:
        """Test updating status for non-existent UUID."""
        from unittest.mock import Mock

        mock_instance = Mock()
        mock_instance.set_status.return_value = False
        mock_task_manager.return_value = mock_instance

        response = status_client.post(
            "/status/statusUpdate",
            json={"status": "running", "uuid": "non-existent"},
        )

        assert response.status_code == 404
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "UUID_NOT_FOUND" in detail.get("error", {}).get("code", "")
