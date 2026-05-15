"""Model management endpoints for Glyph API.

This module provides endpoints for managing machine learning models,
including retrieving model information and function predictions.
"""

from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.responses import HTMLResponse

from app.api.types import ModelName, FunctionName, TaskName
from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.utils.persistence_util import (
    FunctionPersistanceUtil,
    MLPersistanceUtil,
    PredictionPersistanceUtil)
from app.utils.helpers import ACCEPT_TYPE
from app.utils.common import format_code, build_prediction_details_response
from loguru import logger
from app.utils.responses import (
    create_success_response,
    create_error_response,
    SuccessResponse)
from app.templates import templates  # Shared Jinja2Templates instance
from app.utils.logging_utils import catch_http_exception


router = APIRouter()


@router.delete("/deleteModel", response_model=SuccessResponse[dict[str, Any]])
@catch_http_exception(status_code=500, error_code="DELETE_MODEL_ERROR", message="Failed to delete model")
async def delete_model(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    """
    Handles a DELETE request to delete a supplied model by name.

    Args:
        model_name: The name of the model to delete (automatically validated and stripped).

    Returns:
        Success response when model is deleted.
    """
    await MLPersistanceUtil.delete_model(model_name)
    await PredictionPersistanceUtil.delete_model_predictions(model_name)
    return create_success_response(
        data={},
        message="Model deleted successfully")


@router.delete("/deleteModels", response_model=SuccessResponse[dict[str, Any]])
@catch_http_exception(status_code=500, error_code="DELETE_MODELS_ERROR", message="Failed to delete models")
async def delete_models(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_names: str = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    """
    Handles a DELETE request to delete multiple models by name.

    Args:
        model_names: Comma-separated list of model names to delete.

    Returns:
        Success response when models are deleted.
    """
    names = [name.strip() for name in model_names.split(",") if name.strip()]
    if not names:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_MODEL_NAMES",
                error_message="At least one model name must be provided").model_dump())
    
    deleted: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            await MLPersistanceUtil.delete_model(name)
            await PredictionPersistanceUtil.delete_model_predictions(name)
            deleted.append(name)
        except Exception as exc:
            logger.warning("Failed to delete model '%s': %s", name, exc)
            failed.append(name)
    
    data = {"deleted": deleted, "failed": failed}
    message = f"Deleted {len(deleted)} model(s)"
    if failed:
        message += f"; failed to delete {len(failed)}: {', '.join(failed)}"
    
    return create_success_response(data=data, message=message)


@router.get("/getFunction", response_model=None)
async def get_function(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...)
) -> Union[SuccessResponse[dict[str, Any]], HTMLResponse]:
    """
    Handles a GET request to return a specific function associated with a model.

    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).
        function_name: The name of the function (automatically validated and stripped).

    Returns:
        Function information or HTML template response.

    Raises:
        HTTPException: If function is not found or inputs are invalid.
    """
    # Validate inputs before persistence layer call
    if not model_name or not model_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="model_name must be a non-empty string").model_dump())
    if not function_name or not function_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_FUNCTION_NAME",
                error_message="function_name must be a non-empty string").model_dump())

    function_information = await FunctionPersistanceUtil.get_function(
        model_name.strip(), function_name.strip()
    )

    if function_information is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="FUNCTION_NOT_FOUND",
                error_message="Function not found").model_dump())

    f_name = function_information.function_name
    f_entry = function_information.entrypoint
    f_tokens = format_code(function_information.tokens)

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "get_function.html",
            {
                "title": f"Glyph - Function: {f_name}",
                "model_name": model_name,
                "function_name": f_name,
                "function_entry": f_entry,
                "tokens": f_tokens,
                "user": current_user,
            })

    return create_success_response(
        data={
            "id": function_information.id,
            "function_name": f_name,
            "entrypoint": f_entry,
            "tokens": function_information.tokens,
        },
        message="Function retrieved successfully")


@router.get("/getFunctions", response_model=None)
async def get_functions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...)
) -> Union[SuccessResponse[dict[str, Any]], HTMLResponse]:
    """
    Handles a GET request to return all identified functions associated with a model.

    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).

    Returns:
        List of functions or HTML template response.
    """
    functions = await FunctionPersistanceUtil.get_functions(model_name)

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "get_symbols.html",
            {
                "title": f"Glyph - Model: {model_name}",
                "bin_name": "test",
                "model_name": model_name,
                "functions": functions,
                "user": current_user,
            })

    return create_success_response(
        data={
            "functions": [
                {
                    "id": f.id,
                    "function_name": f.function_name,
                    "entrypoint": f.entrypoint,
                    "tokens": f.tokens,
                }
                for f in functions
            ]
        },
        message="Functions retrieved successfully")


@router.get("/getPredictionDetails", response_model=None)
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
    task_name: TaskName = Query(...)
) -> Union[SuccessResponse[dict[str, Any]], HTMLResponse]:
    """Displays specific details of a prediction.

    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).
        function_name: The name of the function (automatically validated and stripped).
        task_name: The name of the task (automatically validated and stripped).

    Returns:
        Prediction details or HTML template response.

    Raises:
        HTTPException: If function or prediction is not found.
    """
    try:
        model_info = await FunctionPersistanceUtil.get_function(model_name, function_name)
        prediction_data = await FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, function_name
        )

        if model_info is None:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="FUNCTION_NOT_FOUND",
                    error_message="Function not found in model").model_dump())
        if not prediction_data:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="PREDICTION_NOT_FOUND",
                    error_message="Prediction not found").model_dump())

        model_tokens = format_code(model_info.tokens)
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except (TypeError, IndexError, KeyError):
        logger.exception("Failed to retrieve prediction details")
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="RETRIEVAL_ERROR",
                error_message="Could not retrieve details").model_dump())

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "prediction_function_details.html",
            {
                "title": f"Glyph - Prediction: {function_name}",
                "task_name": task_name,
                "model_name": model_name,
                "function_name": function_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
                "user": current_user,
            })

    return create_success_response(
        data=build_prediction_details_response(
            task_name, model_name, function_name, model_tokens, prediction_tokens
        ),
        message="Prediction details retrieved successfully")
