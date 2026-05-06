import sys
from unittest import mock

import pytest


def pytest_configure(config):
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra"
    ]
    for mod in mock_modules:
        sys.modules[mod] = mock.MagicMock()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset rate limiters before each test to prevent false rate limiting in tests."""
    from app.core.rate_limiter import login_limiter, register_limiter, password_change_limiter, refresh_limiter
    login_limiter._requests.clear()
    register_limiter._requests.clear()
    password_change_limiter._requests.clear()
    refresh_limiter._requests.clear()
    yield

