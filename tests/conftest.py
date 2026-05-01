import os
import signal
import sys
from unittest import mock

import pytest

_BINARY_TEST_TIMEOUT = 5

def pytest_configure(config):
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra"
    ]
    for mod in mock_modules:
        sys.modules[mod] = mock.MagicMock()


def _timeout_handler(signum, frame):
    """Force-kill the process when a binaries test times out to prevent heap overflow."""
    print("\n\n!!! TIMEOUT: Binaries endpoint test exceeded {}s — force-killing to prevent heap overflow !!!".format(_BINARY_TEST_TIMEOUT))
    os._exit(124)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Set up alarm-based timeout for binaries endpoint tests."""
    if "test_binaries_endpoint" in str(item.fspath):
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(_BINARY_TEST_TIMEOUT)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item):
    """Clear the alarm after binaries endpoint tests complete."""
    if "test_binaries_endpoint" in str(item.fspath):
        signal.alarm(0)


