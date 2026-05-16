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


# In-memory database URLs for testing.
# Each database uses a unique URI so they remain separate in-memory databases.
IN_MEMORY_DATABASE_URLS: dict[str, str] = {
    "models": "sqlite+aiosqlite:///file:mem_models?mode=memory&cache=shared",
    "predictions": "sqlite+aiosqlite:///file:mem_predictions?mode=memory&cache=shared",
    "functions": "sqlite+aiosqlite:///file:mem_functions?mode=memory&cache=shared",
    "auth": "sqlite+aiosqlite:///file:mem_auth?mode=memory&cache=shared",
}


def pytest_configure(config: Any) -> None:
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules: list[str] = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra"
    ]
    for mod in mock_modules:
        sys.modules[mod] = mock.MagicMock()

    # Switch to in-memory databases for all tests.
    from app.database.session_handler import set_database_urls
    set_database_urls(IN_MEMORY_DATABASE_URLS)


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
    # Always replace with fresh storage to clear all rate limit state.
    # This handles both pre-initialized and lazily-initialized storage.
    limiter._storage = MemoryStorage()  # pyright: ignore[reportPrivateUsage]
    yield
    # Reset again after the test to ensure clean state for the next test.
    limiter._storage = MemoryStorage()  # pyright: ignore[reportPrivateUsage]


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
