import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.request_handler import PredictionRequest
from app.task_management import Predictor, Trainer


router = APIRouter()


class PredictTokensRequest(BaseModel):
    modelName: Optional[str] = None
    uuid: Optional[str] = None

    class Config:
        extra = "allow"  # Allows additional fields in `data`


@router.post("/predict", status_code=201)
def predict_tokens(request_values: PredictTokensRequest) -> JSONResponse:
    """
    Creates a job to predict a function name based on the tokens supplied
    """

    try:
        model_name = request_values.modelName
        if model_name is None:
            raise HTTPException(status_code=400, detail="model name is invalid")

        uuid = request_values.uuid
        if not uuid:
            uuid = Trainer().get_uuid()

        data = request_values.model_dump()
    except KeyError as key_error:
        logging.error(key_error)
        raise HTTPException(status_code=400, detail="model name is invalid")

    try:
        prediction_request = PredictionRequest(uuid, model_name, data)
        Predictor().start_prediction(prediction_request)

        return JSONResponse(content={"uuid": prediction_request.uuid}, status_code=201)
    except TypeError as type_error:
        logging.error(type_error)
        raise HTTPException(status_code=400, detail="type error")