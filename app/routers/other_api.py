from typing_extensions import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, StringConstraints

from app.task_management import Trainer


router = APIRouter()


class StatusUpdatePayload(BaseModel):
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    uuid: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


@router.get("/getStatus")
async def get_status(uuid: str = Query(...)):
    """
    Handles a GET request to obtain the supplied uuid task status.
    """
    if uuid == "all":
        return {"status": "test"}

    status = Trainer().get_status(uuid)

    if status == "UUID Not Found":
        raise HTTPException(status_code=404, detail="UUID Not Found")

    return {"status": status}


@router.post("/statusUpdate")
async def update_status(payload: StatusUpdatePayload):
    """
    Handles a POST request (typically from Ghidra) to update
    the current status of a task.
    """
    status = payload.status.strip()
    uuid = payload.uuid.strip()

    if not status or not uuid:
        raise HTTPException(
            status_code=400, detail="Invalid request, status and uuid cannot be empty"
        )

    updated: bool = Trainer().set_status(uuid, status)

    if not updated:
        raise HTTPException(status_code=404, detail="UUID not found")

    return {}  # Returns a 200 OK by default
