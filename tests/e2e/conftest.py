# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright test configuration and fixtures for Glyph application.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
import requests

# Project root is two levels up from tests/e2e/
PROJECT_ROOT = Path(__file__).parent.parent.parent

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
    # Point the application's per-purpose SQLite databases at a clean,
    # session-scoped temp directory so state (uploaded binaries, scan
    # reports, LLM results) does not leak between test runs or pollute the
    # real data/ directory.
    data_dir = tempfile.mkdtemp(prefix="glyph_e2e_data_")
    env = os.environ.copy()
    env["GLYPH_JWT_SECRET_KEY"] = "test-secret-key-for-playwright-testing"
    env["GLYPH_DATA_DIR"] = data_dir
    # Set generous rate limits for testing (100 requests per 60 seconds)
    env["GLYPH_RATE_LIMIT_LOGIN_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_LOGIN_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_REGISTER_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_REGISTER_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_REFRESH_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_REFRESH_WINDOW"] = "60"

    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=PROJECT_ROOT,
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
        # Clean up the temp data directory (databases) used by the server
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for the application."""
    return BASE_URL


@pytest.fixture()
def page(base_url: str, page: Any, server: Any) -> Any:  # pyright: ignore[reportRedeclaration]
    """Extend the default page fixture to ensure server is running."""
    return page
