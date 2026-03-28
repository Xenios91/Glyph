import logging
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

import app._version as _version
from app.config.settings import MAX_CPU_CORES, GlyphConfig
from app.utils.helpers import ACCEPT_TYPE
from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil, PredictionPersistanceUtil
from app.processing.task_management import TaskManager
from app.utils.common import format_code

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
async def error_page(request: Request, type: str | None = None):
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
    logging.debug("GET /getPredictions called")
    logging.debug("Accept header: %s", request.headers.get("Accept", ""))
    
    predictions = PredictionPersistanceUtil.get_predictions_list()
    logging.debug("Retrieved %d predictions from database", len(predictions))
    
    for i, p in enumerate(predictions):
        logging.debug("Prediction %d: task_name=%s, model_name=%s, predictions_count=%d",
                     i, p.task_name, p.model_name, len(p.predictions))
    
    accept = request.headers.get("Accept", "")
    logging.debug("Accept header value: '%s', ACCEPT_TYPE: '%s', match: %s",
                 accept, ACCEPT_TYPE, ACCEPT_TYPE in accept)

    if ACCEPT_TYPE not in accept:
        logging.debug("Returning JSON response")
        return {"predictions": [p.__dict__ for p in predictions]}

    logging.debug("Returning HTML template response")
    return templates.TemplateResponse(
        "get_predictions.html",
        {"request": request, "title": "Predictions List", "predictions": predictions},
    )


@router.get("/getPredictionDetails")
async def get_prediction_details(
    request: Request,
    modelName: str = Query(...),
    functionName: str = Query(...),
    taskName: str = Query(...),
):
    """Displays specific details of a prediction"""
    model_name = modelName.strip()
    func_name = functionName.strip()
    task_name = taskName.strip()

    try:
        model_info = FunctionPersistanceUtil.get_function(model_name, func_name)
        prediction_data = FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, func_name
        )

        if not model_info:
            raise HTTPException(status_code=404, detail="Function not found in model")
        if not prediction_data:
            raise HTTPException(status_code=404, detail="Prediction not found")

        # model_info is a dict with keys: model_name, function_name, entrypoint, tokens
        model_tokens = format_code(model_info.get("tokens", ""))
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except HTTPException:
        raise
    except (TypeError, IndexError, KeyError) as e:
        logging.error(e)
        raise HTTPException(status_code=400, detail="Could not retrieve details")

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            "prediction_function_details.html",
            {
                "request": request,
                "task_name": task_name,
                "model_name": model_name,
                "function_name": func_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
            },
        )

    return {
        "task_name": task_name,
        "model_name": model_name,
        "function_name": func_name,
        "model_tokens": model_tokens,
        "prediction_tokens": prediction_tokens,
    }


@router.get("/getPrediction")
async def get_prediction(
    request: Request, taskName: str = Query(...), modelName: str = Query(...)
):
    """Obtain predictions for a specific task and model"""
    logging.debug("GET /getPrediction called with taskName=%s, modelName=%s", taskName, modelName)
    logging.debug("Accept header: %s", request.headers.get("Accept", ""))
    
    prediction = PredictionPersistanceUtil.get_predictions(taskName, modelName)
    logging.debug("Retrieved prediction: task_name=%s, model_name=%s, predictions_count=%d",
                 prediction.task_name, prediction.model_name, len(prediction.predictions))
    
    accept = request.headers.get("Accept", "")
    logging.debug("Accept header value: '%s', ACCEPT_TYPE: '%s', match: %s",
                 accept, ACCEPT_TYPE, ACCEPT_TYPE in accept)

    if ACCEPT_TYPE not in accept:
        logging.debug("Returning JSON response")
        return {
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "predictions": prediction.predictions
        }

    logging.debug("Returning HTML template response")
    return templates.TemplateResponse(
        "get_prediction.html",
        {
            "request": request,
            "title": "Prediction Details",
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "prediction": {"predictions": prediction.predictions},
        },
    )
