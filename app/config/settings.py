"""Configuration module for Glyph application settings."""

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, YamlConfigSettingsSource

import yaml

MAX_CPU_CORES = os.cpu_count() or 1


class GlyphSettings(BaseSettings):
    """Pydantic-based configuration for Glyph application."""

    ghidra_location: Path = Field(..., description="Path to Ghidra installation")
    ghidra_project_location: Path = Field(..., description="Path to Ghidra project directory")
    ghidra_project_name: str = Field(..., description="Name of Ghidra project")
    glyph_script_location: Path = Field(..., description="Path to Glyph Ghidra scripts")

    prediction_probability_threshold: float = Field(
        default=50.0,
        ge=0,
        le=100,
        description="Minimum probability threshold for predictions (0-100)"
    )

    max_file_size_mb: int = Field(
        default=512,
        ge=1,
        le=2048,
        description="Maximum file size for uploads in MB"
    )

    cpu_cores: int = Field(
        default=2,
        ge=1,
        le=32,
        description="Number of CPU cores for processing"
    )

    upload_folder: Path = Field(default=Path("./binaries"), description="Upload directory")

    model_config = {
        "env_prefix": "GLYPH_",
        "extra": "ignore"
    }

    @classmethod
    def settings_customise_sources(cls, *args, **kwargs):
        """Customize settings sources to prioritize YAML file."""
        return (
            YamlConfigSettingsSource(cls, "config.yml"),
        )

    @field_validator(
        'ghidra_location',
        'ghidra_project_location',
        'glyph_script_location',
        mode='before'
    )
    @classmethod
    def convert_to_path(cls, v):
        """Convert string paths to Path objects."""
        return Path(v) if isinstance(v, str) else v


_settings: GlyphSettings | None = None


def get_settings() -> GlyphSettings:
    """Get or create the settings singleton instance.

    Returns:
        GlyphSettings: The application settings instance.

    Raises:
        RuntimeError: If settings fail to load.
    """
    global _settings
    if _settings is None:
        try:
            _settings = GlyphSettings()
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    return _settings


def reload_settings() -> GlyphSettings:
    """Reload settings from config file.

    Returns:
        GlyphSettings: Fresh settings instance.
    """
    global _settings
    _settings = GlyphSettings()
    return _settings


class GlyphConfig:
    """Configuration manager for Glyph application (legacy compatibility)."""

    _config: dict[str, Any] = {}
    _initialized = False

    @staticmethod
    def load_config() -> bool:
        """Load configuration from config.yml file.

        Returns:
            bool: True if configuration loaded successfully, False otherwise.
        """
        if not GlyphConfig._initialized:
            logging.basicConfig(
                filename="glyph_log.log", encoding="utf-8", level=logging.INFO
            )

        try:
            with open("config.yml", "r", encoding="utf-8") as config_file:
                GlyphConfig._config = yaml.safe_load(config_file) or {}

            GlyphConfig._config["UPLOAD_FOLDER"] = "./binaries"
            GlyphConfig._initialized = True
            return True
        except FileNotFoundError:
            logging.error("config.yml not found.")
            return False
        except yaml.YAMLError as yaml_error:
            logging.error("Failed to parse config.yml: %s", yaml_error)
            return False

    @staticmethod
    def get_config_value(value: str) -> Any | None:
        """Get a configuration value by key.

        Args:
            value: The configuration key to retrieve.

        Returns:
            The configuration value or None if not found.
        """
        return GlyphConfig._config.get(value)

    @staticmethod
    def set_max_file_size(size: int) -> bool:
        """Set the maximum file size limit for a file upload.

        Args:
            size (int): The maximum file size in megabytes.

        Returns:
            Bool: True if the maximum file size is set successfully, False otherwise.

        Raises:
            ValueError: If the maximum file size is negative.
            TypeError: If the maximum file size is not an integer.
        """
        if not isinstance(size, int):
            logging.error("Maximum file size must be an integer.")
            return False

        if size < 1:
            logging.error("Attempted to set a file size of 0 MB or smaller.")
            return False

        if size > 2048:
            logging.error("Attempted to set a maximum file size greater than 2048 MB.")
            return False

        GlyphConfig._config["max_file_size_mb"] = size
        return True

    @staticmethod
    def set_cpu_cores(cores: int) -> bool:
        """Set the number of CPU cores available for analysis.

        Args:
            cores (int): The number of CPU cores to use.

        Returns:
            Bool: True if the number of CPU cores is set successfully, False otherwise.

        Raises:
            ValueError: If the number of CPU cores is negative.
            TypeError: If the number of cores is not an integer.
        """
        if not isinstance(cores, int):
            logging.error("Number of CPU cores must be an integer.")
            return False

        if cores <= 0:
            logging.error("Attempted to set a non-positive or 0 number of CPU cores.")
            return False

        if cores > MAX_CPU_CORES:
            logging.error("Attempted to set more than %d CPU cores.", MAX_CPU_CORES)
            return False

        GlyphConfig._config["cpu_cores"] = cores
        return True
