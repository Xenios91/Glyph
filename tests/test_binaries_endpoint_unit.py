"""Unit tests for binaries API v1 endpoints with mocking to ensure full coverage.

CRITICAL: Heavy modules (TaskManager, ProcessingPipeline) are mocked at sys.modules
level BEFORE importing from binaries.py to prevent ProcessPoolExecutor from spawning
child processes that hang indefinitely.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open

# -----------------------------------------------------------------------
# Mock heavy modules BEFORE importing from binaries.py
# This prevents ProcessPoolExecutor from spawning child processes
# -----------------------------------------------------------------------
sys.modules["app.processing.task_management"] = MagicMock()
sys.modules["app.processing.pipeline"] = MagicMock()
sys.modules["app.services.request_handler"] = MagicMock()
sys.modules["app.utils.persistence_util"] = MagicMock()
sys.modules["app.processing.ghidra_processor"] = MagicMock()

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.api.v1.endpoints.binaries import (  # noqa: E402
    sanitize_filename,
    validate_binary_mime_type,
)
from app.database.models import User  # noqa: E402
from app.database import sql_service  # noqa: E402  # Ensure loaded for patching


def mock_get_current_user() -> User:
    """Mock current active user for testing."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )


# -----------------------------------------------------------------------
# Helper function tests
# -----------------------------------------------------------------------


class TestValidateBinaryMimeType:
    """Tests for validate_binary_mime_type helper."""

    def test_allowed_mime_type(self) -> None:
        """Test that allowed MIME types pass validation."""
        with patch("app.api.v1.endpoints.binaries.magic") as mock_magic:
            mock_magic.from_buffer.return_value = "application/x-executable"
            validate_binary_mime_type(b"\x7fELF")

    def test_disallowed_mime_type(self) -> None:
        """Test that disallowed MIME types raise HTTPException."""
        with patch("app.api.v1.endpoints.binaries.magic") as mock_magic:
            mock_magic.from_buffer.return_value = "text/plain"
            with pytest.raises(HTTPException) as exc_info:
                validate_binary_mime_type(b"hello")
            assert exc_info.value.status_code == 400

    def test_magic_detection_fails(self) -> None:
        """Test that magic detection failure raises HTTPException."""
        with patch("app.api.v1.endpoints.binaries.magic") as mock_magic:
            mock_magic.from_buffer.return_value = "inode/x-empty"
            with pytest.raises(HTTPException) as exc_info:
                validate_binary_mime_type(b"")
            assert exc_info.value.status_code == 400


class TestSanitizeFilename:
    """Tests for sanitize_filename helper."""

    def test_valid_filename(self) -> None:
        """Test that valid filenames pass through."""
        assert sanitize_filename("test.elf") == "test.elf"

    def test_empty_filename(self) -> None:
        """Test that empty filename raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("")
        assert exc_info.value.status_code == 400

    def test_path_traversal(self) -> None:
        """Test that path traversal is blocked."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_null_byte(self) -> None:
        """Test that null bytes are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("test\x00.elf")
        assert exc_info.value.status_code == 400

    def test_strips_path(self) -> None:
        """Test that path components are stripped."""
        assert sanitize_filename("/tmp/test.elf") == "test.elf"


# -----------------------------------------------------------------------
# Upload binary endpoint tests
# -----------------------------------------------------------------------


class TestUploadBinaryEndpoint:
    """Tests for post_upload_binary endpoint by calling the function directly."""

    @pytest.fixture
    def mock_binary_file(self) -> Any:
        """Create a mock binary file."""
        mock_file = MagicMock()
        mock_file.filename = "test.elf"
        mock_file.read = AsyncMock(return_value=b"\x7fELF" + b"\x00" * 100)
        return mock_file

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_success_json(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
        mock_binary_file: Any,
    ) -> None:
        """Test successful binary upload returning JSON."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_magic.from_buffer.return_value = "application/x-executable"
        mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]
        mock_os.makedirs = MagicMock()
        mock_os.chmod = MagicMock()
        mock_uuid.uuid4.return_value = MagicMock(hex="abc123")
        mock_shutil.disk_usage.return_value = MagicMock(free=1024 * 1024 * 1024)

        mock_sql_util = MagicMock()
        mock_sql_util.save_binary = AsyncMock(return_value=1)

        mock_user = mock_get_current_user()
        mock_request = MagicMock()
        mock_request.headers = {"accept": "application/json"}
        mock_bg = BackgroundTasks()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.binaries.open", mock_open()):
                with patch("app.api.v1.endpoints.binaries.capture_request_context", return_value=None):
                    with patch("app.api.v1.endpoints.binaries.templates") as mock_templates:
                        mock_templates.TemplateResponse = MagicMock
                        result = await post_upload_binary(
                            background_tasks=mock_bg,
                            request=mock_request,
                            current_user=mock_user,
                            binary_file=mock_binary_file,
                            name="test_binary",
                        )
                        assert result is not None

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_file_too_large(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
    ) -> None:
        """Test upload rejected for file exceeding max size."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 10
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_magic.from_buffer.return_value = "application/x-executable"
        mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]
        mock_shutil.disk_usage.return_value = MagicMock(free=1024 * 1024 * 1024)

        file_content = b"\x7fELF" + b"\x00" * (11 * 1024 * 1024)
        mock_file = MagicMock()
        mock_file.filename = "big.elf"
        mock_file.read = AsyncMock(return_value=file_content)

        mock_request = MagicMock()
        mock_request.headers = {"accept": "application/json"}

        mock_user = mock_get_current_user()
        mock_bg = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await post_upload_binary(
                background_tasks=mock_bg,
                request=mock_request,
                current_user=mock_user,
                binary_file=mock_file,
                name="big_binary",
            )
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_disallowed_mime(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
    ) -> None:
        """Test upload rejected for disallowed MIME type."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_magic.from_buffer.return_value = "text/plain"
        mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]

        mock_file = MagicMock()
        mock_file.filename = "readme.txt"
        mock_file.read = AsyncMock(return_value=b"hello world")

        mock_request = MagicMock()
        mock_request.headers = {"accept": "application/json"}

        mock_user = mock_get_current_user()
        mock_bg = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await post_upload_binary(
                background_tasks=mock_bg,
                request=mock_request,
                current_user=mock_user,
                binary_file=mock_file,
                name="text_file",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_insufficient_storage(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
        mock_binary_file: Any,
    ) -> None:
        """Test upload rejected when disk space is insufficient."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_magic.from_buffer.return_value = "application/x-executable"
        mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]
        mock_os.makedirs = MagicMock()
        mock_os.chmod = MagicMock()
        mock_shutil.disk_usage.return_value = MagicMock(free=0)

        mock_request = MagicMock()
        mock_request.headers = {"accept": "application/json"}

        mock_user = mock_get_current_user()
        mock_bg = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await post_upload_binary(
                background_tasks=mock_bg,
                request=mock_request,
                current_user=mock_user,
                binary_file=mock_binary_file,
                name="test",
            )
        assert exc_info.value.status_code == 507

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_no_filename(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
    ) -> None:
        """Test upload rejected when file has no filename."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_file = MagicMock()
        mock_file.filename = None
        mock_file.read = AsyncMock(return_value=b"\x7fELF")

        mock_request = MagicMock()
        mock_request.headers = {"accept": "application/json"}

        mock_user = mock_get_current_user()
        mock_bg = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await post_upload_binary(
                background_tasks=mock_bg,
                request=mock_request,
                current_user=mock_user,
                binary_file=mock_file,
                name="test",
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.binaries.get_settings")
    @patch("app.api.v1.endpoints.binaries.os")
    @patch("app.api.v1.endpoints.binaries.magic")
    @patch("app.api.v1.endpoints.binaries.shutil")
    @patch("app.api.v1.endpoints.binaries.uuid")
    @patch("app.api.v1.endpoints.binaries.TaskManager")
    async def test_upload_binary_html_response(
        self,
        mock_task_manager: Any,
        mock_uuid: Any,
        mock_shutil: Any,
        mock_magic: Any,
        mock_os: Any,
        mock_get_settings: Any,
        mock_binary_file: Any,
    ) -> None:
        """Test binary upload returns HTML TemplateResponse for browser requests."""
        from fastapi import BackgroundTasks

        from app.api.v1.endpoints.binaries import post_upload_binary

        mock_settings = Mock()
        mock_settings.max_file_size_mb = 100
        mock_settings.upload_folder = "/tmp/uploads"
        mock_get_settings.return_value = mock_settings

        mock_magic.from_buffer.return_value = "application/x-executable"
        mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]
        mock_os.makedirs = MagicMock()
        mock_os.chmod = MagicMock()
        mock_uuid.uuid4.return_value = MagicMock(hex="abc123")
        mock_shutil.disk_usage.return_value = MagicMock(free=1024 * 1024 * 1024)

        mock_sql_util = MagicMock()
        mock_sql_util.save_binary = AsyncMock(return_value=1)

        mock_user = mock_get_current_user()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "text/html"
        mock_bg = BackgroundTasks()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.binaries.open", mock_open()):
                with patch("app.api.v1.endpoints.binaries.capture_request_context", return_value=None):
                    with patch("app.api.v1.endpoints.binaries.templates") as mock_templates:
                        mock_templates.TemplateResponse = Mock(return_value=Mock())
                        result = await post_upload_binary(
                            background_tasks=mock_bg,
                            request=mock_request,
                            current_user=mock_user,
                            binary_file=mock_binary_file,
                            name="test_binary",
                        )
                        mock_templates.TemplateResponse.assert_called_once()


# -----------------------------------------------------------------------
# List binaries endpoint tests
# -----------------------------------------------------------------------


class TestListBinariesEndpoint:
    """Tests for list_binaries endpoint."""

    @pytest.mark.asyncio
    async def test_list_binaries_success(self) -> None:
        """Test listing binaries successfully."""
        from app.api.v1.endpoints.binaries import list_binaries

        mock_binary = MagicMock()
        mock_binary.id = 1
        mock_binary.name = "test.elf"
        mock_binary.file_size = 1024
        mock_binary.mime_type = "application/x-executable"
        mock_binary.created_at = MagicMock()
        mock_binary.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binaries_by_user = AsyncMock(return_value=[mock_binary])
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[MagicMock()])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_binaries(current_user=mock_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_list_binaries_empty(self) -> None:
        """Test listing binaries returns empty list when user has no binaries."""
        from app.api.v1.endpoints.binaries import list_binaries

        mock_sql_util = MagicMock()
        mock_sql_util.get_binaries_by_user = AsyncMock(return_value=[])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_binaries(current_user=mock_user)
            assert result is not None


# -----------------------------------------------------------------------
# list_bins endpoint tests
# -----------------------------------------------------------------------


class TestListBinsEndpoint:
    """Tests for list_bins endpoint."""

    @pytest.mark.asyncio
    async def test_list_bins_success(self) -> None:
        """Test list_bins returns binary dict successfully."""
        from app.api.v1.endpoints.binaries import list_bins

        mock_binary = MagicMock()
        mock_binary.id = 1
        mock_binary.name = "test.elf"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binaries_by_user = AsyncMock(return_value=[mock_binary])
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[MagicMock()])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_bins(current_user=mock_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_list_bins_empty(self) -> None:
        """Test list_bins returns empty dict when no binaries."""
        from app.api.v1.endpoints.binaries import list_bins

        mock_sql_util = MagicMock()
        mock_sql_util.get_binaries_by_user = AsyncMock(return_value=[])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_bins(current_user=mock_user)
            assert result is not None


# -----------------------------------------------------------------------
# Binary detail endpoint tests
# -----------------------------------------------------------------------


class TestBinaryDetailEndpoint:
    """Tests for get_binary_detail endpoint."""

    @pytest.mark.asyncio
    async def test_get_binary_detail_success(self) -> None:
        """Test getting binary detail returns successfully."""
        from app.api.v1.endpoints.binaries import get_binary_detail

        mock_binary = MagicMock()
        mock_binary.id = 1
        mock_binary.name = "test.elf"
        mock_binary.file_size = 1024
        mock_binary.mime_type = "application/x-executable"
        mock_binary.user_id = 1
        mock_binary.uploaded_by = 1
        mock_binary.created_at = MagicMock()
        mock_binary.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        mock_binary.modified_at = MagicMock()
        mock_binary.modified_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[MagicMock()])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await get_binary_detail(binary_id=1, current_user=mock_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_binary_detail_not_found(self) -> None:
        """Test getting binary detail returns 404 when not found."""
        from app.api.v1.endpoints.binaries import get_binary_detail

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=None)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await get_binary_detail(binary_id=999, current_user=mock_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_binary_detail_access_denied(self) -> None:
        """Test getting binary detail returns 403 for other user's binary."""
        from app.api.v1.endpoints.binaries import get_binary_detail

        mock_binary = MagicMock()
        mock_binary.user_id = 999

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await get_binary_detail(binary_id=1, current_user=mock_user)
            assert exc_info.value.status_code == 403


# -----------------------------------------------------------------------
# List binary functions endpoint tests
# -----------------------------------------------------------------------


class TestListBinaryFunctionsEndpoint:
    """Tests for list_binary_functions endpoint."""

    @pytest.mark.asyncio
    async def test_list_binary_functions_success(self) -> None:
        """Test listing binary functions returns successfully."""
        from app.api.v1.endpoints.binaries import list_binary_functions

        mock_binary = MagicMock()
        mock_binary.user_id = 1
        mock_binary.uploaded_by = 1

        mock_func = MagicMock()
        mock_func.id = 1
        mock_func.name = "main"
        mock_func.function_name = "main"
        mock_func.entrypoint = "0x401000"
        mock_func.raw_code = "int main() {\n    return 0;\n}"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_func])

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_binary_functions(binary_id=1, current_user=mock_user)
            assert result is not None

    @pytest.mark.asyncio
    async def test_list_binary_functions_not_found(self) -> None:
        """Test listing functions returns 404 when binary not found."""
        from app.api.v1.endpoints.binaries import list_binary_functions

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=None)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await list_binary_functions(binary_id=999, current_user=mock_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_binary_functions_access_denied(self) -> None:
        """Test listing functions returns 403 for other user's binary."""
        from app.api.v1.endpoints.binaries import list_binary_functions

        mock_binary = MagicMock()
        mock_binary.user_id = 999

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await list_binary_functions(binary_id=1, current_user=mock_user)
            assert exc_info.value.status_code == 403


# -----------------------------------------------------------------------
# Delete binary endpoint tests
# -----------------------------------------------------------------------


class TestDeleteBinaryEndpoint:
    """Tests for delete_binary endpoint."""

    @pytest.mark.asyncio
    async def test_delete_binary_success(self) -> None:
        """Test deleting binary succeeds."""
        from app.api.v1.endpoints.binaries import delete_binary

        mock_binary = MagicMock()
        mock_binary.user_id = 1
        mock_binary.uploaded_by = 1

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)
        mock_sql_util.delete_binary = AsyncMock(return_value=None)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.binaries.os") as mock_os:
                mock_os.path.join = lambda *a: "/".join(str(x) for x in a)  # type: ignore[assignment]
                mock_os.remove = MagicMock()
                result = await delete_binary(binary_id=1, current_user=mock_user)
                assert result is not None

    @pytest.mark.asyncio
    async def test_delete_binary_not_found(self) -> None:
        """Test deleting binary returns 404 when not found."""
        from app.api.v1.endpoints.binaries import delete_binary

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=None)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await delete_binary(binary_id=999, current_user=mock_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_binary_access_denied(self) -> None:
        """Test deleting binary returns 403 for other user's binary."""
        from app.api.v1.endpoints.binaries import delete_binary

        mock_binary = MagicMock()
        mock_binary.user_id = 999

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        mock_user = mock_get_current_user()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await delete_binary(binary_id=1, current_user=mock_user)
            assert exc_info.value.status_code == 403


# -----------------------------------------------------------------------
# Upload pipeline background task tests
# -----------------------------------------------------------------------


class TestUploadPipeline:
    """Tests for _run_upload_pipeline background task.

    Signature: _run_upload_pipeline(binary_id, file_path, task_uuid, captured_ctx=None)
    """

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_upload_pipeline_success(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test upload pipeline completes successfully."""
        from app.api.v1.endpoints.binaries import _run_upload_pipeline

        mock_result = MagicMock()
        mock_result.error = None
        mock_result.get = MagicMock(return_value=5)

        mock_execute = AsyncMock(return_value=mock_result)
        mock_instance = MagicMock()
        mock_instance.execute = mock_execute

        with patch.dict("sys.modules", {"app.processing.steps": MagicMock()}):
            mock_pipeline = sys.modules["app.processing.pipeline"]
            mock_pipeline.ProcessingPipeline.return_value = mock_instance

            await _run_upload_pipeline(
                binary_id=1,
                file_path="/tmp/test.elf",
                task_uuid="abc-123",
            )

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_upload_pipeline_error_result(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test upload pipeline handles pipeline error result."""
        from app.api.v1.endpoints.binaries import _run_upload_pipeline

        mock_result = MagicMock()
        mock_result.error = "Something failed"
        mock_result.exc_info = (RuntimeError, RuntimeError("fail"), None)

        mock_execute = AsyncMock(return_value=mock_result)
        mock_instance = MagicMock()
        mock_instance.execute = mock_execute

        with patch.dict("sys.modules", {"app.processing.steps": MagicMock()}):
            mock_pipeline = sys.modules["app.processing.pipeline"]
            mock_pipeline.ProcessingPipeline.return_value = mock_instance

            await _run_upload_pipeline(
                binary_id=1,
                file_path="/tmp/test.elf",
                task_uuid="abc-123",
            )

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_upload_pipeline_exception(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test upload pipeline handles unexpected exceptions."""
        from app.api.v1.endpoints.binaries import _run_upload_pipeline

        mock_instance = MagicMock()
        mock_instance.execute = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with patch.dict("sys.modules", {"app.processing.steps": MagicMock()}):
            mock_pipeline = sys.modules["app.processing.pipeline"]
            mock_pipeline.ProcessingPipeline.return_value = mock_instance

            with pytest.raises(RuntimeError):
                await _run_upload_pipeline(
                    binary_id=1,
                    file_path="/nonexistent.elf",
                    task_uuid="abc-123",
                )

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_upload_pipeline_with_context(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test upload pipeline with captured request context."""
        from app.api.v1.endpoints.binaries import _run_upload_pipeline

        mock_ctx = MagicMock()

        mock_result = MagicMock()
        mock_result.error = None
        mock_result.get = MagicMock(return_value=3)

        mock_execute = AsyncMock(return_value=mock_result)
        mock_instance = MagicMock()
        mock_instance.execute = mock_execute

        with patch("app.api.v1.endpoints.binaries.restore_request_context") as mock_restore:
            with patch.dict("sys.modules", {"app.processing.steps": MagicMock()}):
                mock_pipeline = sys.modules["app.processing.pipeline"]
                mock_pipeline.ProcessingPipeline.return_value = mock_instance

                await _run_upload_pipeline(
                    binary_id=1,
                    file_path="/tmp/test.elf",
                    task_uuid="abc-123",
                    captured_ctx=mock_ctx,
                )
                mock_restore.assert_called_once()


# -----------------------------------------------------------------------
# Pipeline analysis background task tests
# -----------------------------------------------------------------------


class TestPipelineAnalysis:
    """Tests for _run_pipeline_analysis background task.

    Signature: _run_pipeline_analysis(ghidra_request, file_path, captured_ctx=None)
    """

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_training_success(
        self, mock_clear: Any, mock_tm: Any
    ) -> None:
        """Test training pipeline completes successfully."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.file_name = "test.elf"
        mock_ghidra_request.model_name = "test_model"
        mock_ghidra_request.is_training = True

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.get = MagicMock(side_effect=lambda k, d=None: {
                "filtered_functions": [{"name": "main"}],
                "errored_functions": [],
            }.get(k, d))

            mock_run = AsyncMock(return_value=mock_result)
            mock_ghidra.run_full_pipeline = mock_run

            mock_persist = sys.modules["app.utils.persistence_util"].FunctionPersistanceUtil
            mock_persist.add_model_functions = AsyncMock()
            await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_prediction_success(
        self, mock_clear: Any, mock_tm: Any
    ) -> None:
        """Test prediction pipeline completes successfully."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.file_name = "test.elf"
        mock_ghidra_request.model_name = "test_model"
        mock_ghidra_request.is_training = False

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.get = MagicMock(side_effect=lambda k, d=None: {
                "predictions": [{"name": "main", "prediction": "safe"}],
                "filtered_functions": [{"name": "main"}],
                "errored_functions": [],
            }.get(k, d))

            mock_run = AsyncMock(return_value=mock_result)
            mock_ghidra.run_full_pipeline = mock_run

            mock_persist = sys.modules["app.utils.persistence_util"].FunctionPersistanceUtil
            mock_persist.add_prediction_functions = AsyncMock()
            await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_error_result(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test pipeline analysis handles error result."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.is_training = True

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_result = MagicMock()
            mock_result.error = "Pipeline failed"
            mock_result.exc_info = (RuntimeError, RuntimeError("fail"), None)

            mock_run = AsyncMock(return_value=mock_result)
            mock_ghidra.run_full_pipeline = mock_run

            await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_exception(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test pipeline analysis handles unexpected exceptions."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.is_training = True

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_ghidra.run_full_pipeline = AsyncMock(side_effect=RuntimeError("Unexpected"))

            with pytest.raises(RuntimeError):
                await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_training_no_functions(
        self, mock_clear: Any, mock_tm: Any
    ) -> None:
        """Test training pipeline when no functions extracted."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.is_training = True

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.get = MagicMock(return_value=None)

            mock_run = AsyncMock(return_value=mock_result)
            mock_ghidra.run_full_pipeline = mock_run

            await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_prediction_empty(
        self, mock_clear: Any, mock_tm: Any
    ) -> None:
        """Test prediction pipeline when no predictions."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.is_training = False

        with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
            mock_result = MagicMock()
            mock_result.error = None
            mock_result.get = MagicMock(return_value=None)

            mock_run = AsyncMock(return_value=mock_result)
            mock_ghidra.run_full_pipeline = mock_run

            await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf")

    @patch("app.api.v1.endpoints.binaries.TaskManager")
    @patch("app.api.v1.endpoints.binaries.clear_request_context")
    async def test_run_pipeline_analysis_with_context(self, mock_clear: Any, mock_tm: Any) -> None:
        """Test pipeline analysis with captured request context."""
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis

        mock_ghidra_request = MagicMock()
        mock_ghidra_request.uuid = "abc-123"
        mock_ghidra_request.is_training = True

        mock_ctx = MagicMock()

        with patch("app.api.v1.endpoints.binaries.restore_request_context") as mock_restore:
            with patch("app.api.v1.endpoints.binaries.Ghidra") as mock_ghidra:
                mock_result = MagicMock()
                mock_result.error = None
                mock_result.get = MagicMock(return_value=None)

                mock_run = AsyncMock(return_value=mock_result)
                mock_ghidra.run_full_pipeline = mock_run

                await _run_pipeline_analysis(mock_ghidra_request, "/tmp/test.elf", captured_ctx=mock_ctx)
                mock_restore.assert_called_once()
