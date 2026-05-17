import asyncio
import contextvars
from typing import Annotated, Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from starlette.responses import HTMLResponse
from markupsafe import escape
from pydantic import BaseModel

from app.api.types import ModelName, FunctionName, TaskName
from app.utils.helpers import ACCEPT_TYPE
from app.utils.persistence_util import FunctionPersistanceUtil, PredictionPersistanceUtil
from app.services.request_handler import PredictionRequest
from app.processing.task_management import TaskManager
from app.utils.common import format_code
from loguru import logger
from app.utils.responses import create_success_response, create_error_response, SuccessResponse
from app.templates import templates
from app.utils.logging_utils import catch_http_exception
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    restore_request_context,
    clear_request_context,
)
from app.auth.dependencies import get_current_active_user
from app.database.models import User


router = APIRouter()


class PredictTokensRequest(BaseModel):
    modelName: str
    uuid: str | None = None

    model_config = {"extra": "allow"}


def _run_prediction_task(
    prediction_request: PredictionRequest,
    captured_ctx: CapturedContext | None = None,
) -> None:
    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=prediction_request.uuid)

        from app.processing.steps import (
            TokenizeStep,
            FilterStep,
            FeatureExtractStep,
            PredictStep)
        from app.processing.pipeline import ProcessingPipeline, PipelineContext

        functions = prediction_request.get_functions()

        context = PipelineContext(
            uuid=prediction_request.uuid,
            binary_path="",
            pipeline_type="ml_prediction",
            metadata={
                "model_name": prediction_request.model_name,
                "task_name": prediction_request.task_name,
            })

        context.set("functions", functions)

        pipeline = ProcessingPipeline(
            "ML Prediction Pipeline",
            [
                TokenizeStep(),
                FilterStep(),
                FeatureExtractStep(),
                PredictStep(),
            ])
        result = cast(
            PipelineContext,
            asyncio.run(
                pipeline.execute(context),
                context=contextvars.copy_context(),  # pyright: ignore[reportCallIssue]
            ),
        )

        if result.error:
            raise RuntimeError(result.error)

        logger.info("Prediction task completed: {}", prediction_request.uuid)
    except Exception:
        logger.exception("Prediction task failed: {}", prediction_request.uuid)
        raise
    finally:
        clear_request_context()


@router.post("/predict", status_code=201, response_model=SuccessResponse[dict[str, Any]])
@catch_http_exception(status_code=400, error_code="PREDICTION_ERROR")
async def predict_tokens(
    background_tasks: BackgroundTasks,
    request_values: PredictTokensRequest,
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
    model_name = request_values.modelName
    uuid = request_values.uuid or TaskManager().get_uuid()
    data = request_values.model_dump()
    task_name = data.get("taskName", "")

    if not task_name or not task_name.strip():
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="TASK_NAME_REQUIRED",
                error_message="taskName is required for predictions").model_dump())
    task_name = task_name.strip()

    if not await PredictionPersistanceUtil.is_task_name_unique(task_name):
        raise HTTPException(
            status_code=409,
            detail=create_error_response(
                error_code="TASK_NAME_EXISTS",
                error_message=f"Task name '{task_name}' already exists. Task names must be unique.").model_dump())

    prediction_request = PredictionRequest(uuid, model_name, data)
    captured_ctx = capture_request_context()
    background_tasks.add_task(_run_prediction_task, prediction_request, captured_ctx)

    return create_success_response(
        data={"uuid": prediction_request.uuid},
        message="Prediction task created successfully")


@router.get("/getPrediction", response_model=None)
async def get_prediction(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    task_name: TaskName = Query(...)
) -> SuccessResponse[dict[str, Any]] | HTMLResponse:
    prediction = await PredictionPersistanceUtil.get_predictions(task_name, model_name)

    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="PREDICTION_NOT_FOUND",
                error_message="Prediction not found").model_dump())

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "get_prediction.html",
            {
                "title": "Prediction",
                "model_name": prediction.model_name,
                "task_name": prediction.task_name,
                "prediction": prediction,
                "user": current_user,
            })

    return create_success_response(
        data={
            "prediction": {
                "task_name": prediction.task_name,
                "model_name": prediction.model_name,
                "predictions": prediction.predictions
            }
        },
        message="Prediction retrieved successfully")


@router.delete("/deletePrediction")
@catch_http_exception(status_code=500, error_code="DELETE_ERROR", message="Failed to delete prediction")
async def delete_prediction(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_name: TaskName = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    await PredictionPersistanceUtil.delete_prediction(task_name)

    return create_success_response(
        data={},
        message="Prediction deleted successfully")


@router.delete("/deletePredictions", response_model=SuccessResponse[dict[str, Any]])
@catch_http_exception(status_code=500, error_code="DELETE_PREDICTIONS_ERROR", message="Failed to delete predictions")
async def delete_predictions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_names: str = Query(...)
) -> SuccessResponse[dict[str, Any]]:
    names = [name.strip() for name in task_names.split(",") if name.strip()]
    if not names:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_TASK_NAMES",
                error_message="At least one task name must be provided").model_dump())

    deleted: list[str] = []
    failed: list[str] = []
    for name in names:
        try:
            await PredictionPersistanceUtil.delete_prediction(name)
            deleted.append(name)
        except Exception as exc:
            logger.warning("Failed to delete prediction '%s': %s", name, exc)
            failed.append(name)

    data = {"deleted": deleted, "failed": failed}
    message = f"Deleted {len(deleted)} prediction(s)"
    if failed:
        message += f"; failed to delete {len(failed)}: {', '.join(failed)}"

    return create_success_response(data=data, message=message)


@router.get("/getPredictionDetails", response_model=None)
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
    task_name: TaskName = Query(...)
) -> SuccessResponse[dict[str, Any]] | HTMLResponse:
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
                    error_message="Function not found").model_dump())

        model_tokens = format_code(model_info.tokens)
        prediction_tokens = format_code(prediction_data.get("tokens", ""))

    except (TypeError, IndexError):
        logger.exception(
            "Failed to retrieve prediction details for task={}, model={}, function={}",
            task_name, model_name, function_name)
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
                "task_name": task_name,
                "model_name": model_name,
                "function_name": function_name,
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
            })

    return create_success_response(
        data={
            "task_name": escape(task_name),
            "model_name": escape(model_name),
            "function_name": escape(function_name),
            "model_tokens": model_tokens,
            "prediction_tokens": prediction_tokens,
        },
        message="Prediction details retrieved successfully")
