from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config.settings import MAX_CPU_CORES, GlyphConfig

router = APIRouter()


class ConfigPayload(BaseModel):
    max_file_size_mb: int | None = None
    cpu_cores: int | None = None


@router.post("/save")
async def save_config(payload: ConfigPayload):
    """
    Saves the configuration settings
    """
    if payload.max_file_size_mb is not None:
        GlyphConfig.set_max_file_size(payload.max_file_size_mb)

    if payload.cpu_cores is not None:
        if 1 <= payload.cpu_cores <= MAX_CPU_CORES:
            GlyphConfig._config["cpu_cores"] = payload.cpu_cores
        else:
            raise HTTPException(
                status_code=400,
                detail=f"CPU cores must be between 1 and {MAX_CPU_CORES}",
            )

    return JSONResponse(content={})
