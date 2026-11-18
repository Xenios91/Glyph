"""Endpoint tests for the remaining binaries API endpoints.

Covers the bulk upload limit/name parsing, the legacy disk-listing endpoint,
and the single-upload happy path (task registration + background queueing).
"""

import io
import uuid as uuid_module
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from tests.conftest import create_app_client
from tests.factories import make_user


def _client(user: Any) -> Any:
    from app.api.v1.endpoints import binaries
    from app.auth.dependencies import get_current_active_user

    return create_app_client(
        routers=[(binaries.router, "")],
        dependency_overrides={get_current_active_user: lambda: user},
    )


class _FakeBinary:
    """Minimal stand-in for a Binary ORM row (only fields list_bins uses)."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path


class TestUploadBulk:
    """Tests for POST /uploadBulk."""

    @pytest.fixture
    def owner(self) -> Any:
        return make_user(user_id=1, username="owner")

    @staticmethod
    def _multipart_files(count: int) -> list[tuple[str, tuple[str, bytes, str]]]:
        return [
            ("files", (f"file{i}.elf", b"\x7fELF", "application/octet-stream")) for i in range(count)
        ]

    def test_upload_bulk_over_limit_rejected(self, owner: Any) -> None:
        """More than 20 files should be rejected with 400 TOO_MANY_FILES."""
        client = _client(owner)
        response = client.post(
            "/uploadBulk",
            files=self._multipart_files(21),
            data={"names": ",".join(f"n{i}" for i in range(21))},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"]["code"] == "TOO_MANY_FILES"

    def test_upload_bulk_exactly_20_allowed(self, owner: Any) -> None:
        """Exactly 20 files is the boundary and must be accepted."""
        from app.api.v1.endpoints import binaries
        from app.api.v1.endpoints.binaries import BulkUploadItem

        client = _client(owner)
        with patch.object(
            binaries,
            "_upload_single_binary",
            new=AsyncMock(return_value=BulkUploadItem(name="x", status="success")),
        ):
            response = client.post(
                "/uploadBulk",
                files=self._multipart_files(20),
                data={"names": ",".join(f"n{i}" for i in range(20))},
            )

        assert response.status_code == 200
        assert response.json()["data"]["total"] == 20

    def test_upload_bulk_name_parsing(self, owner: Any) -> None:
        """Comma-separated names are stripped; empty entries are skipped."""
        from app.api.v1.endpoints import binaries
        from app.api.v1.endpoints.binaries import BulkUploadItem

        client = _client(owner)
        mock_single = AsyncMock(return_value=BulkUploadItem(name="x", status="success"))
        with patch.object(binaries, "_upload_single_binary", new=mock_single):
            response = client.post(
                "/uploadBulk",
                files=self._multipart_files(2),
                data={"names": "  alpha  ,, beta "},
            )

        assert response.status_code == 200
        # The endpoint receives UploadFile objects; pull the resolved names from
        # the per-file calls (second positional argument).
        names = [call.args[1] for call in mock_single.call_args_list]
        assert names == ["alpha", "beta"]

    def test_upload_bulk_fewer_names_falls_back_to_filename(self, owner: Any) -> None:
        """When fewer names than files, the missing names use the filenames."""
        from app.api.v1.endpoints import binaries
        from app.api.v1.endpoints.binaries import BulkUploadItem

        client = _client(owner)
        mock_single = AsyncMock(return_value=BulkUploadItem(name="x", status="success"))
        with patch.object(binaries, "_upload_single_binary", new=mock_single):
            response = client.post(
                "/uploadBulk",
                files=self._multipart_files(2),
                data={"names": "alpha"},
            )

        assert response.status_code == 200
        names = [call.args[1] for call in mock_single.call_args_list]
        assert names == ["alpha", "file1.elf"]

    def test_upload_bulk_summary_counts(self, owner: Any) -> None:
        """The response summary counts successful and failed items."""
        from app.api.v1.endpoints import binaries
        from app.api.v1.endpoints.binaries import BulkUploadItem

        client = _client(owner)
        results = [
            BulkUploadItem(binary_id=1, uuid="u1", name="ok", status="success"),
            BulkUploadItem(name="bad", status="error", error="No filename provided"),
        ]
        with patch.object(binaries, "_upload_single_binary", new=AsyncMock(side_effect=results)):
            response = client.post(
                "/uploadBulk",
                files=self._multipart_files(2),
                data={"names": "ok,bad"},
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2
        assert data["successful"] == 1
        assert data["failed"] == 1


class TestListBins:
    """Tests for GET /listBins (legacy disk listing)."""

    @pytest.fixture
    def owner(self) -> Any:
        return make_user(user_id=1, username="owner")

    def test_list_bins_returns_disk_list(self, owner: Any, tmp_path: Any) -> None:
        """Only files that exist on disk are returned, as bare basenames."""
        from app.api.v1.endpoints import binaries

        existing = tmp_path / "a.elf"
        existing.write_bytes(b"\x7fELF")
        existing2 = tmp_path / "b.elf"
        existing2.write_bytes(b"\x7fELF")

        binaries._upload_service.list_binaries = AsyncMock(
            return_value=(
                [
                    _FakeBinary(str(existing)),
                    _FakeBinary(str(existing2)),
                    _FakeBinary(str(tmp_path / "gone.elf")),  # missing on disk
                ],
                3,
            )
        )

        client = _client(owner)
        response = client.get("/listBins")

        assert response.status_code == 200
        assert response.json()["data"]["files"] == ["a.elf", "b.elf"]
        # The service is scoped to the current user.
        binaries._upload_service.list_binaries.assert_awaited_once_with(
            user_id=owner.id, offset=0, limit=1000
        )

    def test_list_bins_empty(self, owner: Any) -> None:
        """No binaries yields an empty file list."""
        from app.api.v1.endpoints import binaries

        binaries._upload_service.list_binaries = AsyncMock(return_value=([], 0))

        client = _client(owner)
        response = client.get("/listBins")

        assert response.status_code == 200
        assert response.json()["data"]["files"] == []


class TestUploadBinaryHappyPath:
    """Tests for POST /uploadBinary (single upload happy path)."""

    @pytest.fixture
    def owner(self) -> Any:
        return make_user(user_id=1, username="owner")

    def test_upload_binary_happy_path_registers_task(self, owner: Any) -> None:
        """A successful upload registers a task and queues the pipeline."""
        from app.api.v1.endpoints import binaries

        client = _client(owner)
        pipeline_calls: list[tuple[Any, ...]] = []

        async def _fake_pipeline(binary_id: Any, file_path: Any, task_uuid: Any, ctx: Any) -> None:
            pipeline_calls.append((binary_id, file_path, task_uuid, ctx))

        with (
            patch.object(
                binaries._upload_service,
                "upload_binary",
                new=AsyncMock(return_value=(7, "/uploads/test.elf")),
            ),
            patch.object(binaries.TaskManager, "register_task") as mock_register,
            patch.object(binaries, "_run_upload_pipeline", new=_fake_pipeline),
        ):
            response = client.post(
                "/uploadBinary",
                files={"binary_file": ("test.elf", io.BytesIO(b"\x7fELF"), "application/octet-stream")},
                data={"name": "testbin"},
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["binary_id"] == 7

        task_uuid = data["uuid"]
        uuid_module.UUID(task_uuid)  # must be a valid UUID

        mock_register.assert_called_once_with(task_uuid, "starting", owner_id=owner.id)
        # The background pipeline ran after the response, with the captured context.
        assert len(pipeline_calls) == 1
        assert pipeline_calls[0][:3] == (7, "/uploads/test.elf", task_uuid)
        assert pipeline_calls[0][3] is not None

    async def test_upload_binary_no_filename_rejected(self, owner: Any) -> None:
        """An upload without a filename should return 400 NO_FILE_FOUND."""
        from app.api.v1.endpoints import binaries
        from fastapi import HTTPException

        file = UploadFile(file=io.BytesIO(b"\x7fELF"), filename=None)
        file.filename = None

        with patch.object(binaries._upload_service, "upload_binary", new=AsyncMock()) as mock_upload:
            with pytest.raises(HTTPException) as exc_info:
                await binaries.post_upload_binary(
                    background_tasks=MagicMock(),
                    current_user=owner,
                    binary_file=file,
                    name="testbin",
                )

        assert exc_info.value.status_code == 400
        assert "NO_FILE_FOUND" in str(exc_info.value.detail)
        mock_upload.assert_not_awaited()
