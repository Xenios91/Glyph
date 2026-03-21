import pytest
import pyghidra

@pytest.fixture(scope="session", autouse=True)
def start_ghidra():
    """Starts the Ghidra JVM once for the entire test session."""
    if not pyghidra.is_active():
        pyghidra.start()