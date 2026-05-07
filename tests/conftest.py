import sys
from typing import Any
from unittest import mock

import pytest


def pytest_configure(config: Any) -> None:
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules: list[str] = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra"
    ]
    for mod in mock_modules:
        sys.modules[mod] = mock.MagicMock()


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> Any:
    """Reset rate limiters before each test to prevent false rate limiting in tests."""
    from app.core.rate_limiter import login_limiter, register_limiter, password_change_limiter, refresh_limiter
    login_limiter._requests.clear()  # pyright: ignore[reportPrivateUsage]
    register_limiter._requests.clear()  # pyright: ignore[reportPrivateUsage]
    password_change_limiter._requests.clear()  # pyright: ignore[reportPrivateUsage]
    refresh_limiter._requests.clear()  # pyright: ignore[reportPrivateUsage]
    yield


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
