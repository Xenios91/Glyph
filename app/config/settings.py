"""Configuration module for Glyph application settings."""

import os
import secrets
from pathlib import Path
from typing import Any

from loguru import logger

from pydantic import Field, BaseModel
from pydantic_settings import (
    BaseSettings,
    YamlConfigSettingsSource,
    PydanticBaseSettingsSource,
)

import yaml

MAX_CPU_CORES = os.cpu_count() or 1


# Logging configuration models
class LoggingFileConfig(BaseModel):
    """File logging configuration."""
    path: str = "logs/glyph.log"
    max_size_mb: int = Field(default=50, ge=1, le=1000)
    backup_count: int = Field(default=10, ge=0, le=100)
    rotate: str = Field(default="size", pattern="^(size|time)$")
    time_interval: str = Field(default="midnight", pattern="^(midnight|daily|weekly|monthly)$")


class LoggingConsoleConfig(BaseModel):
    """Console logging configuration."""
    enabled: bool = True
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    colorize: bool = True


class LoggingRequestTracingConfig(BaseModel):
    """Request tracing configuration."""
    enabled: bool = True
    header_name: str = "X-Request-ID"


class LoggingRateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = False
    max_messages: int = Field(default=10, ge=1)
    period: float = Field(default=60.0, gt=0)
    max_keys: int = Field(default=1000, ge=1)


class LoggingAsyncConfig(BaseModel):
    """Async logging configuration."""
    enabled: bool = False
    max_queue_size: int = Field(default=1000, ge=1)


class LoggingSamplingConfig(BaseModel):
    """Log sampling configuration."""
    enabled: bool = False
    rate: float = Field(default=1.0, ge=0.0, le=1.0)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="json", pattern="^(json|text)$")
    file: LoggingFileConfig = Field(default_factory=LoggingFileConfig)
    console: LoggingConsoleConfig = Field(default_factory=LoggingConsoleConfig)
    request_tracing: LoggingRequestTracingConfig = Field(default_factory=LoggingRequestTracingConfig)
    module_levels: dict[str, str] = Field(default_factory=dict)
    rate_limit: LoggingRateLimitConfig = Field(default_factory=LoggingRateLimitConfig)
    async_logging: LoggingAsyncConfig = Field(default_factory=LoggingAsyncConfig)
    sampling: LoggingSamplingConfig = Field(default_factory=LoggingSamplingConfig)


class GlyphSettings(BaseSettings):
    """Pydantic-based configuration for Glyph application."""

    prediction_probability_threshold: float = Field(
        default=50.0,
        ge=0,
        le=100,
        description="Minimum probability threshold for predictions (0-100)")

    max_file_size_mb: int = Field(
        default=512, ge=1, le=2048, description="Maximum file size for uploads in MB"
    )

    cpu_cores: int = Field(
        default=2, ge=1, le=32, description="Number of CPU cores for processing"
    )

    upload_folder: Path = Field(
        default=Path("./binaries"), description="Upload directory"
    )

    # JWT Settings
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT signing"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)
    
    # OAuth2 Settings
    oauth2_enabled: bool = Field(default=False)
    oauth2_session_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    # Authentication Settings
    auth_enabled: bool = Field(default=True, description="Whether authentication is enabled")
    
    # Logging Settings
    logging: LoggingConfig = LoggingConfig()

    model_config = {"env_prefix": "GLYPH_", "extra": "ignore"}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to prioritize YAML file."""
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls, "config.yml"),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


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
            # Logging is now configured centrally in main.py
            # No need to set up logging here
            pass

        try:
            with open("config.yml", "r", encoding="utf-8") as config_file:
                GlyphConfig._config = yaml.safe_load(config_file) or {}

            GlyphConfig._config["UPLOAD_FOLDER"] = "./binaries"
            GlyphConfig._initialized = True
            return True
        except FileNotFoundError:
            logger.error(
                "config.yml not found.")
            return False
        except yaml.YAMLError as yaml_error:
            logger.error(
                "Failed to parse config.yml: {}", yaml_error)
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
            logger.error("Maximum file size must be an integer.")
            return False

        if size < 1:
            logger.error("Attempted to set a file size of 0 MB or smaller.")
            return False

        if size > 2048:
            logger.error("Attempted to set a maximum file size greater than 2048 MB.")
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
            logger.error("Number of CPU cores must be an integer.")
            return False

        if cores <= 0:
            logger.error("Attempted to set a non-positive or 0 number of CPU cores.")
            return False

        if cores > MAX_CPU_CORES:
            logger.error("Attempted to set more than {} CPU cores.", MAX_CPU_CORES)
            return False

        GlyphConfig._config["cpu_cores"] = cores
        return True
