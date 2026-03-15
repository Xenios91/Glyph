import logging

from flask import Response, make_response, jsonify
from app.blueprints.request_handler import PredictionRequest
from app.blueprints.task_management import Predictor, Trainer


def predict_tokens(request_values: dict) -> Response:
    """
    Creates a job to predict a function name based on the tokens supplied
    """

    try:
        model_name = request_values.get("modelName")
        if model_name is None:
            return make_response(jsonify(error="model name is invalid"), 400)
        uuid = request_values.get("uuid")
        if uuid == "" or uuid is None:
            uuid = Trainer().get_uuid()
        data = request_values
    except KeyError as key_error:
        logging.error(key_error)
        return make_response(jsonify(error="model name is invalid"), 400)

    try:
        prediction_request: PredictionRequest = PredictionRequest(
            uuid, model_name, data
        )
        Predictor().start_prediction(prediction_request)

        return make_response(jsonify(uuid=prediction_request.uuid), 201)
    except TypeError as type_error:
        logging.error(type_error)
        return make_response(jsonify(error="type error"), 400)
