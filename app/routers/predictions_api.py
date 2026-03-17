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
    
    @app.route("/getPredictions", methods=["GET"])
@swag_from("swagger/predictions.yml")
def get_list_predictions():
    """
    Handles a GET request to obtain all predictions available
    """
    predictions: list[Prediction] = PredictionPersistanceUtil.get_predictions_list()

    headers = request.headers
    accept = headers.get("Accept")

    if ACCEPT_TYPE not in accept:
        predictions_list: list[dict] = []
        for prediction in predictions:
            predictions_list.append(prediction.__dict__)

        return jsonify(predictions=list(predictions_list)), 200

    return render_template(
        "get_predictions.html", title="Predictions List", predictions=predictions
    )


@app.route("/getPrediction", methods=["GET"])
@swag_from("swagger/prediction.yml")
def get_predictions():
    """
    Handles a GET request to obtain all predictions from one task available
    """

    args = request.args

    try:
        model_name = args["modelName"]
        task_name = args["taskName"]
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not model_name or not task_name:
        return jsonify(error="invalid request"), 400

    prediction: Prediction = PredictionPersistanceUtil.get_predictions(
        task_name, model_name
    )

    headers = request.headers
    accept = headers.get("Accept")
    if ACCEPT_TYPE not in accept:
        pred: dict = prediction.__dict__
        return jsonify(prediction=pred), 200

    return render_template(
        "get_prediction.html",
        title="Prediction",
        model_name=prediction.model_name,
        task_name=prediction.task_name,
        prediction=prediction,
    )

@app.route("/deletePrediction", methods=["DELETE"])
@swag_from("swagger/delete_prediction.yml")
def delete_prediction():
    """
    Handles a DELETE request to delete a prediction
    """
    args = request.args

    try:
        task_name = args.get("taskName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not task_name:
        return jsonify(error="invalid task name"), 400

    PredictionPersistanceUtil.delete_prediction(task_name)
    return jsonify(), 200


@app.route("/getPredictionDetails", methods=["GET"])
@swag_from("swagger/get_prediction_details.yml")
def get_prediction_details():
    """
    Used for displaying details of a prediction
    """
    args = request.args
    headers = request.headers
    accept = headers.get("Accept")

    try:
        model_name = args["modelName"].strip()
        function_name = args["functionName"].strip()
        task_name = args["taskName"].strip()
    except KeyError as key_error:
        return jsonify(error=str(key_error)), 400

    if not model_name or not function_name or not task_name:
        return jsonify(error="Invalid model, task, or function name"), 400

    try:
        model_function_information: list = FunctionPersistanceUtil.get_function(
            model_name, function_name
        )
        prediction = FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, function_name
        )

        model_tokens = format_code(model_function_information[3])
        prediction_tokens = format_code(prediction["tokens"])
    except TypeError as type_error:
        logging.error(type_error)
        return jsonify(error=str(type_error)), 400

    if ACCEPT_TYPE in accept:
        return render_template(
            "prediction_function_details.html",
            task_name=task_name,
            model_name=model_name,
            function_name=function_name,
            model_tokens=model_tokens,
            prediction_tokens=prediction_tokens,
        )

    return jsonify(
        task_name=escape(task_name),
        model_name=escape(model_name),
        function_name=escape(function_name),
        model_tokens=model_tokens,
        prediction_tokens=prediction_tokens,
    )
