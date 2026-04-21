"""Status endpoints for Glyph API.

This module provides endpoints for checking the status of tasks and operations.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, StringConstraints

from app.api.types import UUID as UUIDType
from app.processing.task_management import TaskManager
from app.utils.responses import create_success_response, create_error_response, SuccessResponse
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.database.models import User

router = APIRouter()


class StatusUpdatePayload(BaseModel):
    """Payload model for status updates.

    Attributes:
        status: The status message (automatically validated and stripped).
        uuid: The UUID associated with the status (automatically validated and stripped).
    """

    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    uuid: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/getStatus", response_model=SuccessResponse[dict])
async def get_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    uuid: UUIDType = Query(...),
):
    """
    Handles a GET request to obtain the supplied uuid task status.
    
    Args:
        uuid: The task UUID (automatically validated and stripped).
        
    Returns:
        Task status response.
        
    Raises:
        HTTPException: If UUID is not found.
    """
    status = TaskManager().get_status(uuid)

    if status == "UUID Not Found":
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="UUID_NOT_FOUND",
                error_message="UUID Not Found",
            ).model_dump(),
        )

    return create_success_response(
        data={"status": status},
        message="Task status retrieved successfully",
    )


@router.post("/statusUpdate", response_model=SuccessResponse[dict])
async def update_status(
    payload: StatusUpdatePayload,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Handles a POST request (typically from Ghidra) to update
    the current status of a task.
    
    Args:
        payload: The status update payload with validated status and uuid.
        
    Returns:
        Success response when status is updated.
        
    Raises:
        HTTPException: If UUID is not found.
    """
    # Validation is handled by Pydantic - status and uuid are already stripped and validated
    updated: bool = TaskManager().set_status(payload.uuid, payload.status)

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="UUID_NOT_FOUND",
                error_message="UUID not found",
            ).model_dump(),
        )

    return create_success_response(
        data={"success": True},
        message="Task status updated successfully",
    )
