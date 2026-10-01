"""Model management endpoints for Glyph API v1.

Provides endpoints for retrieving, listing, and deleting ML models,
as well as accessing function details and prediction information.
"""

import types
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.api.types import FunctionName, ModelName, TaskName
from app.auth.dependencies import assert_owned, can_access, get_current_active_user
from app.database.function_repository import FunctionRepository
from app.database.model_repository import ModelRepository
from app.database.models import User
from app.database.prediction_repository import PredictionRepository
from app.services.prediction_service import PredictionService
from app.utils.common import build_prediction_details_response, format_code
from app.utils.logging_utils import catch_http_exception
from app.utils.responses import SuccessResponse, create_error_response, create_success_response

router = APIRouter()


@router.delete(
    "/deleteModel",
    summary="Delete a model",
    description="Delete a trained ML model by name and all associated predictions.",
)
@catch_http_exception(status_code=500, error_code="DELETE_MODEL_ERROR", message="Failed to delete model")
async def delete_model(
    current_user: Annotated[User, Depends(get_current_active_user)], model_name: Annotated[ModelName, Query()],
) -> SuccessResponse[dict[str, Any]]:
    """Delete a trained ML model by name and all associated predictions."""
    model_row = await ModelRepository.get(model_name)
    if model_row is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="MODEL_NOT_FOUND", error_message="Model not found",
            ).model_dump(),
        )
    assert_owned(model_row, current_user, "model")
    await ModelRepository.delete(model_name)
    await PredictionService.delete_predictions_for_model(model_name)
    return create_success_response(data={}, message="Model deleted successfully")


@router.delete(
    "/deleteModels",
    summary="Delete multiple models",
    description="Delete multiple trained ML models by comma-separated names.",
)
@catch_http_exception(status_code=500, error_code="DELETE_MODELS_ERROR", message="Failed to delete models")
async def delete_models(
    current_user: Annotated[User, Depends(get_current_active_user)], model_names: Annotated[str, Query()],
) -> SuccessResponse[dict[str, Any]]:
    """Delete multiple trained ML models by comma-separated names."""
    names = [name.strip() for name in model_names.split(",") if name.strip()]
    if not names:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_MODEL_NAMES", error_message="At least one model name must be provided",
            ).model_dump(),
        )
    if len(names) > 100:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="TOO_MANY_MODELS",
                error_message="At most 100 model names may be deleted per request",
            ).model_dump(),
        )

    deleted: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            model_row = await ModelRepository.get(name)
            if model_row is None or not can_access(model_row, current_user):
                # Missing or owned by another user: skip (do not leak existence).
                failed.append(name)
                continue
            await ModelRepository.delete(name)
            await PredictionService.delete_predictions_for_model(name)
            deleted.append(name)
        except Exception as exc:
            logger.warning("Failed to delete model '%s': %s", name, exc)
            failed.append(name)

    data = {"deleted": deleted, "failed": failed}
    message = f"Deleted {len(deleted)} model(s)"
    if failed:
        message += f"; failed to delete {len(failed)}: {', '.join(failed)}"

    return create_success_response(data=data, message=message)


@router.get(
    "/getFunction",
    response_model=None,
    summary="Get a single function",
    description="Get decompiled code for a single function from a model.",
)
async def get_function(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: Annotated[ModelName, Query()],
    function_name: Annotated[FunctionName, Query()],
) -> SuccessResponse[dict[str, Any]]:
    """Get decompiled code for a single function from a model."""
    if not model_name or not model_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_MODEL_NAME", error_message="model_name must be a non-empty string",
            ).model_dump(),
        )
    if not function_name or not function_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_FUNCTION_NAME", error_message="function_name must be a non-empty string",
            ).model_dump(),
        )

    function_information = await FunctionRepository.get(model_name.strip(), function_name.strip())

    if function_information is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="FUNCTION_NOT_FOUND", error_message="Function not found",
            ).model_dump(),
        )

    assert_owned(function_information, current_user, "function")

    f_name = function_information.function_name
    f_entry = function_information.entrypoint

    return create_success_response(
        data={
            "id": function_information.id,
            "function_name": f_name,
            "entrypoint": f_entry,
            "tokens": function_information.tokens,
        },
        message="Function retrieved successfully",
    )


@router.get(
    "/getFunctions",
    response_model=None,
    summary="List model functions",
    description="List all extracted functions for a trained model.",
)
async def get_functions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: Annotated[ModelName, Query()],
) -> SuccessResponse[dict[str, Any]]:
    """List all extracted functions for a trained model."""
    functions = await FunctionRepository.get_functions(model_name)
    # Scope to rows the current user may access (own + legacy/unowned).
    functions = [f for f in functions if can_access(f, current_user)]

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
            ],
        },
        message="Functions retrieved successfully",
    )


@router.get(
    "/getPredictionDetails",
    response_model=None,
    summary="Get prediction details",
    description="Get detailed prediction results for a specific function, comparing model and prediction tokens.",
)
async def get_prediction_details(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: Annotated[ModelName, Query()],
    function_name: Annotated[FunctionName, Query()],
    task_name: Annotated[TaskName, Query()],
) -> SuccessResponse[dict[str, Any]]:
    """Get detailed prediction results for a specific function, comparing model and prediction tokens."""
    try:
        # Enforce prediction ownership before exposing any prediction data.
        pred_owner_id = await PredictionRepository.get_owner(task_name, model_name)
        assert_owned(types.SimpleNamespace(user_id=pred_owner_id), current_user, "prediction")

        model_info = await FunctionRepository.get(model_name, function_name)
        prediction_data = await PredictionRepository.get_prediction_function(task_name, model_name, function_name)

        if not prediction_data:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="PREDICTION_NOT_FOUND", error_message="Prediction not found",
                ).model_dump(),
            )

        # Model function lookup is optional - the binary may not have been used
        # during model training, so the function may not exist in the functions DB.
        if model_info is not None:
            model_tokens = format_code(model_info.tokens)
        else:
            model_tokens = "Model function not found (binary was not used during training)"
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except HTTPException:
        raise
    except (TypeError, IndexError, KeyError):
        logger.exception("Failed to retrieve prediction details")
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="RETRIEVAL_ERROR", error_message="Could not retrieve details",
            ).model_dump(),
        )

    return create_success_response(
        data=build_prediction_details_response(task_name, model_name, function_name, model_tokens, prediction_tokens),
        message="Prediction details retrieved successfully",
    )
