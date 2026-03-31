import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from markupsafe import escape
from pydantic import BaseModel

from app.utils.helpers import ACCEPT_TYPE
from app.utils.persistence_util import FunctionPersistanceUtil, PredictionPersistanceUtil
from app.services.request_handler import PredictionRequest
from app.processing.task_management import Predictor, Trainer
from app.utils.common import format_code
from app.utils.responses import create_success_response, create_error_response

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class PredictTokensRequest(BaseModel):
    modelName: str
    uuid: str | None = None

    class Config:
        extra = "allow"


@router.post("/predict", status_code=201)
async def predict_tokens(request_values: PredictTokensRequest):
    """Creates a job to predict a function name based on the tokens supplied"""
    try:
        model_name = request_values.modelName
        uuid = request_values.uuid or Trainer().get_uuid()
        data = request_values.model_dump()
        task_name = data.get("taskName", "")

        # Validate that task name is unique
        if not PredictionPersistanceUtil.is_task_name_unique(task_name):
            return JSONResponse(
                content=create_error_response(
                    error_code="TASK_NAME_EXISTS",
                    error_message=f"Task name '{task_name}' already exists. Task names must be unique.",
                ).model_dump(),
                status_code=409,
            )

        prediction_request = PredictionRequest(uuid, model_name, data)
        Predictor().start_prediction(prediction_request)

        return JSONResponse(
            content=create_success_response(
                data={"uuid": prediction_request.uuid},
                message="Prediction task created successfully",
            ).model_dump(),
            status_code=201,
        )

    except Exception as e:
        logging.error(f"Prediction error: {e}")
        return JSONResponse(
            content=create_error_response(
                error_code="PREDICTION_ERROR",
                error_message=str(e),
            ).model_dump(),
            status_code=400,
        )


@router.get("/getPrediction")
async def get_prediction(
    request: Request, modelName: str = Query(...), taskName: str = Query(...)
):
    """Obtain all predictions from one task"""
    prediction = PredictionPersistanceUtil.get_predictions(taskName, modelName)

    if not prediction:
        return JSONResponse(
            content=create_error_response(
                error_code="PREDICTION_NOT_FOUND",
                error_message="Prediction not found",
            ).model_dump(),
            status_code=404,
        )

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(
            content=create_success_response(
                data={"prediction": prediction.__dict__},
                message="Prediction retrieved successfully",
            ).model_dump(),
            status_code=200,
        )

    return templates.TemplateResponse(
        "get_prediction.html",
        {
            "request": request,
            "title": "Prediction",
            "model_name": prediction.model_name,
            "task_name": prediction.task_name,
            "prediction": prediction,
        },
    )


@router.delete("/deletePrediction")
async def delete_prediction(taskName: str = Query(...)):
    """Deletes a prediction by task name"""
    task_name = taskName.strip()
    if not task_name:
        return JSONResponse(
            content=create_error_response(
                error_code="INVALID_TASK_NAME",
                error_message="invalid task name",
            ).model_dump(),
            status_code=400,
        )

    PredictionPersistanceUtil.delete_prediction(task_name)
    return JSONResponse(
        content=create_success_response(
            data={},
            message="Prediction deleted successfully",
        ).model_dump(),
        status_code=200,
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

        model_tokens = format_code(model_info[3])
        prediction_tokens = format_code(prediction_data["tokens"])

    except (TypeError, IndexError) as e:
        logging.error(e)
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
            data={
                "task_name": escape(task_name),
                "model_name": escape(model_name),
                "function_name": escape(func_name),
                "model_tokens": model_tokens,
                "prediction_tokens": prediction_tokens,
            },
            message="Prediction details retrieved successfully",
        ).model_dump(),
        status_code=200,
    )
