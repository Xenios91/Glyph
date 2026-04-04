"""Tests for binaries API v1 endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import UploadFile
import io

from app.api.v1.endpoints.binaries import router as binaries_router, UploadBinaryRequest


class TestUploadBinaryRequest:
    """Tests for UploadBinaryRequest model."""

    def test_upload_binary_request_minimal(self):
        """Test UploadBinaryRequest with minimal fields."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.bin"
        request = UploadBinaryRequest(
            binary_file=mock_file,
            model_name="test_model",
            ml_class_type="test_type",
        )
        assert request.model_name == "test_model"
        assert request.ml_class_type == "test_type"
        assert request.training_data == "false"
        assert request.task_name is None

    def test_upload_binary_request_full(self):
        """Test UploadBinaryRequest with all fields."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.bin"
        request = UploadBinaryRequest(
            binary_file=mock_file,
            training_data="true",
            model_name="test_model",
            ml_class_type="test_type",
            task_name="test_task",
        )
        assert request.training_data == "true"
        assert request.model_name == "test_model"
        assert request.ml_class_type == "test_type"
        assert request.task_name == "test_task"


class TestBinariesRouter:
    """Tests for binaries router endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client with binaries router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(binaries_router, prefix="/binaries")
        return TestClient(app, raise_server_exceptions=True)

    @patch("app.api.v1.endpoints.binaries._run_ghidra_analysis")
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.validate_binary_mime_type")
    @patch("app.api.v1.endpoints.binaries.sanitize_filename")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_upload_binary_success(
        self,
        mock_os,
        mock_uuid,
        mock_sanitize,
        mock_validate,
        mock_get_settings,
        mock_run_ghidra,
        client,
    ):
        """Test successful binary upload."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Mock UUID
        mock_uuid.uuid4.return_value = "test-uuid-123"

        # Create test file
        file_content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
        file = io.BytesIO(file_content)
        upload_file = UploadFile(
            file=file,
            filename="test_binary.elf",
        )

        response = client.post(
            "/binaries/uploadBinary",
            files={"binary_file": upload_file},
            data={
                "training_data": "true",
                "model_name": "test_model",
                "ml_class_type": "test_type",
                "task_name": "test_task",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "uuid" in data["data"]
        assert "Binary uploaded successfully" in data["message"]

    @patch("app.api.v1.endpoints.binaries._run_ghidra_analysis")
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.validate_binary_mime_type")
    @patch("app.api.v1.endpoints.binaries.sanitize_filename")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_upload_binary_no_file(
        self,
        mock_os,
        mock_uuid,
        mock_sanitize,
        mock_validate,
        mock_get_settings,
        mock_run_ghidra,
        client,
    ):
        """Test upload without file returns 400."""
        response = client.post(
            "/binaries/uploadBinary",
            data={
                "training_data": "true",
                "model_name": "test_model",
                "ml_class_type": "test_type",
            },
        )

        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "NO_FILE_FOUND" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.binaries._run_ghidra_analysis")
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.validate_binary_mime_type")
    @patch("app.api.v1.endpoints.binaries.sanitize_filename")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_upload_binary_file_too_large(
        self,
        mock_os,
        mock_uuid,
        mock_sanitize,
        mock_validate,
        mock_get_settings,
        mock_run_ghidra,
        client,
    ):
        """Test upload with file exceeding max size returns 413."""
        # Mock settings with small max size
        mock_settings = Mock()
        mock_settings.max_file_size_mb = 0  # 0 MB = 0 bytes
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Create test file larger than max
        file_content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 1000
        file = io.BytesIO(file_content)
        upload_file = UploadFile(
            file=file,
            filename="large_binary.elf",
        )

        response = client.post(
            "/binaries/uploadBinary",
            files={"binary_file": upload_file},
            data={
                "training_data": "true",
                "model_name": "test_model",
                "ml_class_type": "test_type",
            },
        )

        assert response.status_code == 413
        data = response.json()
        detail = data.get("detail", data)
        assert detail["success"] is False
        assert "FILE_TOO_LARGE" in detail.get("error", {}).get("code", "")

    @patch("app.api.v1.endpoints.binaries._run_ghidra_analysis")
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.validate_binary_mime_type")
    @patch("app.api.v1.endpoints.binaries.sanitize_filename")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_upload_binary_invalid_mime_type(
        self,
        mock_os,
        mock_uuid,
        mock_sanitize,
        mock_validate,
        mock_get_settings,
        mock_run_ghidra,
        client,
    ):
        """Test upload with invalid MIME type returns 400."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Mock validate to raise HTTPException
        from fastapi import HTTPException
        mock_validate.side_effect = HTTPException(
            status_code=400,
            detail="File type 'text/plain' not allowed. Expected binary/ELF format",
        )

        # Create test file
        file_content = b"Hello, World!"
        file = io.BytesIO(file_content)
        upload_file = UploadFile(
            file=file,
            filename="text_file.txt",
        )

        response = client.post(
            "/binaries/uploadBinary",
            files={"binary_file": upload_file},
            data={
                "training_data": "true",
                "model_name": "test_model",
                "ml_class_type": "test_type",
            },
        )

        assert response.status_code == 400

    @patch("app.api.v1.endpoints.binaries._run_ghidra_analysis")
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.validate_binary_mime_type")
    @patch("app.api.v1.endpoints.binaries.sanitize_filename")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_upload_binary_path_traversal_blocked(
        self,
        mock_os,
        mock_uuid,
        mock_sanitize,
        mock_validate,
        mock_get_settings,
        mock_run_ghidra,
        client,
    ):
        """Test upload with path traversal filename returns 400."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Mock sanitize to raise HTTPException
        from fastapi import HTTPException
        mock_sanitize.side_effect = HTTPException(
            status_code=400,
            detail="Invalid filename characters",
        )

        # Create test file
        file_content = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100
        file = io.BytesIO(file_content)
        upload_file = UploadFile(
            file=file,
            filename="../etc/passwd",
        )

        response = client.post(
            "/binaries/uploadBinary",
            files={"binary_file": upload_file},
            data={
                "training_data": "true",
                "model_name": "test_model",
                "ml_class_type": "test_type",
            },
        )

        assert response.status_code == 400

    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_list_bins_success(self, mock_os, mock_get_settings, client):
        """Test listing binaries successfully."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Mock os.walk
        mock_os.walk.return_value = [
            ("/tmp/uploads", [], ["binary1.elf", "binary2.elf"])
        ]

        response = client.get("/binaries/listBins")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "binary1.elf" in data["data"]["files"]
        assert "binary2.elf" in data["data"]["files"]

    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_list_bins_empty(self, mock_os, mock_get_settings, client):
        """Test listing binaries when directory is empty."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        # Mock os.walk with empty directory
        mock_os.walk.return_value = [("/tmp/uploads", [], [])]

        response = client.get("/binaries/listBins")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["files"] == []
