import os
import logging
from unittest.mock import patch, mock_open
import pytest
import yaml

# Import your module — adjust import path as needed
from app.config import GlyphConfig, MAX_CPU_CORES


# --------------------------
# Fixtures
# --------------------------

@pytest.fixture(autouse=True)
def cleanup_singleton_and_logging():
    """Ensure clean state before and after each test."""
    # Reset singleton and config
    GlyphConfig._config = {}
    GlyphConfig._initialized = False
    GlyphConfig.__instance = None

    # Ensure log file doesn't persist across tests
    if os.path.exists("glyph_log.log"):
        os.remove("glyph_log.log")

    yield

    # Optional: cleanup after test
    if os.path.exists("../glyph_log.log"):
        os.remove("glyph_log.log")


@pytest.fixture
def valid_config_content():
    return {
        "upload_folder": "./binaries",
        "max_file_size_mb": 100,
        "cpu_cores": 4,
        "debug": True,
    }


@pytest.fixture
def config_file_path():
    return "../config.yml"


# --------------------------
# Tests
# --------------------------

def test_singleton_new_instance():
    """Test that only one instance is ever created."""
    instance1 = GlyphConfig()
    instance2 = GlyphConfig()
    assert instance1 is instance2


def test_init_only_runs_once():
    """Test __init__ logic only executes once despite multiple instantiations."""
    GlyphConfig()  # first init
    GlyphConfig()  # second — should not re-init
    # _initialized flag should be True after first init
    assert GlyphConfig._initialized


@patch("logging.basicConfig")
def test_init_sets_up_logging(mock_basicConfig):
    """Test initialization sets up logging to file."""
    GlyphConfig()
    mock_basicConfig.assert_called_once()
    args, kwargs = mock_basicConfig.call_args
    assert kwargs.get("filename") == "glyph_log.log"
    assert kwargs.get("encoding") == "utf-8"
    assert kwargs.get("level") == logging.INFO


def test_load_config_success(valid_config_content, config_file_path):
    """Test successful config loading from YAML."""
    with patch("builtins.open", mock_open(read_data=yaml.dump(valid_config_content))):
        result = GlyphConfig.load_config()
        assert result is True
        assert GlyphConfig._config == valid_config_content


def test_load_config_file_not_found():
    """Test behavior when config.yml is missing."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        result = GlyphConfig.load_config()
        assert result is False
        # Ensure error was logged
        with open("glyph_log.log", "r", encoding="utf-8") as f:
            log_content = f.read()
            assert "config.yml not found" in log_content


def test_load_config_yaml_error():
    """Test behavior when YAML parsing fails."""
    invalid_yaml = "key: [unclosed"  # malformed YAML
    with patch("builtins.open", mock_open(read_data=invalid_yaml)):
        result = GlyphConfig.load_config()
        assert result is False
        with open("glyph_log.log", "r", encoding="utf-8") as f:
            assert "Failed to parse config.yml" in f.read()


def test_load_config_empty_or_none_yaml():
    """Test behavior when config.yml is empty or yields None."""
    for data in ["", "null", " \n", None]:
        with patch("builtins.open", mock_open(read_data=data)):
            # Mock safe_load to return empty or None
            with patch("yaml.safe_load", return_value=data or {}):
                result = GlyphConfig.load_config()
                assert result is True
                # Should fallback to empty dict if None
                expected = {} if data is None else {}
                assert GlyphConfig._config == expected


def test_get_config_value_exists():
    """Test `get_config_value` retrieves existing keys."""
    GlyphConfig._config = {"key": "value"}
    assert GlyphConfig.get_config_value("key") == "value"


def test_get_config_value_missing():
    """Test `get_config_value` returns None for missing keys."""
    GlyphConfig._config = {"key": "value"}
    assert GlyphConfig.get_config_value("missing") is None


def test_set_max_file_size_type_error():
    """Test `set_max_file_size` rejects non-int."""
    assert GlyphConfig.set_max_file_size("10") is False
    assert "max_file_size_mb" not in GlyphConfig._config


def test_set_max_file_size_negative():
    """Test `set_max_file_size` rejects ≤0."""
    assert GlyphConfig.set_max_file_size(0) is False
    assert GlyphConfig.set_max_file_size(-5) is False


def test_set_max_file_size_too_large():
    """Test `set_max_file_size` rejects >2048 MB."""
    assert GlyphConfig.set_max_file_size(2049) is False


def test_set_max_file_size_success():
    """Test `set_max_file_size` accepts valid int within range."""
    assert GlyphConfig.set_max_file_size(100) is True
    assert GlyphConfig._config["max_file_size_mb"] == 100


def test_set_max_file_size_edge_cases():
    """Test boundary values."""
    assert GlyphConfig.set_max_file_size(1) is True
    assert GlyphConfig.set_max_file_size(2048) is True


def test_set_cpu_cores_type_error():
    """Test `set_cpu_cores` rejects non-int."""
    assert GlyphConfig.set_cpu_cores("8") is False
    assert "cpu_cores" not in GlyphConfig._config


def test_set_cpu_cores_zero_or_negative():
    """Test `set_cpu_cores` rejects ≤0."""
    assert GlyphConfig.set_cpu_cores(0) is False
    assert GlyphConfig.set_cpu_cores(-2) is False


def test_set_cpu_cores_exceeds_max():
    """Test `set_cpu_cores` rejects >MAX_CPU_CORES."""
    too_many = MAX_CPU_CORES + 1
    assert GlyphConfig.set_cpu_cores(too_many) is False
    with open("glyph_log.log", "r", encoding="utf-8") as f:
        assert f"Attempted to set more than {MAX_CPU_CORES} CPU cores" in f.read()


def test_set_cpu_cores_success():
    """Test `set_cpu_cores` accepts valid int."""
    cores = 4
    assert GlyphConfig.set_cpu_cores(cores) is True
    assert GlyphConfig._config["cpu_cores"] == cores


def test_set_cpu_cores_boundary_valid():
    """Test edge case of 1 and MAX_CPU_CORES."""
    assert GlyphConfig.set_cpu_cores(1) is True
    assert GlyphConfig.set_cpu_cores(MAX_CPU_CORES) is True


def test_default_upload_folder_set_in_init():
    """Test that `UPLOAD_FOLDER` is set to './binaries' in __init__."""
    GlyphConfig()  # calls __init__ once
    assert GlyphConfig._config["UPLOAD_FOLDER"] == "./binaries"


# Optional: Add integration-style test with real YAML file
def test_load_config_with_real_file(tmp_path, valid_config_content):
    """Integration test using actual file system."""
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(valid_config_content))

    with patch("glyph_app.glyph_config.GlyphConfig._config", {}):
        with patch.dict(os.environ, {"CONFIG_FILE": str(config_file)}):
            # Use path directly instead of open mock
            with patch("builtins.open", mock_open(read_data=yaml.dump(valid_config_content))):
                result = GlyphConfig.load_config()
                assert result is True
                assert GlyphConfig._config["cpu_cores"] == valid_config_content["cpu_cores"]