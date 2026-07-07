"""Test to verify upload endpoint enforces authentication.

Uses a minimal FastAPI app with only the v1 router to avoid loading
the full application (reduces test startup time and dependencies).
"""

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client() -> TestClient:
    """Create a minimal TestClient with the v1 API router included.

    Avoids importing the full app from main.py, which is slow and pulls
    in heavy dependencies (Ghidra, ML models, etc.).
    """
    from app.api.router import api_v1_router
    from app.auth.dependencies import get_db

    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api")

    # Override get_db to avoid needing real DB initialization.
    # The 401 is raised in get_current_user before the DB session is used,
    # so a mock dependency is sufficient for auth-rejection tests.
    async def _mock_db():
        yield None

    app.dependency_overrides[get_db] = _mock_db

    return TestClient(app)


def test_upload_without_auth_rejected(auth_client: TestClient) -> None:
    """Verify that uploading without authentication returns 401."""
    # Create minimal ELF-like binary content
    elf_content = b"\x7fELF" + b"\x00" * 100
    files = {
        "binary_file": (
            "test.bin",
            io.BytesIO(elf_content),
            "application/octet-stream",
        ),
    }
    data = {"name": "test_binary"}
    response = auth_client.post(
        "/api/v1/binaries/uploadBinary",
        files=files,
        data=data,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 401, (
        f"Expected 401 (unauthorized), got {response.status_code} - auth is NOT enforced!"
    )
