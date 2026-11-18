# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright test configuration and fixtures for Glyph application.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

import os
import re
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

# Temp data directory for the session server. Populated by the `server`
# fixture and exposed via the `data_dir` fixture so tests can seed or
# inspect the SQLite databases directly.
_e2e_data_dir: str | None = None

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

    Every item is also tagged with the registered ``e2e`` marker so the
    suite can be selected or deselected via ``-m`` (e.g. ``-m "not e2e"``).
    """
    for item in items:
        item.add_marker(pytest.mark.e2e)
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
    global _e2e_data_dir
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
    _e2e_data_dir = data_dir
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


@pytest.fixture()
def start_dedicated_server(request: Any):
    """Factory fixture that starts a dedicated FastAPI server on a free port.

    Some tests need a non-default configuration (a tiny ``max_file_size_mb``,
    a strict rate-limit window, ...) that would break the shared session
    server. Each call starts an isolated server process in its own temp
    working directory and returns ``(process, base_url)``. The server is torn
    down automatically when the calling test finishes (via
    ``request.addfinalizer``).

    Why a temp working directory: the app resolves ``config.yml``,
    ``templates/`` and ``static/`` relative to the CWD, and
    ``settings_customise_sources`` gives ``config.yml`` priority *over*
    environment variables. So to override a YAML-backed setting (e.g.
    ``max_file_size_mb``) we must run the server from a directory whose
    ``config.yml`` carries the value we want. ``templates/`` and ``static/``
    are symlinked in so the UI keeps working.

    Args:
        env_overrides: optional ``GLYPH_`` env var overrides (rate limits,
            JWT secret, ...).
        max_file_size_mb: if given, the temp ``config.yml`` is rewritten so
            ``max_file_size_mb`` takes this value (env vars alone cannot
            override it because of the YAML source priority).

    The returned ``base_url`` uses a dynamically chosen free port, so these
    servers never collide with the shared port-8000 server (and do not start
    it: callers must use the ``browser`` fixture + their own context rather
    than the conftest ``page`` fixture, which would pull in the shared server).

    Example:
        def test_x(browser, start_dedicated_server):
            _, base_url = start_dedicated_server(max_file_size_mb=1)
    """

    def _start(
        env_overrides: dict[str, str] | None = None,
        *,
        max_file_size_mb: int | None = None,
    ) -> tuple[Any, str]:
        # Grab a free port by binding to port 0 and asking the OS.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        work_dir = tempfile.mkdtemp(prefix="glyph_e2e_dedicated_")
        for name in ("templates", "static"):
            os.symlink(PROJECT_ROOT / name, os.path.join(work_dir, name))

        # Build a temp config.yml. The YAML source outranks env vars, so a
        # YAML-backed override (max_file_size_mb) must go in the file itself.
        config_text = (PROJECT_ROOT / "config.yml").read_text(encoding="utf-8")
        if max_file_size_mb is not None:
            config_text = re.sub(
                r"(?m)^max_file_size_mb:.*$",
                f"max_file_size_mb: {max_file_size_mb}",
                config_text,
            )
        with open(os.path.join(work_dir, "config.yml"), "w", encoding="utf-8") as fh:
            fh.write(config_text)

        data_dir = os.path.join(work_dir, "data")
        os.makedirs(data_dir, exist_ok=True)

        env = os.environ.copy()
        env["GLYPH_JWT_SECRET_KEY"] = "test-secret-key-for-playwright-testing"
        env["GLYPH_DATA_DIR"] = data_dir
        env["GLYPH_HOST"] = "127.0.0.1"
        env["GLYPH_PORT"] = str(port)
        # Generous defaults so only the overrides the test cares about are
        # tight; everything else stays permissive. Set explicitly (not
        # setdefault) so a stray GLYPH_* var in the parent shell can't leak in.
        env["GLYPH_RATE_LIMIT_LOGIN_MAX"] = "100"
        env["GLYPH_RATE_LIMIT_LOGIN_WINDOW"] = "60"
        env["GLYPH_RATE_LIMIT_REGISTER_MAX"] = "100"
        env["GLYPH_RATE_LIMIT_REGISTER_WINDOW"] = "60"
        env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX"] = "100"
        env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW"] = "60"
        env["GLYPH_RATE_LIMIT_REFRESH_MAX"] = "100"
        env["GLYPH_RATE_LIMIT_REFRESH_WINDOW"] = "60"
        if env_overrides:
            env.update(env_overrides)

        process = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "main.py")],
            cwd=work_dir,
            env=env,
        )
        base_url = f"http://127.0.0.1:{port}"

        def _teardown() -> None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            shutil.rmtree(work_dir, ignore_errors=True)

        try:
            wait_for_server(base_url)
        except Exception:
            _teardown()
            raise

        # Tear the server down when the calling test finishes, even on failure.
        request.addfinalizer(_teardown)
        return process, base_url

    return _start


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for the application."""
    return BASE_URL


@pytest.fixture(scope="session")
def data_dir(server: Any) -> str:
    """Return the temp data directory backing the e2e server's SQLite DBs."""
    assert _e2e_data_dir is not None, "server fixture has not started yet"
    return _e2e_data_dir


@pytest.fixture(scope="session")
def browser_type_launch_args(  # pyright: ignore[reportRedeclaration]
    browser_type_launch_args: dict,
) -> dict:
    """Allow overriding the browser executable via ``PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH``.

    Playwright's bundled Chromium requires a newer glibc than some local
    dev/CI images provide (e.g. Debian 11 / glibc 2.31). When the bundled
    browser cannot be installed or launched, point this env var at a
    system-installed Chromium/Chrome binary and Playwright will drive it
    instead. CI (ubuntu-latest) leaves the var unset and uses the bundled
    browser, so this is a no-op there.
    """
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if executable:
        browser_type_launch_args["executable_path"] = executable
    return browser_type_launch_args


@pytest.fixture()
def page(base_url: str, page: Any, server: Any) -> Any:  # pyright: ignore[reportRedeclaration]
    """Extend the default page fixture to ensure server is running."""
    return page
