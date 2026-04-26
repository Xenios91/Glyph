"""Prediction endpoints for Glyph API.

This module provides endpoints for making predictions and retrieving
prediction results.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
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
from app.utils.jinja_utils import configure_jinja2_templates
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.database.models import User


router = APIRouter()
templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)


class PredictTokensRequest(BaseModel):
    """Request model for token prediction.

    Attributes:
        modelName: Name of the model to use for prediction.
        uuid: Optional UUID for the prediction task.
    """

    modelName: str
    uuid: str | None = None

    model_config = {"extra": "allow"}


def _run_prediction_task(prediction_request: PredictionRequest) -> None:
    """Background task for running predictions.
    
    Args:
        prediction_request: The prediction request containing data.
    """
    try:
        # Use the pipeline framework for predictions
        from app.processing.steps import (
            ValidationStep,
            DecompileStep,
            TokenizeStep,
            FilterStep,
            FeatureExtractStep,
            PredictStep)
        from app.processing.pipeline import ProcessingPipeline, PipelineContext
        
        context = PipelineContext(
            uuid=prediction_request.uuid,
            binary_path="",  # Will be set by the pipeline
            pipeline_type="ml_prediction",
            metadata={
                "model_name": prediction_request.model_name,
                "task_name": prediction_request.task_name,
            })
        
        pipeline = ProcessingPipeline(
            "ML Prediction Pipeline",
            [
                ValidationStep(),
                DecompileStep(),
                TokenizeStep(),
                FilterStep(),
                FeatureExtractStep(),
                PredictStep(),
            ])
        result = pipeline.execute(context)
        
        if result.error:
            raise Exception(result.error)
            
        logger.info("Prediction task completed successfully: {}", prediction_request.uuid)
    except Exception as exc:
        logger.error("Prediction task failed: {} - {}", prediction_request.uuid, exc)
        raise


@router.post("/predict", status_code=201, response_model=SuccessResponse[dict])
async def predict_tokens(
    background_tasks: BackgroundTasks,
    request_values: PredictTokensRequest,
    current_user: Annotated[User, Depends(get_current_active_user)]):
    """Creates a job to predict a function name based on the tokens supplied.
    
    Args:
        background_tasks: FastAPI BackgroundTasks for async task execution.
        request_values: The prediction request containing model name and data.
        
    Returns:
        Success response with task UUID.
        
    Raises:
        HTTPException: If task name already exists or prediction fails.
    """
    try:
        model_name = request_values.modelName
        uuid = request_values.uuid or TaskManager().get_uuid()
        data = request_values.model_dump()
        task_name = data.get("taskName", "")

        # Validate that task name is unique
        if not PredictionPersistanceUtil.is_task_name_unique(task_name):
            raise HTTPException(
                status_code=409,
                detail=create_error_response(
                    error_code="TASK_NAME_EXISTS",
                    error_message=f"Task name '{task_name}' already exists. Task names must be unique.").model_dump())

        prediction_request = PredictionRequest(uuid, model_name, data)
        
        # Add prediction as a background task
        background_tasks.add_task(_run_prediction_task, prediction_request)

        return create_success_response(
            data={"uuid": prediction_request.uuid},
            message="Prediction task created successfully")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Prediction error: {}", exc)
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="PREDICTION_ERROR",
                error_message=str(exc)).model_dump())


@router.get("/getPrediction")
async def get_prediction(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    task_name: TaskName = Query(...)):
    """Obtain all predictions from one task.
    
    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).
        task_name: The name of the task (automatically validated and stripped).
        
    Returns:
        Prediction data or HTML template response.
        
    Raises:
        HTTPException: If prediction is not found.
    """
    prediction = PredictionPersistanceUtil.get_predictions(task_name, model_name)

    if not prediction:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="PREDICTION_NOT_FOUND",
                error_message="Prediction not found").model_dump())

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return create_success_response(
            data={"prediction": prediction.__dict__},
            message="Prediction retrieved successfully")

    return templates.TemplateResponse(
        "get_prediction.html",
        {
            "request": request,
            "title": "Prediction",
            "model_name": prediction.model_name,
            "task_name": prediction.task_name,
            "prediction": prediction,
        })


@router.delete("/deletePrediction")
async def delete_prediction(
    current_user: Annotated[User, Depends(get_current_active_user)],
    task_name: TaskName = Query(...)):
    """Deletes a prediction by task name.
    
    Args:
        task_name: The name of the task to delete (automatically validated and stripped).
        
    Returns:
        Success response when prediction is deleted.
    """
    try:
        # Validation is handled by Pydantic - task_name is already stripped and validated
        PredictionPersistanceUtil.delete_prediction(task_name)
        
        return create_success_response(
            data={},
            message="Prediction deleted successfully")
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="VALIDATION_ERROR",
                error_message=str(ve)).model_dump())
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code="DELETE_ERROR",
                error_message=f"Failed to delete prediction: {exc}").model_dump())


@router.get("/getPredictionDetails")
async def get_prediction_details(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    model_name: ModelName = Query(...),
    function_name: FunctionName = Query(...),
    task_name: TaskName = Query(...)):
    """Displays specific details of a prediction.
    
    Args:
        request: The FastAPI request object.
        model_name: The name of the model (automatically validated and stripped).
        function_name: The name of the function (automatically validated and stripped).
        task_name: The name of the task (automatically validated and stripped).
        
    Returns:
        Prediction details or HTML template response.
        
    Raises:
        HTTPException: If retrieval fails.
    """
    try:
        model_info = FunctionPersistanceUtil.get_function(model_name, function_name)
        prediction_data = FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, function_name
        )

        model_tokens = format_code(model_info[3])
        prediction_tokens = format_code(prediction_data["tokens"])

    except (TypeError, IndexError) as e:
        logger.error(
            "Failed to retrieve prediction details for task={}, model={}, function={}: {}",
            task_name, model_name, function_name, e)
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="RETRIEVAL_ERROR",
                error_message="Could not retrieve details").model_dump())

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            "prediction_function_details.html",
            {
                "request": request,
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
