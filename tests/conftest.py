import sys
from unittest.mock import MagicMock

import pytest

def pytest_configure(config):
    """Mocks the Ghidra/Java world so pytest can collect tests safely."""
    mock_modules = [
        "ghidra", "ghidra.app.decompiler", "ghidra.framework.options",
        "ghidra.util.task", "ghidra.program.model.listing", "ghidra.app.script",
        "java", "java.lang", "pyghidra"
    ]
    for mod in mock_modules:
        sys.modules[mod] = MagicMock()

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)