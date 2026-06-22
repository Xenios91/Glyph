import glob
import os
import sys
from typing import Any
from unittest import mock

# Set generous rate limits for tests BEFORE any app imports.
# This ensures rate_limiter.py picks up these values at module load time.
os.environ.setdefault("GLYPH_RATE_LIMIT_LOGIN_MAX", "1000")
os.environ.setdefault("GLYPH_RATE_LIMIT_LOGIN_WINDOW", "60")
os.environ.setdefault("GLYPH_RATE_LIMIT_REGISTER_MAX", "1000")
os.environ.setdefault("GLYPH_RATE_LIMIT_REGISTER_WINDOW", "60")
os.environ.setdefault("GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX", "1000")
os.environ.setdefault("GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW", "60")
os.environ.setdefault("GLYPH_RATE_LIMIT_REFRESH_MAX", "1000")
os.environ.setdefault("GLYPH_RATE_LIMIT_REFRESH_WINDOW", "60")

import pytest


# In-memory database URL templates for testing.
# Each database uses a unique URI so they remain separate in-memory databases.
# When running under pytest-xdist, the worker ID is included in the URI to avoid
# cross-worker conflicts with shared-cache SQLite databases.
_IN_MEMORY_DATABASE_TEMPLATES: dict[str, str] = {
    "models": "sqlite+aiosqlite:///file:mem_models{worker}?mode=memory&cache=shared",
    "predictions": "sqlite+aiosqlite:///file:mem_predictions{worker}?mode=memory&cache=shared",
    "functions": "sqlite+aiosqlite:///file:mem_functions{worker}?mode=memory&cache=shared",
    "auth": "sqlite+aiosqlite:///file:mem_auth{worker}?mode=memory&cache=shared",
    "binaries": "sqlite+aiosqlite:///file:mem_binaries{worker}?mode=memory&cache=shared",
    "intelligence": "sqlite+aiosqlite:///file:mem_intelligence{worker}?mode=memory&cache=shared",
}


def _cleanup_sqlite_files() -> None:
    """Remove SQLite shared-cache files created by in-memory database URIs.

    SQLite's file:mem_*?mode=memory&cache=shared URIs with StaticPool create
    physical files on disk named 'file:mem_*'. Clean them up after tests.
    """
    pattern = os.path.join(os.getcwd(), "file:mem_*")
    for filepath in glob.glob(pattern):
        try:
            os.remove(filepath)
        except OSError:
            pass


def pytest_unconfigure(config: Any) -> None:
    """Clean up SQLite files after all tests complete."""
    _cleanup_sqlite_files()


def _build_database_urls() -> dict[str, str]:
    """Build worker-aware in-memory database URLs.

    When running under pytest-xdist, each worker gets its own set of in-memory
    databases to avoid cross-worker table conflicts with shared-cache SQLite.
    The worker ID is read from the PYTEST_XDIST_WORKER environment variable,
    which is set automatically by pytest-xdist for each worker process.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "")
    worker_suffix = f"_{worker_id}" if worker_id else ""
    return {k: v.format(worker=worker_suffix) for k, v in _IN_MEMORY_DATABASE_TEMPLATES.items()}


def pytest_configure(config: Any) -> None:
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules: list[str] = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra",
    ]
    for mod in mock_modules:
        sys.modules[mod] = mock.MagicMock()

    # Switch to in-memory databases for all tests (worker-aware URLs).
    from app.database.session_handler import set_database_urls
    set_database_urls(_build_database_urls())


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> Any:
    """Reset rate limiter storage before and after each test to prevent false rate limiting.

    slowapi uses an in-memory storage backend by default. We reset it both before
    and after each test to ensure each test starts with a clean slate. Storage is
    always recreated (rather than conditionally cleared) because slowapi may
    initialize it lazily during request processing.
    """
    from app.core.rate_limiter import limiter
    from limits.storage import MemoryStorage

    def _create_storage():
        try:
            return MemoryStorage()
        except RuntimeError:
            # If thread creation fails (e.g., under heavy load or ulimit constraints),
            # return the existing storage to avoid breaking the test.
            return limiter._storage

    # Always replace with fresh storage to clear all rate limit state.
    # This handles both pre-initialized and lazily-initialized storage.
    limiter._storage = _create_storage()  # pyright: ignore[reportPrivateUsage]
    yield
    # Reset again after the test to ensure clean state for the next test.
    limiter._storage = _create_storage()  # pyright: ignore[reportPrivateUsage]


def set_dependency_override(client: Any, dependency: Any, override: Any) -> None:
    """Set a dependency override on the test client's app.

    Helper to work around TestClient.app having incomplete type stubs.
    """
    app = client.app  # pyright: ignore[reportAttributeAccessIssue]
    app.dependency_overrides[dependency] = override  # pyright: ignore[reportAttributeAccessIssue]


def clear_dependency_overrides(client: Any) -> None:
    """Clear all dependency overrides on the test client's app.

    Helper to work around TestClient.app having incomplete type stubs.
    """
    app = client.app  # pyright: ignore[reportAttributeAccessIssue]
    app.dependency_overrides.clear()  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# Centralized test fixtures and helpers
# ---------------------------------------------------------------------------


def create_mock_user(
    user_id: int = 1,
    username: str = "testuser",
    email: str = "test@example.com",
    is_active: bool = True,
) -> Any:
    """Create a mock user object for dependency overrides.

    Centralizes the mock user pattern duplicated across multiple test files.
    """
    from unittest.mock import Mock

    mock_user = Mock()
    mock_user.id = user_id
    mock_user.username = username
    mock_user.email = email
    mock_user.is_active = is_active
    return mock_user


def _mount_static_files(app: Any) -> None:
    """Mount static files directory on a FastAPI app for template rendering.

    Silently ignores errors if the static directory is unavailable.
    """
    from fastapi.staticfiles import StaticFiles

    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    except Exception:
        pass


def create_app_client(
    routers: list[tuple[Any, str]] | None = None,
    dependency_overrides: dict | None = None,
    mount_static: bool = False,
) -> Any:
    """Create a minimal FastAPI TestClient with specified routers.

    Args:
        routers: List of (router, prefix) tuples to include on the app.
            Use empty string for no prefix override (uses router's default).
        dependency_overrides: Dict of dependency -> override callable.
        mount_static: Whether to mount the static files directory.

    Returns:
        A TestClient instance wrapping the configured app.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    if mount_static:
        _mount_static_files(app)

    if routers:
        for router, prefix in routers:
            app.include_router(router, prefix=prefix)

    if dependency_overrides:
        app.dependency_overrides.update(dependency_overrides)

    return TestClient(app)


@pytest.fixture
def mock_current_user() -> Any:
    """Return a mock active user for dependency overrides."""
    return create_mock_user()


@pytest.fixture
def mock_current_user_factory() -> Any:
    """Return a factory callable for creating mock users.

    Useful when tests need multiple users with different attributes.
    """
    return create_mock_user


# Centralized client fixtures per router
# These replace duplicated TestClient setup across test files.


@pytest.fixture
def models_client() -> Any:
    """Create test client with models router."""
    from app.api.v1.endpoints.models import router as models_router
    return create_app_client(
        routers=[(models_router, "/models")],
        mount_static=True,
    )


@pytest.fixture
def predictions_client() -> Any:
    """Create test client with predictions router."""
    from app.api.v1.endpoints.predictions import router as predictions_router
    return create_app_client(
        routers=[(predictions_router, "/predictions")],
        mount_static=True,
    )


@pytest.fixture
def dangerous_functions_client() -> Any:
    """Create test client with dangerous functions router."""
    from app.api.v1.endpoints.dangerous_functions import router as df_router
    return create_app_client(
        routers=[(df_router, "/dangerous-functions")],
        mount_static=True,
    )


@pytest.fixture
def models_client_with_auth(mock_current_user: Any) -> Any:
    """Create test client with models router and auth override."""
    from app.api.v1.endpoints.models import router as models_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(models_router, "/models")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
        mount_static=True,
    )


@pytest.fixture
def predictions_client_with_auth(mock_current_user: Any) -> Any:
    """Create test client with predictions router and auth override."""
    from app.api.v1.endpoints.predictions import router as predictions_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(predictions_router, "/predictions")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
        mount_static=True,
    )


@pytest.fixture
def dangerous_functions_client_with_auth(mock_current_user: Any) -> Any:
    """Create test client with dangerous functions router and auth override."""
    from app.api.v1.endpoints.dangerous_functions import router as df_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(df_router, "/dangerous-functions")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
        mount_static=True,
    )


@pytest.fixture
def config_client(mock_current_user: Any) -> Any:
    """Create test client with config router and auth override."""
    from app.api.v1.endpoints.config import router as config_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(config_router, "/config")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
    )


@pytest.fixture
def status_client(mock_current_user: Any) -> Any:
    """Create test client with status router and auth override."""
    from app.api.v1.endpoints.status import router as status_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(status_router, "/status")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
    )


@pytest.fixture
def web_client(mock_current_user: Any) -> Any:
    """Create test client with web router and auth override."""
    from app.web.endpoints.web import router as web_router
    from app.auth.dependencies import get_current_active_user
    return create_app_client(
        routers=[(web_router, "")],
        dependency_overrides={get_current_active_user: lambda: mock_current_user},
        mount_static=True,
    )


# ---------------------------------------------------------------------------
# Factory fixtures — expose tests.factories as injectable pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_factory() -> Any:
    """Return the make_user model factory callable."""
    from tests.factories import make_user
    return make_user


@pytest.fixture
def mock_user_factory() -> Any:
    """Return the make_mock_user factory callable (lightweight Mock variant)."""
    from tests.factories import make_mock_user
    return make_mock_user


@pytest.fixture
def binary_factory() -> Any:
    """Return the make_binary model factory callable."""
    from tests.factories import make_binary
    return make_binary


@pytest.fixture
def mock_binary_factory() -> Any:
    """Return the make_mock_binary factory callable."""
    from tests.factories import make_mock_binary
    return make_mock_binary


@pytest.fixture
def model_factory() -> Any:
    """Return the make_model model factory callable."""
    from tests.factories import make_model
    return make_model


@pytest.fixture
def prediction_factory() -> Any:
    """Return the make_prediction model factory callable."""
    from tests.factories import make_prediction
    return make_prediction


@pytest.fixture
def function_factory() -> Any:
    """Return the make_function model factory callable."""
    from tests.factories import make_function
    return make_function


@pytest.fixture
def binary_function_factory() -> Any:
    """Return the make_binary_function model factory callable."""
    from tests.factories import make_binary_function
    return make_binary_function


@pytest.fixture
def task_result_factory() -> Any:
    """Return the make_mock_task_result factory callable."""
    from tests.factories import make_mock_task_result
    return make_mock_task_result
