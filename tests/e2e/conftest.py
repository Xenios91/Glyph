# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright test configuration and fixtures for Glyph application.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

import os
import shutil
import socket
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

# E2E tests drive full browser flows (registration, upload, scan) and are
# much slower than unit tests; the global 30s pytest-timeout would abort the
# whole session on the first slow test.
E2E_TIMEOUT_SECONDS = 300


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Relax the global pytest-timeout for the long-running e2e suite.

    The project-wide ``timeout = 30`` (pyproject.toml) is appropriate for
    unit tests but too aggressive for browser-driven tests: a single slow
    test would kill the entire session. Markers take precedence over the
    ini value in pytest-timeout, so tag every e2e item with a generous
    timeout and the signal-based method, which reliably interrupts hung
    Playwright calls (the thread method can leave the event loop wedged).
    """
    for item in items:
        item.add_marker(pytest.mark.timeout(E2E_TIMEOUT_SECONDS, method="signal"))


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


def _port_in_use(host: str, port: int) -> bool:
    """Return True when something is already listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def server() -> Any:
    """Start the FastAPI server for testing and stop it after all tests complete."""
    # Fail fast if something else (e.g. a stale dev server or a previous
    # aborted run) already owns the port: wait_for_server would otherwise
    # succeed against the foreign server and every test would silently hit
    # the wrong application state.
    if _port_in_use("127.0.0.1", 8000):
        raise RuntimeError(
            "Port 8000 is already in use; stop the other process "
            "(e.g. a leftover 'python main.py' server) and re-run the e2e suite."
        )

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
