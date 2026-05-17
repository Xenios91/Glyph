from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, StringConstraints

from app.api.types import UUID as UUIDType
from app.processing.task_management import TaskManager
from loguru import logger
from app.utils.responses import create_success_response, create_error_response, SuccessResponse
from app.auth.dependencies import get_current_active_user
from app.database.models import User


router = APIRouter()


class StatusUpdatePayload(BaseModel):
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    uuid: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/getStatus", response_model=SuccessResponse[dict[str, Any]])
async def get_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    uuid: UUIDType = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    status = TaskManager().get_status(uuid)

    if status == "UUID Not Found":
        logger.warning("Status check failed: UUID {} not found", uuid)
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="UUID_NOT_FOUND",
                error_message="UUID Not Found").model_dump())

    logger.debug("Status retrieved for UUID {} status={}", uuid, status)

    return create_success_response(
        data={"status": status},
        message="Task status retrieved successfully")


@router.post("/statusUpdate", response_model=SuccessResponse[dict[str, Any]])
async def update_status(
    payload: StatusUpdatePayload,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
    updated: bool = TaskManager().set_status(
        payload.uuid, payload.status, owner_id=current_user.id)

    if not updated:
        logger.warning(
            "Status update failed: UUID {} not found or ownership denied",
            payload.uuid)
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="UUID_NOT_FOUND",
                error_message="UUID not found").model_dump())

    logger.info(
        "Status updated for UUID {} to '{}' by user {}",
        payload.uuid, payload.status, current_user.id)

    return create_success_response(
        data={"success": True},
        message="Task status updated successfully")
