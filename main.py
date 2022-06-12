import threading

from flask import Flask, jsonify, request

import _version
from machine_learning import MLPersistanceUtil
from request_handler import PredictionRequest, TrainingRequest

from services import TaskService
from task_management import Predictor, Trainer

app = Flask(__name__)

threading.Thread(target=TaskService().start_service, daemon=True).start()


@app.route("/")
def home():
    return jsonify(version=_version.__version__)


@app.route("/train", methods=["POST"])
def train_model():
    request_values: dict = request.get_json()
    model_name = request_values.get("model_name")
    data = request_values.get("data")

    if MLPersistanceUtil.check_name(model_name):
        return jsonify(error="model name already taken"), 400

    try:
        training_request: TrainingRequest = TrainingRequest(
            Trainer().get_uuid(), data)
        Trainer().start_training(training_request)
        return jsonify(uuid=training_request.uuid), 201
    except Exception as tr_exception:
        print(tr_exception)
        return jsonify("error"), 400


@app.route("/predict", methods=["POST"])
def predict_tokens():
    request_values = request.get_json()
    model_name = request_values.get("model_name")
    data = request_values.get("data")
    try:
        prediction_request: PredictionRequest = PredictionRequest(
            Predictor().get_uuid(), model_name, data)
        predictions = Predictor().run_prediction(prediction_request)
        return jsonify(predictions=""), 200
    except Exception as p_exception:
        print(p_exception)
        return jsonify("error"), 400


@app.route("/status", methods=["GET"])
def get_status():
    args = request.args
    status: str
    status_code: int
    if 'uuid' in args:
        job_uuid: str = args['uuid']
        status = Trainer().get_status(job_uuid)
        if status == "UUID Not Found":
            status_code = 404
        else:
            status_code = 200
    else:
        status = "invalid request"
        status_code = 400
    return jsonify(status=status), status_code


@app.route("/list_models", methods=["GET"])
def get_list_models():
    models: set[str] = MLPersistanceUtil.get_models_list()
    return jsonify(models=list(models)), 200
