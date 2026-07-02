"""Web UI endpoints for Glyph application.

Serves HTML templates for the browser-based interface, including pages
for model management, predictions, configuration, binary upload, and
user authentication.
"""

from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession

import app._version as _version
from app.auth.dependencies import get_current_active_user, get_db, get_jwt_handler, get_optional_user
from app.auth.jwt_handler import JWTHandler
from app.config.settings import MAX_CPU_CORES, get_settings
from app.core.rate_limiter import LOGIN_LIMIT, REGISTER_LIMIT, limiter
from app.database.function_repository import FunctionRepository
from app.database.model_repository import ModelRepository
from app.database.models import User
from app.database.prediction_repository import PredictionRepository
from app.database.repository import UserRepository
from app.processing.task_management import TaskManager
from app.templates import templates
from app.utils.common import build_prediction_details_response, format_code
from app.utils.helpers import ACCEPT_TYPE

router = APIRouter()


@router.get("/", response_model=None)
async def home(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
) -> JSONResponse | HTMLResponse:
    """
    Loads the homepage of Glyph
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(content={"version": _version.__version__})

    return templates.TemplateResponse(request, "main.html", {"title": "Glyph", "user": current_user})


@router.get("/stats", response_model=None)
async def home_stats(request: Request, current_user: Annotated[User, Depends(get_current_active_user)]) -> JSONResponse:
    """
    Returns homepage statistics for the current user.
    """
    from app.database.sql_service import SQLUtil

    binaries = await SQLUtil.get_binaries_by_user(current_user.id)
    models = await ModelRepository.get_models_list()
    predictions = await PredictionRepository.get_predictions_list()

    return JSONResponse(
        content={
            "binaries": len(binaries),
            "models": len(models),
            "predictions": len(predictions) if predictions else 0,
        }
    )


@router.get("/config")
async def config(request: Request, current_user: Annotated[User, Depends(get_current_active_user)]) -> HTMLResponse:
    """
    Loads the configuration page of Glyph
    """
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "title": "Glyph - Configuration",
            "max_cpu_cores": MAX_CPU_CORES,
            "current_cpu_cores": settings.cpu_cores,
            "current_max_file_size": settings.max_file_size_mb,
            "user": current_user,
        },
    )


@router.get("/error")
async def error_page(request: Request, type: str | None = None) -> HTMLResponse:
    """
    Displays errors using the templates system.
    """
    message = "Uh oh! An unknown error has occurred"

    if type == "uploadError":
        message = (
            "Uh oh! It looks like the binary file is not of type ELF. "
            "If it's PE don't worry, we are working on implementing PE capabilities."
        )

    return templates.TemplateResponse(request, "error.html", {"title": "Glyph - Error", "message": message})


@router.get("/getModels", response_model=None)
async def get_list_models(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
) -> dict[str, list[str]] | HTMLResponse:
    """
    Handles a GET request to obtain all models available
    """
    models: list[str] = list(await ModelRepository.get_models_list())
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"models": list(models)}

    models_status: dict[str, str] = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"

    return templates.TemplateResponse(
        request, "get_models.html", {"title": "Models List", "models": models_status, "user": current_user}
    )


@router.get("/getPredictions", response_model=None)
async def get_list_predictions(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
) -> dict[str, list[dict[str, Any]]] | HTMLResponse:
    """Obtain all predictions available"""
    predictions = await PredictionRepository.get_predictions_list()

    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"predictions": [p.__dict__ for p in predictions]}

    return templates.TemplateResponse(
        request, "get_predictions.html", {"title": "Predictions List", "predictions": predictions, "user": current_user}
    )


@router.get("/getPredictionDetails", response_model=None)
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: str = Query(...),
    function_name: str = Query(...),
    task_name: str = Query(...),
) -> dict[str, str] | HTMLResponse:
    """Displays specific details of a prediction"""
    model_name = model_name.strip()
    func_name = function_name.strip()
    task_name = task_name.strip()

    try:
        model_info = await FunctionRepository.get(model_name, func_name)
        prediction_data = await PredictionRepository.get_prediction_function(task_name, model_name, func_name)

        if not model_info:
            raise HTTPException(status_code=404, detail="Function not found in model")
        if not prediction_data:
            raise HTTPException(status_code=404, detail="Prediction not found")

        model_tokens = format_code(getattr(model_info, "tokens", ""))
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except HTTPException:
        raise
    except (TypeError, IndexError, KeyError) as exc:
        logger.exception("Failed to retrieve prediction details")
        raise HTTPException(status_code=400, detail="Could not retrieve details") from exc

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "prediction_function_details.html",
            {
                "title": "Glyph - Prediction Details",
                "task_name": task_name,
                "model_name": model_name,
                "function_name": func_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
                "user": current_user,
            },
        )

    return build_prediction_details_response(task_name, model_name, func_name, model_tokens, prediction_tokens)


@router.get("/getPrediction", response_model=None)
async def get_prediction(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_name: str = Query(...),
    model_name: str = Query(...),
) -> dict[str, Any] | HTMLResponse:
    """Obtain predictions for a specific task and model"""
    prediction = await PredictionRepository.get(task_name, model_name)

    if prediction is None:
        raise HTTPException(status_code=404, detail="Prediction not found")

    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "predictions": prediction.predictions,
        }

    return templates.TemplateResponse(
        request,
        "get_prediction.html",
        {
            "title": "Prediction Details",
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "prediction": {"predictions": prediction.predictions},
            "user": current_user,
        },
    )


@router.get("/getDangerousFunctions", response_model=None)
async def get_dangerous_functions_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> HTMLResponse:
    """Loads the dangerous function scanner page."""
    return templates.TemplateResponse(
        request,
        "get_dangerous_functions.html",
        {"title": "Glyph - Dangerous Function Scanner", "user": current_user},
    )


@router.get("/login", response_model=None)
async def login_page(
    request: Request, current_user: Annotated[User | None, Depends(get_optional_user)]
) -> HTMLResponse | RedirectResponse:
    """
    Loads the login page
    """
    if current_user:
        return RedirectResponse(url="/")

    return templates.TemplateResponse(request, "login.html", {"title": "Glyph - Login", "user": current_user})


@router.post("/login", response_model=None)
@limiter.limit(LOGIN_LIMIT)  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator]
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
) -> RedirectResponse | HTMLResponse:
    """
    Handles login form submission (POST).
    """
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))

    user_repo = UserRepository(db)
    user = await user_repo.verify_credentials(username, password)

    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "Glyph - Login", "user": None, "login_error": "Incorrect username or password"},
        )

    if not user.is_active:
        return templates.TemplateResponse(
            request, "login.html", {"title": "Glyph - Login", "user": None, "login_error": "User account is disabled"}
        )

    access_token = jwt_handler.create_access_token(str(user.id))
    refresh_token = jwt_handler.create_refresh_token(str(user.id))

    settings = get_settings()
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        secure=settings.use_https,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token_cookie",
        value=refresh_token,
        httponly=True,
        secure=settings.use_https,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )

    return response


@router.get("/register", response_model=None)
async def register_page(
    request: Request, current_user: Annotated[User | None, Depends(get_optional_user)]
) -> HTMLResponse | RedirectResponse:
    """
    Loads the registration page
    """
    if current_user:
        return RedirectResponse(url="/")

    return templates.TemplateResponse(request, "register.html", {"title": "Glyph - Register", "user": current_user})


@router.post("/register", response_model=None)
@limiter.limit(REGISTER_LIMIT)  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator]
async def register_submit(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> RedirectResponse | HTMLResponse:
    """
    Handles registration form submission (POST).
    """
    from app.auth.security_logger import log_user_registration
    from app.auth.schemas import UserRegister

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    # Validate form data using UserRegister schema for consistent validation.
    try:
        user_data = UserRegister(
            username=body.get("username", ""),
            email=body.get("email", ""),
            password=body.get("password", ""),
            full_name=body.get("full_name") or None,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"title": "Glyph - Register", "user": None, "register_error": str(exc)},
        )

    username = user_data.username
    email = user_data.email
    password = user_data.password
    full_name = user_data.full_name

    user_repo = UserRepository(db)

    try:
        existing_user = await user_repo.get_by_username(username)
        if existing_user:
            return templates.TemplateResponse(
                request,
                "register.html",
                {"title": "Glyph - Register", "user": None, "register_error": "Username already registered"},
            )

        existing_email = await user_repo.get_by_email(email)
        if existing_email:
            return templates.TemplateResponse(
                request,
                "register.html",
                {"title": "Glyph - Register", "user": None, "register_error": "Email already registered"},
            )

        user = await user_repo.create_user(
            username=username, email=email, password=password, full_name=full_name or None, permissions=["read"]
        )
    except exc.IntegrityError:
        await db.rollback()
        return templates.TemplateResponse(
            request,
            "register.html",
            {"title": "Glyph - Register", "user": None, "register_error": "Username or email already registered"},
        )

    ip_address = request.client.host if request.client else None
    log_user_registration(user_id=user.id, username=username, ip_address=ip_address)

    return RedirectResponse(url="/login", status_code=303)


@router.get("/profile")
async def profile_page(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
) -> HTMLResponse:
    """
    Loads the user profile page
    """
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "title": "Glyph - Profile",
            "user": {
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "created_at": current_user.created_at,
            },
        },
    )


@router.get("/binary-library")
async def binary_library_page(
    request: Request, current_user: Annotated[User, Depends(get_current_active_user)]
) -> HTMLResponse:
    """
    Loads the binary library page for managing uploaded binaries.
    """
    return templates.TemplateResponse(
        request,
        "binary_library.html",
        {"title": "Glyph - Binary Library", "user": current_user},
    )


@router.get("/binary/{binary_id}")
async def binary_detail_page(
    request: Request, binary_id: int, current_user: Annotated[User, Depends(get_current_active_user)]
) -> HTMLResponse:
    """
    Loads the binary detail page showing functions and metadata for a specific binary.
    """
    return templates.TemplateResponse(
        request,
        "binary_detail.html",
        {
            "title": "Glyph - Binary Details",
            "binary_id": binary_id,
            "user": current_user,
        },
    )


@router.get("/run-task")
async def run_task_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_id: int = Query(...),
    binary_name: str = Query(...),
) -> HTMLResponse:
    """
    Loads the task execution page for a given binary.
    """
    models: list[str] = list(await ModelRepository.get_models_list())
    return templates.TemplateResponse(
        request,
        "run_task.html",
        {
            "title": "Glyph - Run Task",
            "binary_id": binary_id,
            "binary_name": binary_name,
            "models": models,
            "user": current_user,
        },
    )


@router.get("/create-model")
async def create_model_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_id: int | None = Query(None),
) -> HTMLResponse:
    """
    Loads the create model page for training ML models from uploaded binaries.
    Optionally pre-selects a binary via the binary_id query parameter.
    """
    return templates.TemplateResponse(
        request,
        "create_model.html",
        {"title": "Glyph - Create Model", "binary_id": binary_id, "user": current_user},
    )


@router.get("/create-prediction")
async def create_prediction_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_id: int | None = Query(None),
) -> HTMLResponse:
    """
    Loads the create prediction page for running ML predictions on uploaded binaries.
    Optionally pre-selects a binary via the binary_id query parameter.
    """
    return templates.TemplateResponse(
        request,
        "create_prediction.html",
        {"title": "Glyph - Create Prediction", "binary_id": binary_id, "user": current_user},
    )


@router.get("/task-results")
async def task_results_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_uuid: str = Query(...),
) -> HTMLResponse:
    """
    Loads the task results page for a given task UUID.
    """
    return templates.TemplateResponse(
        request,
        "task_results.html",
        {"title": "Glyph - Task Results", "task_uuid": task_uuid, "user": current_user},
    )


@router.get("/similarity-dashboard")
async def similarity_dashboard_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> HTMLResponse:
    """
    Loads the binary similarity dashboard page.
    """
    return templates.TemplateResponse(
        request,
        "similarity_dashboard.html",
        {"title": "Glyph - Similarity Dashboard", "user": current_user},
    )
