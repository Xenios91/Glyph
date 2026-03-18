# test_glyph_config.py
import os
import yaml
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest

# Import *after* mocking fixtures — critical to avoid side effects
# We'll use lazy import in tests to ensure clean mocking


# ===== FIXTURES =====


@pytest.fixture(autouse=True)
def cleanup_singleton_and_logging():
    """Reset singleton state and logging before each test to avoid leakage."""
    # Import inside fixture to avoid issues with lazy import
    from app.config import GlyphConfig
    import logging

    # Reset singleton
    GlyphConfig._config = {}
    GlyphConfig._initialized = False
    GlyphConfig.__instance = None

    # Reset logging
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("glyph_log.log", mode="w", encoding="utf-8")],
    )

    yield

    # Optional: clear log file (but keep for test inspection if needed)
    # Path("glyph_log.log").unlink(missing_ok=True)


@pytest.fixture
def valid_config_content():
    return {"cpu_cores": 4, "max_file_size_mb": 100, "UPLOAD_FOLDER": "./binaries"}


# ===== TESTS =====


def test_set_cpu_cores_type_error():
    """Test `set_cpu_cores` rejects non-int."""
    # Lazy import to avoid side effects
    from app.config import GlyphConfig

    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            result = GlyphConfig.set_cpu_cores("8")
            assert result is False
            assert "cpu_cores" not in GlyphConfig._config


def test_set_cpu_cores_zero_or_negative():
    """Test `set_cpu_cores` rejects ≤0."""
    from app.config import GlyphConfig

    assert GlyphConfig.set_cpu_cores(0) is False
    assert GlyphConfig.set_cpu_cores(-2) is False


def test_set_cpu_cores_exceeds_max():
    """Test `set_cpu_cores` rejects >MAX_CPU_CORES."""
    from app.config import GlyphConfig
    import os

    MAX_CPU_CORES = os.cpu_count() or 1

    too_many = MAX_CPU_CORES + 1
    assert GlyphConfig.set_cpu_cores(too_many) is False

    log_path = "glyph_log.log"
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert f"Attempted to set more than {MAX_CPU_CORES} CPU cores" in log_content


def test_set_cpu_cores_success():
    """Test `set_cpu_cores` accepts valid int."""
    from app.config import GlyphConfig

    cores = 1
    assert GlyphConfig.set_cpu_cores(cores) is True
    assert GlyphConfig._config["cpu_cores"] == cores


def test_set_cpu_cores_boundary_valid():
    """Test edge case of 1 and MAX_CPU_CORES."""
    from app.config import GlyphConfig
    import os

    MAX_CPU_CORES = os.cpu_count() or 1

    assert GlyphConfig.set_cpu_cores(1) is True
    assert GlyphConfig.set_cpu_cores(MAX_CPU_CORES) is True


def test_default_upload_folder_set_in_init():
    """Test that `UPLOAD_FOLDER` is set to './binaries' in __init__."""
    from app.config import GlyphConfig

    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            GlyphConfig.load_config()
            assert GlyphConfig._config["UPLOAD_FOLDER"] == "./binaries"


# Integration test: uses real filesystem (via tmp_path), but isolated per test
def test_load_config_with_real_file(tmp_path, valid_config_content):
    """Integration test using actual file system (but temp file)."""
    from app.config import GlyphConfig

    config_file = tmp_path / "config.yml"
    config_content = {
        "cpu_cores": 2,
        "max_file_size_mb": 512,
        "UPLOAD_FOLDER": "./binaries",
    }
    config_file.write_text(yaml.dump(config_content))

    with patch.dict(os.environ, {"CONFIG_FILE": str(config_file)}, clear=True):
        result = GlyphConfig.load_config()

    assert result is True
    assert GlyphConfig._config["cpu_cores"] == config_content["cpu_cores"]
    assert GlyphConfig._config["max_file_size_mb"] == config_content["max_file_size_mb"]
    assert GlyphConfig._config["UPLOAD_FOLDER"] == config_content["UPLOAD_FOLDER"]


@pytest.mark.parametrize(
    "cores,expected",
    [
        (0, False),
        (-1, False),
        ("4", False),
        (1.5, False),
        (os.cpu_count(), True),
        (os.cpu_count() + 1, False),
        (10, False),
    ],
)
def test_set_cpu_cores_parametrized(cores, expected):
    from app.config import GlyphConfig

    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            result = GlyphConfig.set_cpu_cores(cores)
            assert result is expected
