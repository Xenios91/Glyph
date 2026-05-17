"""Tests for binaries API v1 endpoints."""

from typing import Any, Generator

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.api.v1.endpoints.binaries import router as binaries_router, BinaryUploadForm
from app.database.models import User


def mock_get_current_user() -> User:
    """Mock current active user for testing."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )


class TestBinaryUploadForm:
    """Tests for BinaryUploadForm model."""

    def test_binary_upload_form_minimal(self) -> None:
        """Test BinaryUploadForm with minimal fields."""
        request = BinaryUploadForm(
            model_name="test_model",
            ml_class_type="test_type",
            name="test_name",
        )
        assert request.model_name == "test_model"
        assert request.ml_class_type == "test_type"
        assert request.training_data == "false"
        assert request.name == "test_name"

    def test_binary_upload_form_full(self) -> None:
        """Test BinaryUploadForm with all fields."""
        request = BinaryUploadForm(
            training_data="true",
            model_name="test_model",
            ml_class_type="test_type",
            name="test_name",
        )
        assert request.training_data == "true"
        assert request.model_name == "test_model"
        assert request.ml_class_type == "test_type"
        assert request.name == "test_name"

    def test_binary_upload_form_strips_whitespace(self) -> None:
        """Test that string fields are stripped of whitespace."""
        request = BinaryUploadForm(
            model_name="  test_model  ",
            ml_class_type="  test_type  ",
            name="  test_name  ",
        )
        assert request.model_name == "test_model"
        assert request.ml_class_type == "test_type"
        assert request.name == "test_name"

    def test_binary_upload_form_training_data_validation(self) -> None:
        """Test that training_data accepts 'true' and 'false' (case-insensitive)."""
        request = BinaryUploadForm(
            training_data="TRUE",
            model_name="test_model",
            ml_class_type="test_type",
            name="test_name",
        )
        assert request.training_data == "true"

        request = BinaryUploadForm(
            training_data=" False ",
            model_name="test_model",
            ml_class_type="test_type",
            name="test_name",
        )
        assert request.training_data == "false"

    def test_binary_upload_form_invalid_training_data(self) -> None:
        """Test that training_data rejects invalid values."""
        with pytest.raises(Exception):
            BinaryUploadForm(
                training_data="yes",
                model_name="test_model",
                ml_class_type="test_type",
                name="test_name",
            )

    def test_binary_upload_form_empty_model_name_rejected(self) -> None:
        """Test that empty model_name is rejected."""
        with pytest.raises(Exception):
            BinaryUploadForm(
                model_name="",
                ml_class_type="test_type",
                name="test_name",
            )

    def test_binary_upload_form_whitespace_only_model_name_rejected(self) -> None:
        """Test that whitespace-only model_name is rejected."""
        with pytest.raises(Exception):
            BinaryUploadForm(
                model_name="   ",
                ml_class_type="test_type",
                name="test_name",
            )


class TestBinariesRouter:
    """Tests for binaries router endpoints."""

    @pytest.fixture
    def client(self) -> Generator[TestClient, Any, Any]:
        """Create test client with binaries router."""
        from fastapi import FastAPI
        from app.auth.dependencies import get_current_active_user
        app = FastAPI()
        app.include_router(binaries_router, prefix="/binaries")
        app.dependency_overrides[get_current_active_user] = mock_get_current_user  # pyright: ignore[reportArgumentType, reportCallIssue]
        test_client = TestClient(app, raise_server_exceptions=False)
        yield test_client
        # Clean up overrides after test
        app.dependency_overrides.clear()  # pyright: ignore[reportAttributeAccessIssue]

    @staticmethod
    def _setup_mock_os(mock_os: Any) -> None:
        """Helper to set up os mock with proper behavior."""
        def _join(*args: tuple[str, ...]) -> str:
            return "/".join(str(a) for a in args)
        mock_os.path.join = _join
        mock_os.makedirs = MagicMock()
        mock_os.chmod = MagicMock()
        mock_os.walk = MagicMock(return_value=[("/tmp/uploads", [], [])])

    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    def test_list_bins_success(self, mock_os: Any, mock_get_settings: Any, client: TestClient) -> None:
        """Test listing binaries successfully."""
        self._setup_mock_os(mock_os)

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
    def test_list_bins_empty(self, mock_os: Any, mock_get_settings: Any, client: TestClient) -> None:
        """Test listing binaries when directory is empty."""
        self._setup_mock_os(mock_os)

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
