"""Task management endpoints for Glyph API.

This module provides endpoints for managing and querying task status.
"""

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil
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


def train_model(request: TaskRequest) -> JSONResponse:
    """
    Creates a job to train an ml model on the tokens supplied
    """
    if request.modelName is None:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="model name is invalid",
            ).model_dump(),
            status_code=400,
        )

    uuid = request.uuid or Trainer().get_uuid()

    if not request.overwriteModel and MLPersistanceUtil.check_name(request.modelName):
        return JSONResponse(
            content=create_error_response(
                error_code="MODEL_NAME_EXISTS",
                error_message="model name already taken",
            ).model_dump(),
            status_code=400,
        )

    try:
        training_request = TrainingRequest(
            uuid, request.modelName, request.model_dump()
        )
        Trainer().start_training(training_request)
        FunctionPersistanceUtil.add_model_functions(training_request)

        return JSONResponse(
            content=create_success_response(
                data={"uuid": training_request.uuid},
                message="Training task created successfully",
            ).model_dump(),
            status_code=201,
        )
    except TypeError as type_error:
        logging.error(type_error)
        return JSONResponse(
            content=create_error_response(
                error_code="TYPE_ERROR",
                error_message="type error",
            ).model_dump(),
            status_code=400,
        )


def predict_tokens(request: TaskRequest) -> JSONResponse:
    """
    Creates a job to predict a function name based on the tokens supplied
    """
    if request.modelName is None:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_MODEL_NAME",
                error_message="model name is invalid",
            ).model_dump(),
            status_code=400,
        )

    uuid = request.uuid or Trainer().get_uuid()

    try:
        prediction_request = PredictionRequest(
            uuid, request.modelName, request.model_dump()
        )
        Predictor().start_prediction(prediction_request)

        return JSONResponse(
            content=create_success_response(
                data={"uuid": prediction_request.uuid},
                message="Prediction task created successfully",
            ).model_dump(),
            status_code=201,
        )
    except TypeError as type_error:
        logging.error(type_error)
        return JSONResponse(
            content=create_error_response(
                error_code="TYPE_ERROR",
                error_message="type error",
            ).model_dump(),
            status_code=400,
        )


@router.post("/task")
def handle_task(request: TaskRequest) -> JSONResponse:
    """
    Handles a train/predict task
    """
    if request.type == "training":
        return train_model(request)
    elif request.type == "prediction":
        return predict_tokens(request)
    else:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_REQUEST_TYPE",
                error_message="Invalid request type",
            ).model_dump(),
            status_code=400,
        )
