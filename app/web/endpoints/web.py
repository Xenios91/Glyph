from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

import app._version as _version
from app.config.settings import MAX_CPU_CORES, get_settings
from app.utils.helpers import ACCEPT_TYPE
from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil, PredictionPersistanceUtil
from app.processing.task_management import TaskManager
from app.utils.common import format_code, build_prediction_details_response
from app.templates import templates  # Shared Jinja2Templates instance
from loguru import logger
from app.auth.dependencies import get_current_active_user, get_optional_user, get_db, get_jwt_handler
from app.core.rate_limiter import limiter, REGISTER_LIMIT
from app.auth.jwt_handler import JWTHandler
from app.database.repository import UserRepository
from app.database.models import User


router = APIRouter()


@router.get("/", response_model=None)
async def home(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> Union[JSONResponse, HTMLResponse]:
    """
    Loads the homepage of Glyph
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(content={"version": _version.__version__})

    return templates.TemplateResponse(
        request,
        "main.html",
        {"title": "Glyph", "user": current_user}
    )


@router.get("/config")
async def config(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> HTMLResponse:
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
        })


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

    return templates.TemplateResponse(
        request,
        "error.html", {"title": "Glyph - Error", "message": message}
    )


@router.get("/uploadBinary", response_model=None)
async def get_upload_binary(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> Union[JSONResponse, HTMLResponse]:
    """
    Handles GET request to load the upload webpage
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(
            content={"error": "API calls can only be POST"}, status_code=200
        )

    models: set[str] = await MLPersistanceUtil.get_models_list()
    allow_prediction = len(models) > 0
    return templates.TemplateResponse(
        request,
        "upload.html",
        {"title": "Glyph - Upload Binary", "allow_prediction": allow_prediction, "models": models, "user": current_user})


@router.get("/getModels", response_model=None)
async def get_list_models(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> Union[dict[str, list[str]], HTMLResponse]:
    """
    Handles a GET request to obtain all models available
    """
    models: set[str] = await MLPersistanceUtil.get_models_list()
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"models": list(models)}

    models_status: dict[str, str] = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"

    return templates.TemplateResponse(
        request,
        "get_models.html",
        {"title": "Models List", "models": models_status, "user": current_user})


@router.get("/getPredictions", response_model=None)
async def get_list_predictions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> Union[dict[str, list[dict[str, Any]]], HTMLResponse]:
    """Obtain all predictions available"""
    predictions = await PredictionPersistanceUtil.get_predictions_list()
    
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"predictions": [p.__dict__ for p in predictions]}

    return templates.TemplateResponse(
        request,
        "get_predictions.html",
        {"title": "Predictions List", "predictions": predictions, "user": current_user})


@router.get("/getPredictionDetails", response_model=None)
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: str = Query(...),
    function_name: str = Query(...),
    task_name: str = Query(...)
) -> Union[dict[str, str], HTMLResponse]:
    """Displays specific details of a prediction"""
    model_name = model_name.strip()
    func_name = function_name.strip()
    task_name = task_name.strip()

    try:
        model_info = await FunctionPersistanceUtil.get_function(model_name, func_name)
        prediction_data = await FunctionPersistanceUtil.get_prediction_function(
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
            })

    return build_prediction_details_response(
        task_name, model_name, func_name, model_tokens, prediction_tokens
    )


@router.get("/getPrediction", response_model=None)
async def get_prediction(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_name: str = Query(...),
    model_name: str = Query(...)
) -> Union[dict[str, Any], HTMLResponse]:
    """Obtain predictions for a specific task and model"""
    prediction = await PredictionPersistanceUtil.get_predictions(task_name, model_name)
    
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
            "predictions": prediction.predictions
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
        })


@router.get("/login", response_model=None)
async def login_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_user)]
) -> Union[HTMLResponse, RedirectResponse]:
    """
    Loads the login page
    """
    # Redirect to home if already logged in
    if current_user:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Glyph - Login", "user": current_user})


@router.post("/login", response_model=None)
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)]
) -> Union[RedirectResponse, HTMLResponse]:
    """
    Handles login form submission (POST).
    """
    # Handle both JSON and form-urlencoded submissions
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
            {"title": "Glyph - Login", "user": None, "login_error": "Incorrect username or password"}
        )

    if not user.is_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "Glyph - Login", "user": None, "login_error": "User account is disabled"}
        )

    # Generate tokens using existing JWT handler dependency
    access_token = jwt_handler.create_access_token(str(user.id))
    refresh_token = jwt_handler.create_refresh_token(str(user.id))

    # Use same cookie names as /auth/token endpoint so auth dependency can find them
    settings = get_settings()
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        secure=settings.use_https,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60
    )
    response.set_cookie(
        key="refresh_token_cookie",
        value=refresh_token,
        httponly=True,
        secure=settings.use_https,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60
    )

    return response


@router.get("/register", response_model=None)
async def register_page(
    request: Request,
    current_user: Annotated[User | None, Depends(get_optional_user)]
) -> Union[HTMLResponse, RedirectResponse]:
    """
    Loads the registration page
    """
    # Redirect to home if already logged in
    if current_user:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse(
        request,
        "register.html",
        {"title": "Glyph - Register", "user": current_user})


@router.post("/register", response_model=None)
@limiter.limit(REGISTER_LIMIT)
async def register_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Union[RedirectResponse, HTMLResponse]:
    """
    Handles registration form submission (POST).
    """
    from app.auth.security_logger import log_user_registration

    # Handle both JSON and form-urlencoded submissions
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    username = str(body.get("username", ""))
    email = str(body.get("email", ""))
    password = str(body.get("password", ""))
    full_name = str(body.get("full_name", ""))

    user_repo = UserRepository(db)

    # Check if username exists
    existing_user = await user_repo.get_by_username(username)
    if existing_user:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"title": "Glyph - Register", "user": None, "register_error": "Username already registered"}
        )

    # Check if email exists
    existing_email = await user_repo.get_by_email(email)
    if existing_email:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"title": "Glyph - Register", "user": None, "register_error": "Email already registered"}
        )

    # Create user with default permissions
    user = await user_repo.create_user(
        username=username,
        email=email,
        password=password,
        full_name=full_name or None,
        permissions=["read"]
    )

    # Log user registration
    ip_address = request.client.host if request.client else None
    log_user_registration(
        user_id=user.id,
        username=username,
        ip_address=ip_address
    )

    return RedirectResponse(url="/login", status_code=303)


@router.get("/profile")
async def profile_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)]
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
                "created_at": current_user.created_at
            }
        })
