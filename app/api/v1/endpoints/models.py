"""Model management endpoints for Glyph API.

This module provides endpoints for managing machine learning models,
including retrieving model information and function predictions.
"""

import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates


from app.utils.persistence_util import (
    FunctionPersistanceUtil,
    MLPersistanceUtil,
    PredictionPersistanceUtil,
)
from app.utils.helpers import ACCEPT_TYPE
from app.utils.common import format_code, build_prediction_details_response
from app.utils.responses import create_success_response, create_error_response

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.delete("/deleteModel")
async def delete_model(modelName: str = Query(...)):
    """
    Handles a DELETE request to delete a supplied model by name
    """
    model_name = modelName.strip()

    if not model_name:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="invalid model name",
            ).model_dump(),
            status_code=400,
        )

    try:
        MLPersistanceUtil.delete_model(model_name)
        PredictionPersistanceUtil.delete_model_predictions(model_name)
        return JSONResponse(
            content=create_success_response(
                data={},
                message="Model deleted successfully",
            ).model_dump(),
            status_code=200,
        )
    except Exception as exc:
        logging.error("Failed to delete model '%s': %s", model_name, exc)
        return JSONResponse(
            content=create_success_response(
                data={},
                message="Model deleted successfully",
            ).model_dump(),
            status_code=200,
        )


@router.get("/getFunction")
async def get_function(
    request: Request, modelName: str = Query(...), functionName: str = Query(...)
):
    """
    Handles a GET request to return a specific function associated with a model
    """
    model_name = modelName.strip()
    func_name_query = functionName.strip()

    if not model_name or not func_name_query:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_REQUEST",
                error_message="invalid model or function name",
            ).model_dump(),
            status_code=400,
        )

    function_information: dict = FunctionPersistanceUtil.get_function(
        model_name, func_name_query
    )

    if not function_information:
        return JSONResponse(
            content=create_error_response(
                error_code="FUNCTION_NOT_FOUND",
                error_message="Function not found",
            ).model_dump(),
            status_code=404,
        )

    f_name = function_information[1]
    f_entry = function_information[2]
    f_tokens = format_code(function_information[3])

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(
            content=create_success_response(
                data={"functions": function_information},
                message="Function retrieved successfully",
            ).model_dump(),
            status_code=200,
        )

    return templates.TemplateResponse(
        "get_function.html",
        {
            "request": request,
            "model_name": model_name,
            "function_name": f_name,
            "function_entry": f_entry,
            "tokens": f_tokens,
        },
    )


@router.get("/getFunctions")
async def get_functions(request: Request, modelName: str = Query(...)):
    """
    Handles a GET request to return all identified functions associated with a model
    """
    model_name = modelName.strip()

    if not model_name:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="invalid model name",
            ).model_dump(),
            status_code=400,
        )

    functions: list = FunctionPersistanceUtil.get_functions(model_name)

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(
            content=create_success_response(
                data={"functions": functions},
                message="Functions retrieved successfully",
            ).model_dump(),
            status_code=200,
        )

    return templates.TemplateResponse(
        "get_symbols.html",
        {
            "request": request,
            "bin_name": "test",
            "model_name": model_name,
            "functions": functions,
        },
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
            return JSONResponse(
                content=create_error_response(
                    error_code="FUNCTION_NOT_FOUND",
                    error_message="Function not found in model",
                ).model_dump(),
                status_code=404,
            )
        if not prediction_data:
            return JSONResponse(
                content=create_error_response(
                    error_code="PREDICTION_NOT_FOUND",
                    error_message="Prediction not found",
                ).model_dump(),
                status_code=404,
            )

        # model_info is a dict with keys: model_name, function_name, entrypoint, tokens
        model_tokens = format_code(model_info.get("tokens", ""))
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except (TypeError, IndexError, KeyError) as exc:
        logging.error("Failed to retrieve prediction details: %s", exc)
        return JSONResponse(
            content=create_error_response(
                error_code="RETRIEVAL_ERROR",
                error_message="Could not retrieve details",
            ).model_dump(),
            status_code=400,
        )

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

    return JSONResponse(
        content=create_success_response(
            data=build_prediction_details_response(
                task_name, model_name, func_name, model_tokens, prediction_tokens
            ),
            message="Prediction details retrieved successfully",
        ).model_dump(),
        status_code=200,
    )
