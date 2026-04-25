"""Configuration endpoints for Glyph API.

This module provides endpoints for managing application configuration.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config.settings import MAX_CPU_CORES, get_settings
from app.utils.logging_config import get_logger
from app.utils.responses import create_success_response, create_error_response, SuccessResponse
from app.auth.dependencies import get_current_active_user
from app.database.models import User

logger = get_logger(__name__)

router = APIRouter()


class ConfigPayload(BaseModel):
    """Payload model for configuration updates.

    Attributes:
        max_file_size_mb: Maximum file size in megabytes.
        cpu_cores: Number of CPU cores to use.
    """

    max_file_size_mb: int | None = None
    cpu_cores: int | None = None


@router.post("/save", response_model=SuccessResponse[dict])
async def save_config(
    payload: ConfigPayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
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
            "Configuration update: max_file_size_mb changed to %d by user_id=%s",
            payload.max_file_size_mb, current_user.id,
            extra={"extra_data": {
                "event": "config_update",
                "setting": "max_file_size_mb",
                "new_value": payload.max_file_size_mb,
                "user_id": current_user.id,
            }}
        )
        settings.max_file_size_mb = payload.max_file_size_mb

    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            logger.info(
                "Configuration update: cpu_cores changed to %d by user_id=%s",
                payload.cpu_cores, current_user.id,
                extra={"extra_data": {
                    "event": "config_update",
                    "setting": "cpu_cores",
                    "new_value": payload.cpu_cores,
                    "user_id": current_user.id,
                }}
            )
            settings.cpu_cores = payload.cpu_cores
        else:
            logger.warning(
                "Configuration update rejected: invalid cpu_cores=%d by user_id=%s",
                payload.cpu_cores, current_user.id,
                extra={"extra_data": {
                    "event": "config_update_rejected",
                    "setting": "cpu_cores",
                    "invalid_value": payload.cpu_cores,
                    "user_id": current_user.id,
                }}
            )
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="INVALID_CPU_CORES",
                    error_message=f"CPU cores must be between 1 and {MAX_CPU_CORES}",
                ).model_dump(),
            )

    logger.info(
        "Configuration saved successfully by user_id=%s",
        current_user.id,
        extra={"extra_data": {
            "event": "config_saved",
            "user_id": current_user.id,
        }}
    )

    return create_success_response(
        data={},
        message="Configuration saved successfully",
    )
