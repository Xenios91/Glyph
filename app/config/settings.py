"""Configuration module for Glyph application settings."""

import os
import secrets
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource,
)

MAX_CPU_CORES = os.cpu_count() or 1


class LoggingFileConfig(BaseModel):
    """File logging configuration."""

    path: str = "logs/glyph.log"
    rotation: str = Field(default="50 MB", description="Loguru rotation string (e.g., '50 MB', '00:00', '1 week')")
    retention: str = Field(default="10 days", description="Loguru retention string (e.g., '10 days', '1 month')")


class LoggingConsoleConfig(BaseModel):
    """Console logging configuration."""

    enabled: bool = True
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    colorize: bool = True


class LoggingRequestTracingConfig(BaseModel):
    """Request tracing configuration."""

    enabled: bool = True
    header_name: str = "X-Request-ID"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = Field(default="json", pattern="^(json|text)$")
    file: LoggingFileConfig = Field(default_factory=LoggingFileConfig)
    console: LoggingConsoleConfig = Field(default_factory=LoggingConsoleConfig)
    request_tracing: LoggingRequestTracingConfig = Field(default_factory=LoggingRequestTracingConfig)
    module_levels: dict[str, str] = Field(default_factory=dict)


class GlyphSettings(BaseSettings):
    """Pydantic-based configuration for Glyph application."""

    prediction_probability_threshold: float = Field(
        default=50.0, ge=0, le=100, description="Minimum probability threshold for predictions (0-100)"
    )

    max_file_size_mb: int = Field(default=512, ge=1, le=2048, description="Maximum file size for uploads in MB")

    cpu_cores: int = Field(default=2, ge=1, le=32, description="Number of CPU cores for processing")

    upload_folder: Path = Field(default=Path("./binaries"), description="Upload directory")

    jwt_secret_key: str = Field(
        default="change-me-in-production", description="Secret key for JWT signing (must be changed in production)"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    oauth2_enabled: bool = Field(default=False)
    oauth2_session_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    use_https: bool = Field(default=False, description="Whether the application is deployed behind HTTPS/TLS")
    trusted_proxies: list[str] = Field(
        default_factory=list, description="List of trusted proxy IPs/CIDRs for X-Forwarded-For"
    )

    auth_enabled: bool = Field(default=True, description="Whether authentication is enabled")

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
            _DEFAULT_JWT_SECRET = "change-me-in-production"
            if _settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
                env = os.environ.get("GLYPH_ENV", os.environ.get("ENV", "development"))
                if env == "production":
                    logger.critical(
                        "JWT secret key is using default value in production! "
                        "This is a critical security risk. Refusing to start."
                    )
                    raise RuntimeError(
                        "JWT secret key must be changed from default value in production. "
                        "Set GLYPH_JWT_SECRET_KEY environment variable or update config.yml."
                    )
                else:
                    logger.warning(
                        "Using default JWT secret key. "
                        "Set GLYPH_JWT_SECRET_KEY environment variable or "
                        "jwt_secret_key in config.yml for production use. "
                        "Tokens will be invalidated on application restart."
                    )

            if not _settings.use_https:
                env = os.environ.get("GLYPH_ENV", os.environ.get("ENV", "development"))
                if env == "production":
                    logger.critical(
                        "use_https is False in production! "
                        "Cookies will be sent over unencrypted HTTP. "
                        "Set GLYPH_USE_HTTPS=true or use_https in config.yml."
                    )
                else:
                    logger.warning(
                        "use_https is False — cookies will be sent over unencrypted HTTP. "
                        "Enable use_https in production."
                    )
        except RuntimeError:
            raise
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
