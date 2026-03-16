from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from app.config import GlyphConfig, MAX_CPU_CORES
import app._version as _version
from app.helpers import ACCEPT_TYPE

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def home(request: Request):
    """
    Loads the homepage of Glyph
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(content={"version": _version.__version__})

    return templates.TemplateResponse("main.html", {"request": request})


@router.get("/config")
async def config(request: Request):
    """
    Loads the configuration page of Glyph
    """
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "max_cpu_cores": MAX_CPU_CORES,
            "current_cpu_cores": GlyphConfig.get_config_value("cpu_cores") or 2,
            "current_max_file_size": GlyphConfig.get_config_value("max_file_size_mb") or 512,
        },
    )


class ConfigPayload(BaseModel):
    max_file_size_mb: Optional[int] = None
    cpu_cores: Optional[int] = None


@router.post("/api/config/save")
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
