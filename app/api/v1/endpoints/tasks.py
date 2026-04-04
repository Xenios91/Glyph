"""Task management endpoints for Glyph API.

This module provides endpoints for managing and querying task status.
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.utils.persistence_util import MLPersistanceUtil
from app.services.request_handler import PredictionRequest, TrainingRequest
from app.processing.task_management import Predictor, Trainer
from app.utils.responses import create_success_response, create_error_response

router = APIRouter()


class TaskRequest(BaseModel):
    """Request model for task creation.

    Attributes:
        type: Type of task (train or predict).
        modelName: Optional model name.
        uuid: Optional UUID for the task.
        overwriteModel: Whether to overwrite existing model.
        data: Additional task data.
    """

    type: str
    modelName: str | None = None
    uuid: str | None = None
    overwriteModel: bool = False
    data: Any | None = None


def _validate_model_name(request: TaskRequest) -> None:
    """Validate that model name is provided.
    
    Args:
        request: The task request to validate.
        
    Raises:
        HTTPException: If model name is not provided.
    """
    if request.modelName is None:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="model name is invalid",
            ).model_dump(),
        )


def _validate_model_not_exists(model_name: str, overwrite: bool) -> None:
    """Validate that model doesn't already exist (unless overwrite is True).
    
    Args:
        model_name: The model name to check.
        overwrite: Whether to allow overwriting existing models.
        
    Raises:
        HTTPException: If model exists and overwrite is False.
    """
    if not overwrite and MLPersistanceUtil.check_name(model_name):
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="MODEL_NAME_EXISTS",
                error_message="model name already taken",
            ).model_dump(),
        )


def _run_training_task(training_request: TrainingRequest) -> None:
    """Background task for training a model.
    
    Args:
        training_request: The training request containing model data.
    """
    try:
        Trainer().start_training(training_request)
        logging.info("Training task started: %s", training_request.uuid)
    except Exception as exc:
        logging.error("Training task failed: %s - %s", training_request.uuid, exc)
        raise


def _run_prediction_task(prediction_request: PredictionRequest) -> None:
    """Background task for running predictions.
    
    Args:
        prediction_request: The prediction request containing data.
    """
    try:
        Predictor().start_prediction(prediction_request)
        logging.info("Prediction task completed successfully: %s", prediction_request.uuid)
    except Exception as exc:
        logging.error("Prediction task failed: %s - %s", prediction_request.uuid, exc)
        raise


@router.post("/task", status_code=201)
async def handle_task(
    background_tasks: BackgroundTasks,
    request: TaskRequest,
) -> dict[str, Any]:
    """Handle a train/predict task.
    
    Args:
        background_tasks: FastAPI BackgroundTasks for async task execution.
        request: The task request containing task parameters.
        
    Returns:
        Success response with task UUID.
        
    Raises:
        HTTPException: If task type is invalid or validation fails.
    """
    _validate_model_name(request)
    
    # Safe to cast since we validated modelName is not None above
    model_name: str = request.modelName  # type: ignore[assignment]
    uuid = request.uuid or Trainer().get_uuid()
    
    if request.type == "training":
        _validate_model_not_exists(model_name, request.overwriteModel)
        
        try:
            training_request = TrainingRequest(
                uuid, model_name, request.model_dump()
            )
            background_tasks.add_task(_run_training_task, training_request)
            
            return create_success_response(
                data={"uuid": training_request.uuid},
                message="Training task created successfully",
            ).model_dump()
        except TypeError as type_error:
            logging.error(type_error)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="TYPE_ERROR",
                    error_message="type error",
                ).model_dump(),
            )
            
    elif request.type == "prediction":
        try:
            prediction_request = PredictionRequest(
                uuid, model_name, request.model_dump()
            )
            background_tasks.add_task(_run_prediction_task, prediction_request)
            
            return create_success_response(
                data={"uuid": prediction_request.uuid},
                message="Prediction task created successfully",
            ).model_dump()
        except TypeError as type_error:
            logging.error(type_error)
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code="TYPE_ERROR",
                    error_message="type error",
                ).model_dump(),
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_REQUEST_TYPE",
                error_message="Invalid request type",
            ).model_dump(),
        )
