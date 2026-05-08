# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright test configuration and fixtures for Glyph application.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

import sys
import subprocess
import time
import os
import pytest
import requests
from typing import Any

# Base URL for the application
BASE_URL = "http://127.0.0.1:8000"


def wait_for_server(url: str, timeout: int = 60) -> None:
    """Wait for the server to be ready and responding."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                return
        except requests.ConnectionError:
            time.sleep(1)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def server() -> Any:
    """Start the FastAPI server for testing and stop it after all tests complete."""
    env = os.environ.copy()
    env["GLYPH_JWT_SECRET_KEY"] = "test-secret-key-for-playwright-testing"
    env["GLYPH_DATABASE_URL"] = "sqlite+aiosqlite:///./test_playwright.db"
    
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd="/workspaces/Glyph",
        env=env,
    )
    try:
        wait_for_server(BASE_URL)
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        # Clean up test database
        db_path = "/workspaces/Glyph/test_playwright.db"
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for the application."""
    return BASE_URL


@pytest.fixture()
def page(base_url: str, page: Any, server: Any) -> Any:  # pyright: ignore[reportRedeclaration]
    """Extend the default page fixture to ensure server is running."""
    return page
