"""Configuration endpoints for Glyph API.

This module provides endpoints for managing application configuration.
"""

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from app.auth.dependencies import get_current_active_user
from app.config.settings import MAX_CPU_CORES, get_settings, reload_settings
from app.core.rate_limiter import LLM_ANALYSIS_LIMIT, limiter
from app.database.llm_user_config_repository import LLMUserConfigRepository, resolve_user_llm_config
from app.database.models import User
from app.services.llm_analysis_service import LLMNotConfiguredError, test_llm_connection
from app.utils.responses import SuccessResponse, create_error_response, create_success_response

router = APIRouter()

_CONFIG_FILE = Path("config.yml")


class LLMConfigPayload(BaseModel):
    """Payload model for LLM endpoint configuration updates.

    All fields are optional so partial updates are possible. ``None`` means
    "not provided" (except where noted), and provided values are validated
    manually so users get actionable INVALID_LLM_* error codes.

    Attributes:
        enabled: Whether LLM-assisted analysis is enabled.
        base_url: Base URL of the OpenAI-compatible endpoint (host only).
        port: Optional explicit port; an explicit null clears it.
        api_path: Path of the chat completions endpoint.
        model: Model name to send in requests.
        api_key: Optional bearer token; an explicit empty string clears it.
        timeout_seconds: Request timeout in seconds.
        temperature: Sampling temperature for completions.
        max_tokens: Optional maximum tokens to generate; null clears it.
        max_concurrent: Maximum number of parallel analysis requests.

    """

    enabled: bool | None = None
    base_url: str | None = None
    port: int | None = None
    api_path: str | None = None
    model: str | None = None
    api_key: str | None = None
    timeout_seconds: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_concurrent: int | None = None


class ConfigPayload(BaseModel):
    """Payload model for configuration updates.

    Attributes:
        max_file_size_mb: Maximum file size in megabytes.
        cpu_cores: Number of CPU cores to use.
        llm: Optional LLM endpoint configuration updates.

    """

    max_file_size_mb: int | None = None
    cpu_cores: int | None = None
    llm: LLMConfigPayload | None = None


def _validate_llm_payload(llm: LLMConfigPayload) -> dict[str, Any]:
    """Validate the LLM payload and return normalized values to apply.

    Only fields the user explicitly provided are validated and returned, so
    partial updates never clobber values the user did not touch.

    Args:
        llm: The LLM configuration payload.

    Returns:
        Dict of field name to normalized value for the provided fields.

    Raises:
        HTTPException: 400 with an INVALID_LLM_* error code for bad values.

    """
    updates: dict[str, Any] = {}

    def _reject(code: str, message: str) -> None:
        logger.warning("LLM configuration update rejected: {} ({})", code, message)
        raise HTTPException(
            status_code=400,
            detail=create_error_response(error_code=code, error_message=message).model_dump(),
        )

    if llm.enabled is not None:
        updates["enabled"] = bool(llm.enabled)

    if llm.base_url is not None:
        base_url = llm.base_url.strip().rstrip("/")
        if not base_url:
            _reject("INVALID_LLM_BASE_URL", "base_url must not be empty")
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            _reject("INVALID_LLM_BASE_URL", "base_url must be an http(s) URL with a hostname")
        if parts.path not in ("", "/"):
            _reject("INVALID_LLM_BASE_URL", "base_url must be host-only; put the path in the api_path field")
        try:
            _ = parts.port
        except ValueError:
            _reject("INVALID_LLM_BASE_URL", "base_url contains an invalid port")
        updates["base_url"] = base_url

    if "port" in llm.model_fields_set:
        if llm.port is None:
            updates["port"] = None
        elif not (1 <= llm.port <= 65535):
            _reject("INVALID_LLM_PORT", "port must be between 1 and 65535")
        else:
            updates["port"] = llm.port

    if llm.api_path is not None:
        api_path = llm.api_path.strip()
        if not api_path:
            _reject("INVALID_LLM_API_PATH", "api_path must not be empty")
        if not api_path.startswith("/"):
            api_path = f"/{api_path}"
        updates["api_path"] = api_path

    if llm.model is not None:
        model = llm.model.strip()
        if not model:
            _reject("INVALID_LLM_MODEL", "model must not be empty")
        updates["model"] = model

    if llm.api_key is not None:
        updates["api_key"] = llm.api_key

    if llm.timeout_seconds is not None:
        if not (5 <= llm.timeout_seconds <= 600):
            _reject("INVALID_LLM_TIMEOUT", "timeout_seconds must be between 5 and 600")
        updates["timeout_seconds"] = llm.timeout_seconds

    if llm.temperature is not None:
        if not (0.0 <= llm.temperature <= 2.0):
            _reject("INVALID_LLM_TEMPERATURE", "temperature must be between 0 and 2")
        updates["temperature"] = llm.temperature

    if "max_tokens" in llm.model_fields_set:
        if llm.max_tokens is None:
            updates["max_tokens"] = None
        elif llm.max_tokens < 1:
            _reject("INVALID_LLM_MAX_TOKENS", "max_tokens must be at least 1")
        else:
            updates["max_tokens"] = llm.max_tokens

    if llm.max_concurrent is not None:
        if not (1 <= llm.max_concurrent <= 20):
            _reject("INVALID_LLM_MAX_CONCURRENT", "max_concurrent must be between 1 and 20")
        updates["max_concurrent"] = llm.max_concurrent

    return updates


def _persist_config_changes(settings: Any) -> None:
    """Write current settings back to config.yml.

    Reads the existing file, updates the mutable fields, and writes back
    so that changes survive a process restart. The ``llm`` section of the
    file is left untouched: LLM settings are stored per user in the
    database and the file's ``llm`` section only provides global defaults.
    """
    existing: dict[str, Any] = {}
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            logger.warning("Failed to read existing config.yml, overwriting")

    existing["max_file_size_mb"] = settings.max_file_size_mb
    existing["cpu_cores"] = settings.cpu_cores

    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)
        logger.info("Configuration persisted to {}", _CONFIG_FILE)
    except OSError:
        logger.exception("Failed to persist configuration to {}", _CONFIG_FILE)
        raise


@router.post(
    "/save",
    summary="Save configuration",
    description="Update and persist application configuration settings to config.yml.",
)
async def save_config(
    payload: ConfigPayload, current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Saves the configuration settings

    Args:
        payload: The configuration payload containing settings to update.

    Returns:
        Success response with updated configuration.

    Raises:
        HTTPException: If CPU cores value is invalid.

    """
    settings = get_settings()

    if payload.max_file_size_mb is not None:
        if not (1 <= payload.max_file_size_mb <= 2048):
            logger.warning("Configuration update rejected: invalid max_file_size_mb={}", payload.max_file_size_mb)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="INVALID_FILE_SIZE",
                    error_message="max_file_size_mb must be between 1 and 2048",
                ).model_dump(),
            )
        logger.info("Configuration updated: max_file_size_mb={}", payload.max_file_size_mb)
        settings.max_file_size_mb = payload.max_file_size_mb

    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            logger.info("Configuration updated: cpu_cores={}", payload.cpu_cores)
            settings.cpu_cores = payload.cpu_cores
        else:
            logger.warning("Configuration update rejected: invalid cpu_cores={}", payload.cpu_cores)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="INVALID_CPU_CORES", error_message=f"CPU cores must be between 1 and {MAX_CPU_CORES}",
                ).model_dump(),
            )

    if payload.llm is not None:
        llm_updates = _validate_llm_payload(payload.llm)
        for name, value in llm_updates.items():
            log_value = "****" if name == "api_key" and value else value
            logger.info("Configuration updated: llm.{}={}", name, log_value)
        await LLMUserConfigRepository.upsert(current_user.id, llm_updates)

    _persist_config_changes(settings)
    reload_settings()

    logger.info("Configuration saved")

    return create_success_response(data={}, message="Configuration saved successfully")


@router.post(
    "/llm-test",
    summary="Test LLM endpoint connectivity",
    description="Send a minimal prompt to the configured OpenAI-compatible endpoint to verify it is reachable.",
)
@limiter.limit(LLM_ANALYSIS_LIMIT)  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator]
async def test_llm_endpoint(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Test the connection to the configured LLM endpoint.

    Args:
        request: The incoming request (used for rate limiting).
        current_user: The authenticated user.

    Returns:
        Success response with ok/model/elapsed_ms on success, or ok/error
        when the endpoint is reachable but misbehaves.

    Raises:
        HTTPException: 503 LLM_NOT_CONFIGURED when the endpoint cannot be
            built from the current configuration.

    """
    llm = await resolve_user_llm_config(current_user.id)
    try:
        result = await test_llm_connection(llm)
    except LLMNotConfiguredError as exc:
        logger.warning("LLM connection test rejected: {}", exc)
        raise HTTPException(
            status_code=503,
            detail=create_error_response(
                error_code="LLM_NOT_CONFIGURED",
                error_message=str(exc),
            ).model_dump(),
        ) from exc

    if result.ok:
        return create_success_response(
            data={"ok": True, "model": result.model, "elapsed_ms": result.elapsed_ms},
            message="LLM endpoint is reachable",
        )
    return create_success_response(
        data={"ok": False, "error": result.error},
        message="LLM endpoint is not reachable",
    )
