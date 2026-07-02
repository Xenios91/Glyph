"""Prediction endpoints for Glyph API v1.

Provides endpoints for submitting prediction requests, retrieving
prediction results, and managing prediction tasks.

Pure JSON API endpoints -- HTML responses are handled by web endpoints
in app/web/endpoints/web.py.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from loguru import logger
from markupsafe import escape
from pydantic import BaseModel

from app.api.types import FunctionName, ModelName, TaskName
from app.auth.dependencies import get_current_active_user
from app.database.function_repository import FunctionRepository
from app.database.models import User
from app.database.prediction_repository import PredictionRepository
from app.processing.task_management import TaskManager
from app.services.prediction_service import PredictionService
from app.services.request_handler import PredictionRequest
from app.utils.common import format_code
from app.utils.logging_utils import catch_http_exception
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    clear_request_context,
    restore_request_context,
)
from app.utils.responses import (
    PaginatedResponse,
    SuccessResponse,
    create_error_response,
    create_paginated_response,
    create_success_response,
)

router = APIRouter()


class PredictTokensRequest(BaseModel):
    """Request schema for submitting a prediction task.

    Attributes:
        modelName: Name of the trained model to use for prediction.
        taskName: Name of the task (binary) to predict on.
        uuid: Optional custom UUID for the prediction task.
    """

    modelName: str
    taskName: str
    uuid: str | None = None

    model_config = {"extra": "forbid"}


async def _execute_prediction(
    prediction_request: PredictionRequest,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the prediction pipeline and persist results.

    Runs tokenization, filtering, feature extraction, and prediction
    steps using the ProcessingPipeline framework, then saves the
    predictions to the database.

    Args:
        prediction_request: The prediction request containing functions to analyze.
        captured_ctx: Captured request context for logging propagation.
    """
    if captured_ctx is not None:
        restore_request_context(captured_ctx, override_task_id=prediction_request.uuid)

    from app.processing.pipeline import PipelineContext
    from app.processing.pipeline_configs import ML_PREDICTION_ONLY_PIPELINE

    functions = prediction_request.get_functions()

    context = PipelineContext(
        uuid=prediction_request.uuid,
        binary_path="",
        pipeline_type="ml_prediction",
        metadata={
            "model_name": prediction_request.model_name,
            "task_name": prediction_request.task_name,
        },
    )

    context.set("functions", functions)

    result = await ML_PREDICTION_ONLY_PIPELINE.execute(context)

    if result.error:
        raise RuntimeError(result.error)

    # Persist prediction results to the database
    predictions = result.get("predictions")
    if predictions:
        await _save_prediction_functions(prediction_request, predictions)
        logger.info(
            "Prediction task completed and saved: {} ({} predictions)",
            prediction_request.uuid,
            len(predictions),
        )
    else:
        logger.warning(
            "Prediction task completed but no predictions to save: {}",
            prediction_request.uuid,
        )


async def _save_prediction_functions(prediction_request: PredictionRequest, predictions: list[str]) -> None:
    """Merge predictions with functions and persist to database.

    Args:
        prediction_request: The prediction request containing functions.
        predictions: List of predicted labels.
    """
    functions: list[dict[str, Any]] = prediction_request.get_functions() or []
    task_name = prediction_request.task_name

    if functions and len(functions) == len(predictions):
        for ctr, function in enumerate(functions):
            updated_function = function.copy()
            updated_function["prediction"] = predictions[ctr]
            functions[ctr] = updated_function
        await PredictionRepository.save(task_name, prediction_request.model_name, functions)
    elif functions:
        logger.warning(
            "Mismatch between functions ({}) and predictions ({}) for task '{}'",
            len(functions),
            len(predictions),
            task_name,
        )


async def _run_prediction_task(
    prediction_request: PredictionRequest,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the prediction pipeline for a given request.

    Runs tokenization, filtering, feature extraction, and prediction
    steps using the ProcessingPipeline framework, then persists the
    results to the database.

    Args:
        prediction_request: The prediction request containing functions to analyze.
        captured_ctx: Captured request context for logging propagation.
    """
    try:
        await _execute_prediction(prediction_request, captured_ctx)
    except Exception:
        logger.exception("Prediction task failed: {}", prediction_request.uuid)
        raise
    finally:
        clear_request_context()


@router.post(
    "/predict",
    status_code=201,
    response_model=SuccessResponse[dict[str, Any]],
    summary="Create a prediction task",
    description="Run a prediction on a binary using a trained ML model. Queues the prediction as a background task.",
)
@catch_http_exception(status_code=400, error_code="PREDICTION_ERROR")
async def predict_tokens(
    background_tasks: BackgroundTasks,
    request_values: PredictTokensRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Run a prediction on a binary using a trained ML model."""
    model_name = request_values.modelName
    uuid = request_values.uuid or TaskManager().get_uuid()
    data = request_values.model_dump()
    task_name = data.get("taskName", "")

    if not task_name or not task_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="TASK_NAME_REQUIRED", error_message="taskName is required for predictions"
            ).model_dump(),
        )
    task_name = task_name.strip()

    if await PredictionService.check_task_name_unique(task_name):
        raise HTTPException(
            status_code=409,
            detail=create_error_response(
                error_code="TASK_NAME_EXISTS",
                error_message=f"Task name '{task_name}' already exists. Task names must be unique.",
            ).model_dump(),
        )

    prediction_request = PredictionRequest(uuid, model_name, data)
    captured_ctx = capture_request_context()
    background_tasks.add_task(_run_prediction_task, prediction_request, captured_ctx)

    return create_success_response(
        data={"uuid": prediction_request.uuid}, message="Prediction task created successfully"
    )


@router.get("/getPredictionsList", response_model=SuccessResponse[PaginatedResponse[dict[str, Any]]])
async def get_predictions_list(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> SuccessResponse[PaginatedResponse[dict[str, Any]]]:
    """Get a paginated list of all predictions.

    Returns:
        Success response with a paginated list of prediction tasks.
    """
    all_predictions, total = await PredictionService.get_predictions_list(offset=0, limit=10000)
    offset = (page - 1) * page_size
    page_predictions = all_predictions[offset : offset + page_size]

    items: list[dict[str, Any]] = [
        {
            "task_name": prediction.task_name,
            "model_name": prediction.model_name,
        }
        for prediction in page_predictions
    ]

    return create_success_response(
        data=create_paginated_response(items, total, page, page_size), message="Predictions list retrieved successfully"
    )


@router.get(
    "/getPrediction",
    response_model=None,
    summary="Get prediction results",
    description="Get the results of a specific prediction task for a model.",
)
async def get_prediction(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    task_name: TaskName = Query(...),
) -> SuccessResponse[dict[str, Any]]:
    """Get the results of a specific prediction task for a model."""
    prediction = await PredictionService.get_prediction(task_name, model_name)

    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="PREDICTION_NOT_FOUND", error_message="Prediction not found"
            ).model_dump(),
        )

    return create_success_response(
        data={
            "prediction": {
                "task_name": prediction.task_name,
                "model_name": prediction.model_name,
                "predictions": prediction.predictions,
            }
        },
        message="Prediction retrieved successfully",
    )


@router.delete(
    "/deletePrediction",
    summary="Delete a prediction",
    description="Delete a single prediction task by task name.",
)
@catch_http_exception(status_code=500, error_code="DELETE_ERROR", message="Failed to delete prediction")
async def delete_prediction(
    current_user: Annotated[User, Depends(get_current_active_user)], task_name: TaskName = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    """Delete a single prediction task by task name."""
    await PredictionService.delete_prediction(task_name)

    return create_success_response(data={}, message="Prediction deleted successfully")


@router.delete(
    "/deletePredictions",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Delete multiple predictions",
    description="Delete multiple prediction tasks by comma-separated task names.",
)
@catch_http_exception(status_code=500, error_code="DELETE_PREDICTIONS_ERROR", message="Failed to delete predictions")
async def delete_predictions(
    current_user: Annotated[User, Depends(get_current_active_user)], task_names: str = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    """Delete multiple prediction tasks by comma-separated task names."""
    names = [name.strip() for name in task_names.split(",") if name.strip()]
    if not names:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_TASK_NAMES", error_message="At least one task name must be provided"
            ).model_dump(),
        )

    deleted: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            await PredictionService.delete_prediction(name)
            deleted.append(name)
        except Exception as exc:
            logger.warning("Failed to delete prediction '%s': %s", name, exc)
            failed.append(name)

    data = {"deleted": deleted, "failed": failed}
    message = f"Deleted {len(deleted)} prediction(s)"
    if failed:
        message += f"; failed to delete {len(failed)}: {', '.join(failed)}"

    return create_success_response(data=data, message=message)


@router.get(
    "/getPredictionDetails",
    response_model=None,
    summary="Get prediction details",
    description=(
        "Retrieve detailed prediction results for a specific function by comparing "
        "model tokens against prediction tokens."
    ),
)
async def get_prediction_details(
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
    task_name: TaskName = Query(...),
) -> SuccessResponse[dict[str, Any]]:
    """Get detailed prediction results for a specific function."""
    try:
        model_info = await FunctionRepository.get(model_name, function_name)
        prediction_data = await PredictionRepository.get_prediction_function(task_name, model_name, function_name)

        if model_info is None:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code="FUNCTION_NOT_FOUND", error_message="Function not found"
                ).model_dump(),
            )

        model_tokens = format_code(model_info.tokens)
        prediction_tokens = format_code(prediction_data.get("tokens", "") if prediction_data else "")

    except (TypeError, IndexError, KeyError, AttributeError):
        logger.exception(
            "Failed to retrieve prediction details for task={}, model={}, function={}",
            task_name,
            model_name,
            function_name,
        )
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="RETRIEVAL_ERROR", error_message="Could not retrieve details"
            ).model_dump(),
        )

    return create_success_response(
        data={
            "task_name": escape(task_name),
            "model_name": escape(model_name),
            "function_name": escape(function_name),
            "model_tokens": model_tokens,
            "prediction_tokens": prediction_tokens,
        },
        message="Prediction details retrieved successfully",
    )
