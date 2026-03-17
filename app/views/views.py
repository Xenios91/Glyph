from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

import app._version as _version
from app.config import MAX_CPU_CORES, GlyphConfig
from app.helpers import ACCEPT_TYPE
from app.persistance_util import MLPersistanceUtil, PredictionPersistanceUtil
from app.task_management import TaskManager

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
            "current_max_file_size": GlyphConfig.get_config_value("max_file_size_mb")
            or 512,
        },
    )


@router.get("/error")
async def error_page(request: Request, type: Optional[str] = None):
    """
    Displays errors using the templates system.
    """
    message = "Uh oh! An unknown error has occurred"

    if type == "uploadError":
        message = (
            "Uh oh! It looks like the binary file is not of type ELF. "
            "If it's PE don't worry, we are working on implementing PE capabilities."
        )

    return templates.TemplateResponse(
        "error.html", {"request": request, "message": message}
    )


@router.get("/uploadBinary")
async def get_upload_binary(request: Request):
    """
    Handles GET request to load the upload webpage
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(
            content={"error": "API calls can only be POST"}, status_code=200
        )

    models: set[str] = MLPersistanceUtil.get_models_list()
    allow_prediction = len(models) > 0
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "allow_prediction": allow_prediction, "models": models},
    )


@router.get("/getModels")
async def get_list_models(request: Request):
    """
    Handles a GET request to obtain all models available
    """
    models: set[str] = MLPersistanceUtil.get_models_list()
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"models": list(models)}

    models_status: dict = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"

    return templates.TemplateResponse(
        "get_models.html",
        {"request": request, "title": "Models List", "models": models_status},
    )


@router.get("/getPredictions")
async def get_list_predictions(request: Request):
    """Obtain all predictions available"""
    predictions = PredictionPersistanceUtil.get_predictions_list()
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"predictions": [p.__dict__ for p in predictions]}

    return templates.TemplateResponse(
        "get_predictions.html",
        {"request": request, "title": "Predictions List", "predictions": predictions},
    )
