"""Configuration endpoints for Glyph API.

This module provides endpoints for managing application configuration.
"""

from pathlib import Path
from typing import Annotated, Any

import yaml

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config.settings import MAX_CPU_CORES, get_settings, reload_settings
from loguru import logger
from app.utils.responses import create_success_response, create_error_response, SuccessResponse
from app.auth.dependencies import get_current_active_user
from app.database.models import User


router = APIRouter()

_CONFIG_FILE = Path("config.yml")


class ConfigPayload(BaseModel):
    """Payload model for configuration updates.

    Attributes:
        max_file_size_mb: Maximum file size in megabytes.
        cpu_cores: Number of CPU cores to use.
    """

    max_file_size_mb: int | None = None
    cpu_cores: int | None = None


def _persist_config_changes(settings: Any) -> None:
    """Write current settings back to config.yml.

    Reads the existing file, updates the mutable fields, and writes back
    so that changes survive a process restart.
    """
    existing: dict[str, Any] = {}
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
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


@router.post("/save", response_model=SuccessResponse[dict[str, Any]])
async def save_config(
    payload: ConfigPayload,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
    """
    Saves the configuration settings
    
    Args:
        payload: The configuration payload containing settings to update.
        
    Returns:
        Success response with updated configuration.
        
    Raises:
        HTTPException: If CPU cores value is invalid.
    """
    settings = get_settings()

    if payload.max_file_size_mb is not None:
        logger.info(
            "Configuration updated: max_file_size_mb={}",
            payload.max_file_size_mb)
        settings.max_file_size_mb = payload.max_file_size_mb

    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            logger.info(
                "Configuration updated: cpu_cores={}",
                payload.cpu_cores)
            settings.cpu_cores = payload.cpu_cores
        else:
            logger.warning(
                "Configuration update rejected: invalid cpu_cores={}",
                payload.cpu_cores)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="INVALID_CPU_CORES",
                    error_message=f"CPU cores must be between 1 and {MAX_CPU_CORES}").model_dump())

    _persist_config_changes(settings)
    reload_settings()

    logger.info("Configuration saved")

    return create_success_response(
        data={},
        message="Configuration saved successfully")
