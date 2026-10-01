"""Tests for API v1 endpoints."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml  # type: ignore[import-untyped]
from app.api.v1.endpoints.config import ConfigPayload, LLMConfigPayload
from app.api.v1.endpoints.predictions import PredictTokensRequest
from app.api.v1.endpoints.status import StatusUpdatePayload
from app.config.settings import LLMConfig
from app.services.llm_analysis_service import LLMNotConfiguredError, LLMTestResult
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


class TestLLMConfigPayload:
    """Tests for LLMConfigPayload model."""

    def test_llm_config_payload_minimal(self) -> None:
        """Test LLMConfigPayload with no fields."""
        payload = LLMConfigPayload()
        assert payload.enabled is None
        assert payload.base_url is None
        assert payload.port is None
        assert payload.api_path is None
        assert payload.model is None
        assert payload.api_key is None
        assert payload.timeout_seconds is None
        assert payload.temperature is None
        assert payload.max_tokens is None
        assert payload.max_concurrent is None
        assert payload.model_fields_set == set()

    def test_llm_config_payload_tracks_provided_fields(self) -> None:
        """Test that explicitly provided fields are tracked, including explicit nulls."""""
        payload = LLMConfigPayload(model="gpt-4o", port=None)
        assert payload.model == "gpt-4o"
        assert payload.port is None
        assert "model" in payload.model_fields_set
        assert "port" in payload.model_fields_set
        assert "api_key" not in payload.model_fields_set


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
        self, mock_persist: Any, mock_get_settings: Any, config_client: TestClient,
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


    @staticmethod
    def _llm_settings() -> Any:
        """Build a settings mock with real scalar values (yaml.dump-safe)."""
        from unittest.mock import Mock

        settings = Mock()
        settings.max_file_size_mb = 512
        settings.cpu_cores = 4
        settings.llm = LLMConfig()
        return settings

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_llm_full(
        self, mock_get_settings: Any, config_client: TestClient, tmp_path: Path, monkeypatch: Any,
    ) -> None:
        """Test saving an LLM config upserts the per-user row with normalized values."""
        settings = self._llm_settings()
        mock_get_settings.return_value = settings
        monkeypatch.setattr("app.api.v1.endpoints.config._CONFIG_FILE", tmp_path / "config.yml")

        with patch(
            "app.api.v1.endpoints.config.LLMUserConfigRepository.upsert", new_callable=AsyncMock,
        ) as mock_upsert:
            response = config_client.post(
                "/config/save",
                json={
                    "llm": {
                        "enabled": True,
                        "base_url": "http://localhost:8000/",
                        "api_path": "v1/chat/completions",
                        "model": "  llama-3  ",
                        "api_key": "sk-test",
                        "port": None,
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Normalized values are stored per user, not in the global settings.
        mock_upsert.assert_awaited_once_with(
            1,
            {
                "enabled": True,
                "base_url": "http://localhost:8000",
                "api_path": "/v1/chat/completions",
                "model": "llama-3",
                "api_key": "sk-test",
                "port": None,
            },
        )

        # The global config.yml must not receive the user's LLM settings.
        persisted = yaml.safe_load((tmp_path / "config.yml").read_text(encoding="utf-8"))
        assert persisted == {"max_file_size_mb": 512, "cpu_cores": 4}

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_llm_partial_preserves_other_fields(
        self, mock_get_settings: Any, config_client: TestClient, tmp_path: Path, monkeypatch: Any,
    ) -> None:
        """Test that a partial LLM update only upserts the provided fields."""
        settings = self._llm_settings()
        mock_get_settings.return_value = settings
        config_file = tmp_path / "config.yml"
        config_file.write_text(
            yaml.safe_dump({"cpu_cores": 1, "max_file_size_mb": 512, "llm": {"model": "old-model", "api_key": "sk-old"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr("app.api.v1.endpoints.config._CONFIG_FILE", config_file)

        with patch(
            "app.api.v1.endpoints.config.LLMUserConfigRepository.upsert", new_callable=AsyncMock,
        ) as mock_upsert:
            response = config_client.post("/config/save", json={"llm": {"model": "new-model"}})

        assert response.status_code == 200
        mock_upsert.assert_awaited_once_with(1, {"model": "new-model"})
        # The global file's llm section (global defaults) is left untouched.
        persisted = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert persisted["llm"] == {"model": "old-model", "api_key": "sk-old"}

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_llm_port_null_clears(
        self, mock_get_settings: Any, config_client: TestClient, tmp_path: Path, monkeypatch: Any,
    ) -> None:
        """Test that an explicit null port is upserted as a clear for the user row."""
        settings = self._llm_settings()
        mock_get_settings.return_value = settings
        config_file = tmp_path / "config.yml"
        config_file.write_text(
            yaml.safe_dump({"cpu_cores": 1, "max_file_size_mb": 512, "llm": {"port": 9999}}),
            encoding="utf-8",
        )
        monkeypatch.setattr("app.api.v1.endpoints.config._CONFIG_FILE", config_file)

        with patch(
            "app.api.v1.endpoints.config.LLMUserConfigRepository.upsert", new_callable=AsyncMock,
        ) as mock_upsert:
            response = config_client.post("/config/save", json={"llm": {"port": None}})

        assert response.status_code == 200
        mock_upsert.assert_awaited_once_with(1, {"port": None})
        persisted = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert persisted["llm"] == {"port": 9999}

    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_without_llm_leaves_section(
        self, mock_get_settings: Any, config_client: TestClient, tmp_path: Path, monkeypatch: Any,
    ) -> None:
        """Test that saving without llm fields leaves a pre-seeded llm section untouched."""
        settings = self._llm_settings()
        mock_get_settings.return_value = settings
        config_file = tmp_path / "config.yml"
        config_file.write_text(
            yaml.safe_dump({"cpu_cores": 1, "max_file_size_mb": 512, "llm": {"model": "keep-me"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr("app.api.v1.endpoints.config._CONFIG_FILE", config_file)

        response = config_client.post("/config/save", json={"cpu_cores": 4})

        assert response.status_code == 200
        persisted = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert persisted["llm"] == {"model": "keep-me"}

    @pytest.mark.parametrize(
        ("llm_payload", "expected_code"),
        [
            ({"base_url": "ftp://example.com"}, "INVALID_LLM_BASE_URL"),
            ({"base_url": "example.com"}, "INVALID_LLM_BASE_URL"),
            ({"base_url": "https://"}, "INVALID_LLM_BASE_URL"),
            ({"base_url": "https://api.openai.com/v1"}, "INVALID_LLM_BASE_URL"),
            ({"base_url": "https://api.openai.com:badport"}, "INVALID_LLM_BASE_URL"),
            ({"port": 0}, "INVALID_LLM_PORT"),
            ({"port": 70000}, "INVALID_LLM_PORT"),
            ({"api_path": ""}, "INVALID_LLM_API_PATH"),
            ({"model": "   "}, "INVALID_LLM_MODEL"),
            ({"timeout_seconds": 1}, "INVALID_LLM_TIMEOUT"),
            ({"timeout_seconds": 601}, "INVALID_LLM_TIMEOUT"),
            ({"temperature": 3}, "INVALID_LLM_TEMPERATURE"),
            ({"max_tokens": 0}, "INVALID_LLM_MAX_TOKENS"),
            ({"max_concurrent": 0}, "INVALID_LLM_MAX_CONCURRENT"),
        ],
    )
    @patch("app.api.v1.endpoints.config.get_settings")
    def test_save_config_invalid_llm(
        self, mock_get_settings: Any, config_client: TestClient, llm_payload: dict[str, Any], expected_code: str,
    ) -> None:
        """Test that invalid LLM values are rejected with an INVALID_LLM_* code."""
        from unittest.mock import Mock

        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        response = config_client.post("/config/save", json={"llm": llm_payload})

        assert response.status_code == 400
        data = response.json()
        # HTTPException wraps detail in {"detail": ...}
        detail = data.get("detail", data)
        assert detail.get("error", {}).get("code", "") == expected_code


class TestLLMTestEndpoint:
    """Tests for the POST /config/llm-test endpoint."""

    @patch("app.api.v1.endpoints.config.test_llm_connection", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.config.resolve_user_llm_config", new_callable=AsyncMock)
    def test_llm_test_not_configured(
        self, mock_resolve: Any, mock_test: Any, config_client: TestClient,
    ) -> None:
        """Test that a missing LLM configuration returns 503."""
        mock_resolve.return_value = LLMConfig()
        mock_test.side_effect = LLMNotConfiguredError("LLM analysis is disabled")

        response = config_client.post("/config/llm-test")

        assert response.status_code == 503
        data = response.json()
        detail = data.get("detail", data)
        assert detail.get("error", {}).get("code", "") == "LLM_NOT_CONFIGURED"
        mock_resolve.assert_awaited_once_with(1)

    @patch("app.api.v1.endpoints.config.test_llm_connection", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.config.resolve_user_llm_config", new_callable=AsyncMock)
    def test_llm_test_success(
        self, mock_resolve: Any, mock_test: Any, config_client: TestClient,
    ) -> None:
        """Test that a successful connection test returns ok with model info."""
        mock_resolve.return_value = LLMConfig()
        mock_test.return_value = LLMTestResult(ok=True, model="gpt-4o-mini", elapsed_ms=42)

        response = config_client.post("/config/llm-test")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["ok"] is True
        assert data["data"]["model"] == "gpt-4o-mini"
        assert data["data"]["elapsed_ms"] == 42
        mock_resolve.assert_awaited_once_with(1)

    @patch("app.api.v1.endpoints.config.test_llm_connection", new_callable=AsyncMock)
    @patch("app.api.v1.endpoints.config.resolve_user_llm_config", new_callable=AsyncMock)
    def test_llm_test_failure(
        self, mock_resolve: Any, mock_test: Any, config_client: TestClient,
    ) -> None:
        """Test that a failed connection test returns ok=false with the error."""
        mock_resolve.return_value = LLMConfig()
        mock_test.return_value = LLMTestResult(ok=False, error="HTTP 500: boom")

        response = config_client.post("/config/llm-test")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["ok"] is False
        assert data["data"]["error"] == "HTTP 500: boom"


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
