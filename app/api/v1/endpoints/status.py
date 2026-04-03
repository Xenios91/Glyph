"""Status endpoints for Glyph API.

This module provides endpoints for checking the status of tasks and operations.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, StringConstraints
from typing_extensions import Annotated

from app.processing.task_management import Trainer
from app.utils.responses import create_success_response, create_error_response, SuccessResponse

router = APIRouter()


class StatusUpdatePayload(BaseModel):
    """Payload model for status updates.

    Attributes:
        status: The status message.
        uuid: The UUID associated with the status.
    """

    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    uuid: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/getStatus", response_model=SuccessResponse[dict])
async def get_status(uuid: str = Query(...)):
    """
    Handles a GET request to obtain the supplied uuid task status.
    """
    status = Trainer().get_status(uuid)

    if status == "UUID Not Found":
        return create_error_response(
            error_code="UUID_NOT_FOUND",
            error_message="UUID Not Found",
        ), 404

    return create_success_response(
        data={"status": status},
        message="Task status retrieved successfully",
    ), 200


@router.post("/statusUpdate", response_model=SuccessResponse[dict])
async def update_status(payload: StatusUpdatePayload):
    """
    Handles a POST request (typically from Ghidra) to update
    the current status of a task.
    """
    status = payload.status.strip()
    uuid = payload.uuid.strip()

    if not status or not uuid:
        return create_error_response(
            error_code="INVALID_REQUEST",
            error_message="Invalid request, status and uuid cannot be empty",
        ), 400

    updated: bool = Trainer().set_status(uuid, status)

    if not updated:
        return create_error_response(
            error_code="UUID_NOT_FOUND",
            error_message="UUID not found",
        ), 404

    return create_success_response(
        data={"success": True},
        message="Task status updated successfully",
    ), 200
