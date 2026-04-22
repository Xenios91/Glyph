"""Model management endpoints for Glyph API.

This module provides endpoints for managing machine learning models,
including retrieving model information and function predictions.
"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.templating import Jinja2Templates


from app.api.types import ModelName, FunctionName, TaskName
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.database.models import User
from app.utils.persistence_util import (
    FunctionPersistanceUtil,
    MLPersistanceUtil,
    PredictionPersistanceUtil,
)
from app.utils.helpers import ACCEPT_TYPE
from app.utils.common import format_code, build_prediction_details_response
from app.utils.responses import (
    create_success_response,
    create_error_response,
    SuccessResponse,
)
from app.utils.jinja_utils import configure_jinja2_templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)


@router.delete("/deleteModel", response_model=SuccessResponse[dict])
async def delete_model(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
):
    """
    Handles a DELETE request to delete a supplied model by name.

    Args:
        model_name: The name of the model to delete (automatically validated and stripped).

    Returns:
        Success response when model is deleted.
    """
    try:
        MLPersistanceUtil.delete_model(model_name)
        PredictionPersistanceUtil.delete_model_predictions(model_name)
        return create_success_response(
            data={},
            message="Model deleted successfully",
        )
    except Exception as exc:
        logging.error("Failed to delete model '%s': %s", model_name, exc)
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code="DELETE_MODEL_ERROR",
                error_message=f"Failed to delete model: {exc}",
            ).model_dump(),
        )


@router.get("/getFunction", response_model=SuccessResponse[dict])
async def get_function(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
):
    """
    Handles a GET request to return a specific function associated with a model.

    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).
        function_name: The name of the function (automatically validated and stripped).

    Returns:
        Function information or HTML template response.

    Raises:
        HTTPException: If function is not found.
    """
    function_information: list = FunctionPersistanceUtil.get_function(
        model_name, function_name
    )

    if not function_information:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="FUNCTION_NOT_FOUND",
                error_message="Function not found",
            ).model_dump(),
        )

    f_name = function_information[1]
    f_entry = function_information[2]
    f_tokens = format_code(function_information[3])

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return create_success_response(
            data={"functions": function_information},
            message="Function retrieved successfully",
        )

    return templates.TemplateResponse(
        "get_function.html",
        {
            "request": request,
            "model_name": model_name,
            "function_name": f_name,
            "function_entry": f_entry,
            "tokens": f_tokens,
            "user": current_user,
        },
    )


@router.get("/getFunctions", response_model=SuccessResponse[dict])
async def get_functions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
):
    """
    Handles a GET request to return all identified functions associated with a model.

    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).

    Returns:
        List of functions or HTML template response.
    """
    functions: list = FunctionPersistanceUtil.get_functions(model_name)

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return create_success_response(
            data={"functions": functions},
            message="Functions retrieved successfully",
        )

    return templates.TemplateResponse(
        "get_symbols.html",
        {
            "request": request,
            "bin_name": "test",
            "model_name": model_name,
            "functions": functions,
            "user": current_user,
        },
    )


@router.get("/getPredictionDetails", response_model=SuccessResponse[dict])
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
    task_name: TaskName = Query(...),
):
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
        model_info = FunctionPersistanceUtil.get_function(model_name, function_name)
        prediction_data = FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, function_name
        )

        if not model_info:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="FUNCTION_NOT_FOUND",
                    error_message="Function not found in model",
                ).model_dump(),
            )
        if not prediction_data:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="PREDICTION_NOT_FOUND",
                    error_message="Prediction not found",
                ).model_dump(),
            )

        model_tokens = format_code(model_info[3] if len(model_info) >= 3 else "")
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except (TypeError, IndexError, KeyError) as exc:
        logging.error("Failed to retrieve prediction details: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="RETRIEVAL_ERROR",
                error_message="Could not retrieve details",
            ).model_dump(),
        )

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        logging.debug("API getPredictionDetails: Returning HTML template")
        logging.debug("API getPredictionDetails: current_user=%s", current_user)
        logging.debug("API getPredictionDetails: current_user.username=%s", current_user.username if current_user else None)
        return templates.TemplateResponse(
            "prediction_function_details.html",
            {
                "request": request,
                "task_name": task_name,
                "model_name": model_name,
                "function_name": function_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
                "user": current_user,
            },
        )

    return create_success_response(
        data=build_prediction_details_response(
            task_name, model_name, function_name, model_tokens, prediction_tokens
        ),
        message="Prediction details retrieved successfully",
    )
