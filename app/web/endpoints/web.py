from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

import app._version as _version
from app.config.settings import MAX_CPU_CORES, get_settings
from app.utils.helpers import ACCEPT_TYPE
from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil, PredictionPersistanceUtil
from app.processing.task_management import TaskManager
from app.utils.common import format_code, build_prediction_details_response
from app.utils.jinja_utils import configure_jinja2_templates
from loguru import logger
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.database.models import User


router = APIRouter()
templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)


@router.get("/")
async def home(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Loads the homepage of Glyph
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(content={"version": _version.__version__})

    return templates.TemplateResponse(
        "main.html",
        {"request": request, "title": "Glyph", "user": current_user}
    )


@router.get("/config")
async def config(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Loads the configuration page of Glyph
    """
    settings = get_settings()
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "title": "Glyph - Configuration",
            "max_cpu_cores": MAX_CPU_CORES,
            "current_cpu_cores": settings.cpu_cores,
            "current_max_file_size": settings.max_file_size_mb,
            "user": current_user,
        })


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
        "error.html", {"request": request, "title": "Glyph - Error", "message": message}
    )


@router.get("/uploadBinary")
async def get_upload_binary(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
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
        {"request": request, "title": "Glyph - Upload Binary", "allow_prediction": allow_prediction, "models": models, "user": current_user})


@router.get("/getModels")
async def get_list_models(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
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
        {"request": request, "title": "Models List", "models": models_status, "user": current_user})


@router.get("/getPredictions")
async def get_list_predictions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Obtain all predictions available"""
    predictions = PredictionPersistanceUtil.get_predictions_list()
    
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"predictions": [p.__dict__ for p in predictions]}

    return templates.TemplateResponse(
        "get_predictions.html",
        {"request": request, "title": "Predictions List", "predictions": predictions, "user": current_user})


@router.get("/getPredictionDetails")
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: str = Query(...),
    function_name: str = Query(...),
    task_name: str = Query(...)):
    """Displays specific details of a prediction"""
    model_name = model_name.strip()
    func_name = function_name.strip()
    task_name = task_name.strip()

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
    except (TypeError, IndexError, KeyError) as exc:
        logger.error("Failed to retrieve prediction details: {}", exc)
        raise HTTPException(status_code=400, detail="Could not retrieve details") from exc

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            "prediction_function_details.html",
            {
                "request": request,
                "title": "Glyph - Prediction Details",
                "task_name": task_name,
                "model_name": model_name,
                "function_name": func_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
                "user": current_user,
            })

    return build_prediction_details_response(
        task_name, model_name, func_name, model_tokens, prediction_tokens
    )


@router.get("/getPrediction")
async def get_prediction(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_name: str = Query(...),
    model_name: str = Query(...)):
    """Obtain predictions for a specific task and model"""
    prediction = PredictionPersistanceUtil.get_predictions(task_name, model_name)
    
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "predictions": prediction.predictions
        }

    return templates.TemplateResponse(
        "get_prediction.html",
        {
            "request": request,
            "title": "Prediction Details",
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "prediction": {"predictions": prediction.predictions},
            "user": current_user,
        })


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_user)]
):
    """
    Loads the login page
    """
    # Redirect to home if already logged in
    if current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Glyph - Login", "user": current_user})


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_user)]
):
    """
    Loads the registration page
    """
    # Redirect to home if already logged in
    if current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "title": "Glyph - Register", "user": current_user})


@router.get("/profile")
async def profile_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
    Loads the user profile page
    """
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "title": "Glyph - Profile",
            "user": {
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "created_at": current_user.created_at
            }
        })
