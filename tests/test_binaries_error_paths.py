"""Error path tests for binaries API v1 endpoints.

Covers validation failures, ownership checks, and edge cases
that are not exercised by the existing endpoint tests.

Note: The binaries module imports TaskManager and Ghidra from heavy
processing modules at module level. Those imports are mocked via patch
in each test class that needs the full router.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import create_app_client
from tests.factories import make_user, make_binary, make_binary_function


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEAVY_MODULES = [
    "app.processing.task_management",
    "app.processing.pipeline",
    "app.processing.ghidra_processor",
    "app.processing.steps",
    "app.services.request_handler",
    "app.database.function_repository",
]


def _mock_heavy_modules() -> list[tuple[str, Any | None]]:
    """Replace heavy modules with mocks and return originals for restore."""
    originals: list[tuple[str, Any | None]] = []
    for mod in _HEAVY_MODULES:
        originals.append((mod, sys.modules.get(mod)))
        sys.modules[mod] = MagicMock()
    return originals


def _restore_heavy_modules(originals: list[tuple[str, Any | None]]) -> None:
    """Restore original modules after test."""
    for mod, original in originals:
        if original is not None:
            sys.modules[mod] = original
        else:
            sys.modules.pop(mod, None)


@pytest.fixture(autouse=True)
def _isolate_sys_modules() -> Any:
    """Isolate sys.modules for heavy module mocking across this file."""
    originals = _mock_heavy_modules()
    yield
    _restore_heavy_modules(originals)


# ---------------------------------------------------------------------------
# BinaryUploadForm validation
# ---------------------------------------------------------------------------


class TestBinaryUploadFormValidation:
    """Tests for BinaryUploadForm Pydantic model validation."""

    def test_name_required(self) -> None:
        """Empty name should raise validation error."""
        from app.api.v1.endpoints.binaries import BinaryUploadForm

        with pytest.raises(Exception):  # Pydantic validation error
            BinaryUploadForm(name="")

    def test_name_stripped(self) -> None:
        """Name with whitespace should be stripped."""
        from app.api.v1.endpoints.binaries import BinaryUploadForm

        form = BinaryUploadForm(name="  my_binary  ")
        assert form.name == "my_binary"

    def test_name_validator_rejects_none(self) -> None:
        """Name validator should reject None via Pydantic validation error."""
        from app.api.v1.endpoints.binaries import BinaryUploadForm

        # Passing None triggers the strip_name validator which raises ValueError
        with pytest.raises(Exception):  # Pydantic wraps ValueError
            BinaryUploadForm(name=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BinaryUploadService.sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    """Tests for BinaryUploadService.sanitize_filename helper."""

    def test_path_traversal_rejected(self) -> None:
        """Filenames with path traversal should raise ValidationError."""
        from app.exceptions import ValidationError
        from app.services.binary_upload_service import BinaryUploadService

        with pytest.raises(ValidationError):
            BinaryUploadService.sanitize_filename("../etc/passwd")

    def test_null_byte_rejected(self) -> None:
        """Filenames with null bytes should raise ValidationError."""
        from app.exceptions import ValidationError
        from app.services.binary_upload_service import BinaryUploadService

        with pytest.raises(ValidationError):
            BinaryUploadService.sanitize_filename("test\x00.elf")

    def test_safe_filename_allowed(self) -> None:
        """Safe filenames should pass through."""
        from app.services.binary_upload_service import BinaryUploadService

        result = BinaryUploadService.sanitize_filename("my_binary.elf")
        assert result == "my_binary.elf"

    def test_empty_filename_rejected(self) -> None:
        """Empty filename should raise ValidationError."""
        from app.exceptions import ValidationError
        from app.services.binary_upload_service import BinaryUploadService

        with pytest.raises(ValidationError):
            BinaryUploadService.sanitize_filename("")


# ---------------------------------------------------------------------------
# BinaryUploadService.validate_mime_type
# ---------------------------------------------------------------------------


class TestValidateBinaryMimeType:
    """Tests for BinaryUploadService.validate_mime_type helper."""

    def test_allowed_mime_type(self) -> None:
        """Allowed MIME types should not raise."""
        from app.services.binary_upload_service import BinaryUploadService

        with patch("app.services.binary_upload_service.magic") as mock_magic:
            mock_magic.from_buffer.return_value = "application/x-executable"
            BinaryUploadService.validate_mime_type(b"\x7fELF")

    def test_disallowed_mime_type(self) -> None:
        """Text files should raise ValidationError."""
        from app.exceptions import ValidationError
        from app.services.binary_upload_service import BinaryUploadService

        with patch("app.services.binary_upload_service.magic") as mock_magic:
            mock_magic.from_buffer.return_value = "text/plain"
            with pytest.raises(ValidationError):
                BinaryUploadService.validate_mime_type(b"hello world")

    def test_magic_detection_failure(self) -> None:
        """Magic detection failure should raise ValidationError."""
        from app.exceptions import ValidationError
        from app.services.binary_upload_service import BinaryUploadService

        with patch("app.services.binary_upload_service.magic") as mock_magic:
            mock_magic.from_buffer.side_effect = Exception("failed")
            with pytest.raises(ValidationError):
                BinaryUploadService.validate_mime_type(b"\x00")


# ---------------------------------------------------------------------------
# get_binary_detail - error paths
# ---------------------------------------------------------------------------


class TestGetBinaryDetailErrorPaths:
    """Error paths for GET /binaries/{binary_id}."""

    @pytest.fixture
    def mock_user(self) -> Any:
        return make_user(user_id=1, username="testuser")

    @pytest.fixture
    def mock_user_other(self) -> Any:
        return make_user(user_id=99, username="other_user")

    def test_binary_not_found(self, mock_user: Any) -> None:
        """Requesting non-existent binary should return 404."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user
        from app.exceptions import BinaryNotFoundError

        binaries._upload_service.get_binary = AsyncMock(
            side_effect=BinaryNotFoundError(binary_id=999)
        )
        binaries._upload_service.get_function_count = AsyncMock(return_value=0)

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.get("/binaries/999")
        assert response.status_code == 404

    def test_access_denied_wrong_owner(self, mock_user: Any, mock_user_other: Any) -> None:
        """Requesting another user's binary should return 403."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user
        from app.exceptions import BinaryAccessError

        binaries._upload_service.get_binary = AsyncMock(side_effect=BinaryAccessError(binary_id=1, user_id=mock_user.id))
        binaries._upload_service.get_function_count = AsyncMock(return_value=0)

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.get("/binaries/1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# list_binary_functions - error paths
# ---------------------------------------------------------------------------


class TestListBinaryFunctionsErrorPaths:
    """Error paths for GET /functions/{binary_id}."""

    @pytest.fixture
    def mock_user(self) -> Any:
        return make_user(user_id=1, username="testuser")

    def test_functions_binary_not_found(self, mock_user: Any) -> None:
        """Listing functions for non-existent binary should return 404."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user
        from app.exceptions import BinaryNotFoundError

        binaries._upload_service.get_binary = AsyncMock(
            side_effect=BinaryNotFoundError(binary_id=999)
        )
        binaries._upload_service.get_function_count = AsyncMock(return_value=0)

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.get("/functions/999")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# delete_binary - error paths
# ---------------------------------------------------------------------------


class TestDeleteBinaryErrorPaths:
    """Error paths for DELETE /binaries/{binary_id}."""

    @pytest.fixture
    def mock_user(self) -> Any:
        return make_user(user_id=1, username="testuser")

    @pytest.fixture
    def mock_user_other(self) -> Any:
        return make_user(user_id=99, username="other_user")

    def test_delete_binary_not_found(self, mock_user: Any) -> None:
        """Deleting non-existent binary should return 404."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user
        from app.exceptions import BinaryNotFoundError

        binaries._upload_service.get_binary = AsyncMock(
            side_effect=BinaryNotFoundError(binary_id=999)
        )

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.delete("/binaries/999")
        assert response.status_code == 404

    def test_delete_access_denied_wrong_owner(self, mock_user: Any, mock_user_other: Any) -> None:
        """Deleting another user's binary should return 403."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user
        from app.exceptions import BinaryAccessError

        binaries._upload_service.get_binary = AsyncMock(
            side_effect=BinaryAccessError(binary_id=1, user_id=mock_user.id)
        )

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.delete("/binaries/1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# list_binaries - empty state
# ---------------------------------------------------------------------------


class TestListBinariesEmpty:
    """Tests for GET /list with no binaries."""

    @pytest.fixture
    def mock_user(self) -> Any:
        return make_user(user_id=1, username="testuser")

    def test_empty_binary_list(self, mock_user: Any) -> None:
        """Empty binary list should return 200 with empty array."""
        from app.api.v1.endpoints import binaries
        from app.auth.dependencies import get_current_active_user

        binaries._upload_service.list_binaries = AsyncMock(return_value=([], 0))

        client = create_app_client(
            routers=[(binaries.router, "")],
            dependency_overrides={get_current_active_user: lambda: mock_user},
        )
        response = client.get("/list")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0
