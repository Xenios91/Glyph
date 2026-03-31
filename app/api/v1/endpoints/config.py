from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config.settings import MAX_CPU_CORES, get_settings
from app.utils.responses import create_success_response, create_error_response

router = APIRouter()


class ConfigPayload(BaseModel):
    max_file_size_mb: int | None = None
    cpu_cores: int | None = None


@router.post("/save")
async def save_config(payload: ConfigPayload):
    """
    Saves the configuration settings
    """
    settings = get_settings()

    if payload.max_file_size_mb is not None:
        settings.max_file_size_mb = payload.max_file_size_mb

    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            settings.cpu_cores = payload.cpu_cores
        else:
            return JSONResponse(
                content=create_error_response(
                    error_code="INVALID_CPU_CORES",
                    error_message=f"CPU cores must be between 1 and {MAX_CPU_CORES}",
                ).model_dump(),
                status_code=400,
            )

    return JSONResponse(
        content=create_success_response(
            data={},
            message="Configuration saved successfully",
        ).model_dump(),
        status_code=200,
    )
