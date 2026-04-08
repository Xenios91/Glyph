"""Tests for API v1 endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router as config_router, ConfigPayload
from app.api.v1.endpoints.status import router as status_router, StatusUpdatePayload
from app.api.v1.endpoints.predictions import PredictTokensRequest
from app.api.v1.endpoints.tasks import router as tasks_router, TaskRequest


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


class TestTaskRequest:
    """Tests for TaskRequest model."""

    def test_task_request_minimal(self):
        """Test TaskRequest with minimal fields."""
        request = TaskRequest(type="training")
        assert request.type == "training"
        assert request.modelName is None
        assert request.uuid is None
        assert request.overwriteModel is False
        assert request.data is None

    def test_task_request_full(self):
        """Test TaskRequest with all fields."""
        request = TaskRequest(
            type="training",
            modelName="test_model",
            uuid="test-uuid",
            overwriteModel=True,
            data={"key": "value"},
        )
        assert request.type == "training"
        assert request.modelName == "test_model"
        assert request.uuid == "test-uuid"
        assert request.overwriteModel is True
        assert request.data == {"key": "value"}


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
        """Create test client with config router."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(config_router, prefix="/config")
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
        """Create test client with status router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(status_router, prefix="/status")
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


class TestTasksRouter:
    """Tests for tasks router endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with tasks router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(tasks_router, prefix="/tasks")
        return TestClient(app)

    @patch("app.api.v1.endpoints.tasks.Trainer")
    @patch("app.api.v1.endpoints.tasks.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.tasks.TrainingRequest")
    @patch("app.api.v1.endpoints.tasks.FunctionPersistanceUtil")
    @patch("app.api.v1.endpoints.tasks.create_success_response")
    def test_train_model_success(
        self,
        mock_create_success,
        mock_func_persistance,
        mock_training_request,
        mock_ml_persistance,
        mock_trainer,
        client,
    ):
        """Test training model successfully."""
        mock_ml_persistance.check_name.return_value = False

        mock_tr_instance = Mock()
        mock_tr_instance.start_training = Mock()
        mock_trainer.return_value = mock_tr_instance

        mock_req_instance = Mock()
        mock_req_instance.uuid = "test-uuid"
        mock_training_request.return_value = mock_req_instance

        mock_response = Mock()
        mock_response.model_dump.return_value = {"success": True, "message": "Training task created successfully"}
        mock_create_success.return_value = mock_response

        response = client.post(
            "/tasks/task",
            json={
                "type": "training",
                "modelName": "test_model",
                "data": {"tokens": "test"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "Training task created successfully" in data["message"]

    @patch("app.api.v1.endpoints.tasks.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.tasks.create_error_response")
    def test_train_model_name_exists(self, mock_create_error, mock_ml_persistance, client):
        """Test training model with existing name."""
        mock_ml_persistance.check_name.return_value = True

        mock_response = Mock()
        mock_response.model_dump.return_value = {"success": False, "error_code": "MODEL_NAME_EXISTS"}
        mock_create_error.return_value = mock_response

        response = client.post(
            "/tasks/task",
            json={
                "type": "training",
                "modelName": "existing_model",
                "data": {"tokens": "test"},
            },
        )

        assert response.status_code == 400
        data = response.json()
        
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "MODEL_NAME_EXISTS" in detail.get("error_code", "")

    @patch("app.api.v1.endpoints.tasks.MLPersistanceUtil")
    @patch("app.api.v1.endpoints.tasks.Trainer")
    @patch("app.api.v1.endpoints.tasks.TrainingRequest")
    @patch("app.api.v1.endpoints.tasks.FunctionPersistanceUtil")
    @patch("app.api.v1.endpoints.tasks.create_success_response")
    def test_train_model_overwrite_allowed(
        self,
        mock_create_success,
        mock_ml_persistance,
        mock_trainer,
        mock_training_request,
        mock_func_persistance,
        client,
    ):
        """Test training model with overwrite flag."""
        mock_ml_persistance.check_name.return_value = True

        mock_tr_instance = Mock()
        mock_tr_instance.start_training = Mock()
        mock_trainer.return_value = mock_tr_instance

        mock_req_instance = Mock()
        mock_req_instance.uuid = "test-uuid"
        mock_training_request.return_value = mock_req_instance

        mock_response = Mock()
        mock_response.model_dump.return_value = {"success": True, "message": "Training task created successfully"}
        mock_create_success.return_value = mock_response

        response = client.post(
            "/tasks/task",
            json={
                "type": "training",
                "modelName": "existing_model",
                "overwriteModel": True,
                "data": {"tokens": "test"},
            },
        )

        assert response.status_code == 201

    @patch("app.api.v1.endpoints.tasks.Predictor")
    @patch("app.api.v1.endpoints.tasks.Trainer")
    @patch("app.api.v1.endpoints.tasks.PredictionRequest")
    @patch("app.api.v1.endpoints.tasks.create_success_response")
    def test_predict_tokens_success(
        self,
        mock_create_success,
        mock_prediction_request,
        mock_trainer,
        mock_predictor,
        client,
    ):
        """Test predicting tokens successfully."""
        mock_tr_instance = Mock()
        mock_tr_instance.get_uuid.return_value = "test-uuid"
        mock_trainer.return_value = mock_tr_instance

        mock_pred_instance = Mock()
        mock_pred_instance.start_prediction = Mock()
        mock_predictor.return_value = mock_pred_instance

        mock_req_instance = Mock()
        mock_req_instance.uuid = "test-uuid"
        mock_prediction_request.return_value = mock_req_instance

        mock_response = Mock()
        mock_response.model_dump.return_value = {"success": True, "message": "Prediction task created successfully"}
        mock_create_success.return_value = mock_response

        response = client.post(
            "/tasks/task",
            json={
                "type": "prediction",
                "modelName": "test_model",
                "data": {"tokens": "test"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "Prediction task created successfully" in data["message"]

    @patch("app.api.v1.endpoints.tasks.create_error_response")
    def test_invalid_task_type(self, mock_create_error, client):
        """Test handling invalid task type."""
        mock_response = Mock()
        mock_response.model_dump.return_value = {"success": False, "error_code": "INVALID_REQUEST_TYPE"}
        mock_create_error.return_value = mock_response

        response = client.post(
            "/tasks/task",
            json={
                "type": "invalid_type",
                "modelName": "test_model",
            },
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException wraps detail in 'detail' key
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "INVALID_REQUEST_TYPE" in detail.get("error_code", "")


class TestTrainModelFunction:
    """Tests for train_model validation via endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with tasks router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(tasks_router, prefix="/tasks")
        return TestClient(app)

    def test_train_model_no_model_name(self, client):
        """Test training task with no model name returns 400."""
        response = client.post(
            "/tasks/task",
            json={
                "type": "training",
            },
        )

        assert response.status_code == 400
        data = response.json()
        
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "INVALID_MODEL_NAME" in detail.get("error", {}).get("code", "")


class TestPredictTokensFunction:
    """Tests for predict_tokens validation via endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with tasks router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(tasks_router, prefix="/tasks")
        return TestClient(app)

    def test_predict_tokens_no_model_name(self, client):
        """Test prediction task with no model name returns 400."""
        response = client.post(
            "/tasks/task",
            json={
                "type": "prediction",
            },
        )

        assert response.status_code == 400
        data = response.json()
        # HTTPException wraps detail in 'detail' key
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "INVALID_MODEL_NAME" in detail.get("error", {}).get("code", "")
