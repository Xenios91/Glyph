import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from markupsafe import escape
from pydantic import BaseModel

from app.helpers import ACCEPT_TYPE
from app.persistance_util import FunctionPersistanceUtil, PredictionPersistanceUtil
from app.request_handler import PredictionRequest
from app.task_management import Predictor, Trainer
from templates.utils import format_code

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class PredictTokensRequest(BaseModel):
    modelName: str
    uuid: Optional[str] = None

    class Config:
        extra = "allow"


@router.post("/predict", status_code=201)
async def predict_tokens(request_values: PredictTokensRequest):
    """Creates a job to predict a function name based on the tokens supplied"""
    try:
        model_name = request_values.modelName
        uuid = request_values.uuid or Trainer().get_uuid()
        data = request_values.model_dump()

        prediction_request = PredictionRequest(uuid, model_name, data)
        Predictor().start_prediction(prediction_request)

        return {"uuid": prediction_request.uuid}

    except Exception as e:
        logging.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/getPrediction")
async def get_prediction(
    request: Request, modelName: str = Query(...), taskName: str = Query(...)
):
    """Obtain all predictions from one task"""
    prediction = PredictionPersistanceUtil.get_predictions(taskName, modelName)

    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return {"prediction": prediction.__dict__}

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
        raise HTTPException(status_code=400, detail="invalid task name")

    PredictionPersistanceUtil.delete_prediction(task_name)
    return JSONResponse(content={}, status_code=200)


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
        raise HTTPException(status_code=400, detail="Could not retrieve details")

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

    return {
        "task_name": escape(task_name),
        "model_name": escape(model_name),
        "function_name": escape(func_name),
        "model_tokens": model_tokens,
        "prediction_tokens": prediction_tokens,
    }
