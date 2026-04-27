"""Unit tests for Glyph configuration management."""
import os
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest
from loguru import logger

from app.config.settings import GlyphConfig


@pytest.fixture(autouse=True)
def cleanup_singleton_and_logging(tmp_path):
    """Reset singleton state and logging before each test to prevent state leakage."""
    GlyphConfig._config = {}
    GlyphConfig._initialized = False
    GlyphConfig.__instance = None

    # Create a temporary log file for each test
    log_file = tmp_path / "glyph_log.log"

    # Remove default loguru handler and add a file-based one for test capture
    logger.remove()
    handler_id = logger.add(
        str(log_file),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name} | {message}",
        encoding="utf-8",
    )

    yield log_file

    # Clean up: remove the loguru handler
    logger.remove(handler_id)


@pytest.fixture
def valid_config_content():
    """Provide valid configuration content for tests."""
    return {"cpu_cores": 4, "max_file_size_mb": 100, "UPLOAD_FOLDER": "./binaries"}


def test_set_cpu_cores_type_error():
    """Test that set_cpu_cores rejects non-integer input."""
    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            result = GlyphConfig.set_cpu_cores("8")
            assert result is False
            assert "cpu_cores" not in GlyphConfig._config


def test_set_cpu_cores_zero_or_negative():
    """Test that set_cpu_cores rejects zero and negative values."""
    assert GlyphConfig.set_cpu_cores(0) is False
    assert GlyphConfig.set_cpu_cores(-2) is False


def test_set_cpu_cores_exceeds_max(cleanup_singleton_and_logging):
    """Test that set_cpu_cores rejects values exceeding MAX_CPU_CORES."""
    MAX_CPU_CORES = os.cpu_count() or 1
    too_many = MAX_CPU_CORES + 1

    assert GlyphConfig.set_cpu_cores(too_many) is False

    # Get the log file path from the fixture
    log_path = cleanup_singleton_and_logging
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert f"Invalid CPU cores: {too_many} (maximum is {MAX_CPU_CORES})" in log_content


def test_set_cpu_cores_success():
    """Test that set_cpu_cores accepts valid integer input."""
    cores = 1
    assert GlyphConfig.set_cpu_cores(cores) is True
    assert GlyphConfig._config["cpu_cores"] == cores


def test_set_cpu_cores_boundary_valid():
    """Test boundary values of 1 and MAX_CPU_CORES are accepted."""
    MAX_CPU_CORES = os.cpu_count() or 1

    assert GlyphConfig.set_cpu_cores(1) is True
    assert GlyphConfig.set_cpu_cores(MAX_CPU_CORES) is True


def test_default_upload_folder_set_in_init():
    """Test that UPLOAD_FOLDER defaults to './binaries' during initialization."""
    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            GlyphConfig.load_config()
            assert GlyphConfig._config["UPLOAD_FOLDER"] == "./binaries"


def test_load_config_with_real_file(tmp_path, valid_config_content):
    """Integration test using actual filesystem with temporary file."""
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
        (os.cpu_count() + 5, False),
    ],
)
def test_set_cpu_cores_parametrized(cores, expected):
    """Test set_cpu_cores with various input values using parametrization."""
    with patch("builtins.open", mock_open(read_data="")):
        with patch("yaml.safe_load", return_value={}):
            result = GlyphConfig.set_cpu_cores(cores)
            assert result is expected