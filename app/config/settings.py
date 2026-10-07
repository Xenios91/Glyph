"""Configuration module for Glyph application settings."""

import os
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


class LLMConfig(BaseModel):
    """OpenAI-compatible endpoint configuration for LLM-assisted analysis."""

    enabled: bool = False
    base_url: str = "http://localhost:11434"
    port: int | None = None
    api_path: str = "/v1/chat/completions"
    model: str = "llama3"
    api_key: str = ""
    timeout_seconds: float = Field(default=900.0, ge=60)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    max_concurrent: int = Field(default=5, ge=1, le=20)


class GlyphSettings(BaseSettings):
    """Pydantic-based configuration for Glyph application."""

    prediction_probability_threshold: float = Field(
        default=50.0, ge=0, le=100, description="Minimum probability threshold for predictions (0-100)",
    )

    max_file_size_mb: int = Field(default=512, ge=1, le=2048, description="Maximum file size for uploads in MB")

    cpu_cores: int = Field(default=2, ge=1, le=32, description="Number of CPU cores for processing")

    upload_folder: Path = Field(default=Path("./binaries"), description="Upload directory")

    jwt_secret_key: str = Field(
        default="change-me-in-production", description="Secret key for JWT signing (must be changed in production)",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    use_https: bool = Field(default=False, description="Whether the application is deployed behind HTTPS/TLS")
    trusted_proxies: list[str] = Field(
        default_factory=list, description="List of trusted proxy IPs/CIDRs for X-Forwarded-For",
    )

    auth_enabled: bool = Field(default=True, description="Whether authentication is enabled")

    logging: LoggingConfig = LoggingConfig()

    llm: LLMConfig = Field(default_factory=LLMConfig)

    model_config = {"env_prefix": "GLYPH_", "extra": "ignore", "env_nested_delimiter": "_"}

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

_DEFAULT_JWT_SECRET = "change-me-in-production"
_MIN_JWT_SECRET_LEN = 32


def _validate_production_settings(settings: GlyphSettings) -> None:
    """Validate security-critical settings for the current environment.

    Args:
        settings: The settings instance to validate.

    Raises:
        RuntimeError: If a security-critical setting is unsafe for production.

    """
    env = os.environ.get("GLYPH_ENV", os.environ.get("ENV", "development"))
    is_production = env == "production"

    # Treat an empty/whitespace-only secret as unset so the production guard
    # triggers instead of silently signing tokens with an empty key.
    if not settings.jwt_secret_key.strip():
        settings.jwt_secret_key = _DEFAULT_JWT_SECRET

    if settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
        if is_production:
            logger.critical(
                "JWT secret key is using default value in production! "
                "This is a critical security risk. Refusing to start.",
            )
            raise RuntimeError(
                "JWT secret key must be changed from default value in production. "
                "Set GLYPH_JWT_SECRET_KEY environment variable or update config.yml.",
            )
        else:
            logger.warning(
                "Using default JWT secret key. "
                "Set GLYPH_JWT_SECRET_KEY environment variable or "
                "jwt_secret_key in config.yml for production use. "
                "Tokens will be invalidated on application restart.",
            )
    elif is_production and len(settings.jwt_secret_key) < _MIN_JWT_SECRET_LEN:
        logger.critical(
            "JWT secret key is shorter than the recommended minimum in production! "
            "This is a security risk. Refusing to start.",
        )
        raise RuntimeError(
            f"JWT secret key must be at least {_MIN_JWT_SECRET_LEN} characters in production. "
            "Set a stronger GLYPH_JWT_SECRET_KEY environment variable or update config.yml.",
        )

    if not settings.use_https:
        if is_production:
            logger.critical(
                "use_https is False in production! "
                "Cookies will be sent over unencrypted HTTP. "
                "Set GLYPH_USE_HTTPS=true or use_https in config.yml.",
            )
        else:
            logger.warning(
                "use_https is False — cookies will be sent over unencrypted HTTP. "
                "Enable use_https in production.",
            )


def get_settings() -> GlyphSettings:
    """Get or create the settings singleton instance.

    Returns:
        GlyphSettings: The application settings instance.

    Raises:
        RuntimeError: If settings fail to load or are unsafe for production.

    """
    global _settings
    if _settings is None:
        try:
            _settings = GlyphSettings()
            _validate_production_settings(_settings)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}") from e
    return _settings


def reload_settings() -> GlyphSettings:
    """Reload settings from config file and re-validate security settings.

    Returns:
        GlyphSettings: Fresh settings instance.

    Raises:
        RuntimeError: If the reloaded settings are unsafe for production.

    """
    global _settings
    _settings = GlyphSettings()
    _validate_production_settings(_settings)
    return _settings
