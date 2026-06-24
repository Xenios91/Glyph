"""Task status endpoints for Glyph API v1.

Provides endpoints for checking and updating the status of background
analysis tasks (training, prediction, Ghidra decompilation).
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, StringConstraints

from app.api.types import UUID as UUIDType
from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.processing.task_management import TaskManager
from app.utils.responses import SuccessResponse, create_error_response, create_success_response

# Terminal task states that stop SSE streaming
_TERMINAL_STATUSES: set[str] = {"completed", "error", "failed", "cancelled", "UUID Not Found"}

# Default polling interval and timeout for SSE
_DEFAULT_POLL_INTERVAL: float = 2.0
_DEFAULT_SSE_TIMEOUT: int = 600  # 10 minutes


router = APIRouter()


class StatusUpdatePayload(BaseModel):
    """Payload for updating task status.

    Attributes:
        status: New status value for the task.
        uuid: Unique identifier of the task to update.
    """

    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    uuid: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get(
    "/getStatus",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Get task status",
    description="Retrieve the current status of a background analysis task by its UUID.",
)
async def get_status(
    current_user: Annotated[User, Depends(get_current_active_user)], uuid: UUIDType = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    status = TaskManager().get_status(uuid)

    if status == "UUID Not Found":
        logger.warning("Status check failed: UUID {} not found", uuid)
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="UUID_NOT_FOUND", error_message="UUID Not Found").model_dump(),
        )

    logger.debug("Status retrieved for UUID {} status={}", uuid, status)

    return create_success_response(data={"status": status}, message="Task status retrieved successfully")


@router.post(
    "/statusUpdate",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Update task status",
    description="Update the status of a background analysis task. Requires task ownership.",
)
async def update_status(
    payload: StatusUpdatePayload, current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
    updated: bool = TaskManager().set_status(payload.uuid, payload.status, owner_id=current_user.id)

    if not updated:
        logger.warning("Status update failed: UUID {} not found or ownership denied", payload.uuid)
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="UUID_NOT_FOUND", error_message="UUID not found").model_dump(),
        )

    logger.info("Status updated for UUID {} to '{}' by user {}", payload.uuid, payload.status, current_user.id)

    return create_success_response(data={"success": True}, message="Task status updated successfully")


async def _stream_task_status(
    task_uuid: str,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    timeout: int = _DEFAULT_SSE_TIMEOUT,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for task status updates.

    Polls the task manager at regular intervals and yields status events
    until the task reaches a terminal state or the timeout is exceeded.

    Args:
        task_uuid: The UUID of the task to monitor.
        poll_interval: Seconds between status polls.
        timeout: Maximum seconds to stream before disconnecting.

    Yields:
        Formatted SSE event strings.
    """
    start_time = time.monotonic()
    last_status: str | None = None

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed > timeout:
            logger.info("SSE stream timed out after {:.0f}s for task {}", timeout, task_uuid)
            yield f"data: {json.dumps({'type': 'timeout', 'message': 'Stream timeout exceeded'})}\n\n"
            break

        status = TaskManager().get_status(task_uuid)

        # Only send event if status changed or this is the first event
        if status != last_status:
            event_type = "completed" if status in _TERMINAL_STATUSES and status != "UUID Not Found" else "progress"
            if status == "UUID Not Found":
                event_type = "error"
            elif status in ("completed",):
                event_type = "completed"

            payload: dict[str, Any] = {
                "type": event_type,
                "status": status,
                "timestamp": time.time(),
            }
            logger.debug("SSE event for task {}: {}", task_uuid, payload)
            yield f"data: {json.dumps(payload)}\n\n"
            last_status = status

        if status in _TERMINAL_STATUSES:
            break

        await asyncio.sleep(poll_interval)


@router.get(
    "/streamStatus",
    response_class=StreamingResponse,
    summary="Stream task status updates",
    description=(
        "Subscribe to real-time status updates for a background task using "
        "Server-Sent Events (SSE). The server polls the task status at regular "
        "intervals and streams events until the task reaches a terminal state "
        "(completed, error, failed, cancelled) or the timeout is exceeded."
    ),
)
async def stream_task_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    uuid: Annotated[
        UUIDType,
        Query(..., description="Unique identifier of the task to monitor"),
    ] = ...,
    interval: Annotated[
        float,
        Query(ge=0.5, le=30, description="Polling interval in seconds"),
    ] = _DEFAULT_POLL_INTERVAL,
    timeout: Annotated[
        int,
        Query(ge=10, le=3600, description="Maximum streaming duration in seconds"),
    ] = _DEFAULT_SSE_TIMEOUT,
) -> StreamingResponse:
    """Return an SSE stream that pushes task status updates to the client."""
    # Validate task exists before starting the stream
    initial_status = TaskManager().get_status(uuid)
    if initial_status == "UUID Not Found":
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="UUID_NOT_FOUND",
                error_message="Task not found",
            ).model_dump(),
        )

    logger.info(
        "SSE stream started for task {} (interval={:.1f}s, timeout={:.0f}s)",
        uuid,
        interval,
        timeout,
    )

    return StreamingResponse(
        _stream_task_status(uuid, poll_interval=interval, timeout=timeout),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
