"""Test to verify upload endpoint enforces authentication."""
import io
import pytest
from fastapi.testclient import TestClient
from typing import Generator, Any


@pytest.fixture
def auth_client() -> Generator[TestClient, Any, Any]:
    from main import app
    with TestClient(app) as client:
        yield client


def test_upload_without_auth_rejected(auth_client: TestClient) -> None:
    """Verify that uploading without authentication returns 401."""
    # Create minimal ELF-like binary content
    elf_content = b'\x7fELF' + b'\x00' * 100
    files = {
        'binary_file': ('test.bin', io.BytesIO(elf_content), 'application/octet-stream')
    }
    data = {'name': 'test_binary'}
    response = auth_client.post(
        '/api/v1/binaries/uploadBinary',
        files=files,
        data=data,
        headers={'Accept': 'application/json'}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code} - auth is NOT enforced!"
