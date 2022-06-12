import json
import os
import threading

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

import _version
from functions import FunctionPersistanceUtil
from machine_learning import MLPersistanceUtil
from request_handler import PredictionRequest, TrainingRequest
from services import TaskService
from task_management import Predictor, Trainer

app = Flask(__name__)
UPLOAD_FOLDER = './binaries'
app.config['MAX_CONTENT_LENGTH'] = 512 * 1000 * 1000
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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


@app.route("/delete_model", methods=["DELETE"])
def delete_model():
    args = request.args
    model_name = args.get("model_name")
    MLPersistanceUtil.delete_model(model_name)
    return jsonify(), 200


@app.route("/get_functions", methods=["GET"])
def get_functions():
    args = request.args
    model_name = args.get("model_name")
    functions: list = FunctionPersistanceUtil.get_functions(model_name)
    return jsonify(functions=functions), 200


@app.route("/delete_function", methods=["DELETE"])
def delete_function():
    args = request.args
    function_name = args.get("function_name")
    FunctionPersistanceUtil.delete_function(function_name)
    return jsonify(), 200


@app.route("/uploadBinary", methods=["POST"])
def upload_binary():
    if "bin" not in request.files:
        return jsonify(error="no file found"), 400

    file = request.files["bin"]
    if len(file.filename) == 0:
        return jsonify(error="no file found"), 400

    if file:
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config["UPLOAD_FOLDER"]):
            os.mkdir(app.config["UPLOAD_FOLDER"])
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        return jsonify(), 200


@app.route("/listBins", methods=["GET"])
def list_bins():
    files: set = set()
    directory_path = app.config['UPLOAD_FOLDER']
    files_iter = os.walk(directory_path)
    for (_, _, file) in files_iter:
        files.add(file[0])
    return jsonify(files=list(files)), 200


@app.route("/deleteBin", methods=["GET"])
def delete_bin():
    args = request.args
    filename = secure_filename(args.get("filename"))
    directory_path = app.config['UPLOAD_FOLDER']
    file_to_delete = os.path.join(directory_path, filename)
    os.remove(file_to_delete)
    return jsonify(), 200


@app.route("/getSymbols", methods=["GET"])
def get_symbols():
    args = request.args
    model_name = args.get("model_name")
    functions: list = FunctionPersistanceUtil.get_functions(model_name)
    return jsonify(functions=functions), 200


@app.route("/statusUpdate", methods=["POST"])
def update_status():
    args = request.args
    status = args.get("status")
    uuid = args.get("uuid")
    Trainer().set_status(uuid, status)
    return jsonify(), 200
