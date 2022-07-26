import logging
import os
import threading

from flasgger import Swagger, swag_from
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.utils import secure_filename

import _version
from config import GlyphConfig
from persistance_util import (FunctionPersistanceUtil, MLPersistanceUtil,
                              PredictionPersistanceUtil)
from request_handler import (GhidraRequest, Prediction, PredictionRequest,
                             TrainingRequest)
from services import TaskService
from task_management import Ghidra, Predictor, TaskManager, Trainer
from templates.utils import format_code

app = Flask(__name__)
UPLOAD_FOLDER = './binaries'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1000 * 1000  # max file size 500mb
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

swagger = Swagger(app)
threading.Thread(target=TaskService().start_service, daemon=True).start()
GlyphConfig().load_config()


@app.route("/")
def home():
    '''
    Loads the homepage of Glyph
    '''
    headers = request.headers
    accept = headers.get("Accept")
    if "text/html" not in accept:
        return jsonify(version=_version)

    return render_template("main.html")


@app.route("/task", methods=["POST"])
def handle_task():
    '''
    Handles a train/predict task
    '''
    request_values: dict = request.get_json()
    request_type = request_values.get("type")

    if request_type == "train":
        response = train_model(request_values)
    else:
        response = predict_tokens(request_values)

    return response


def train_model(request_values: dict) -> Response:
    '''
    Creates a job to train an ml model on the tokens supplied
    '''

    try:
        model_name = request_values.get("modelName")
        data = request_values
        overwrite_model = request_values.get("overwriteModel")
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if overwrite_model is None and MLPersistanceUtil.check_name(model_name):
        return jsonify(error="model name already taken"), 400

    try:
        training_request: TrainingRequest = TrainingRequest(
            Trainer().get_uuid(), model_name, data)
        Trainer().start_training(training_request)
        FunctionPersistanceUtil.add_model_functions(training_request)

        return jsonify(uuid=training_request.uuid), 201
    except TypeError as type_error:
        logging.error(type_error)
        return jsonify(error="type error"), 400


def predict_tokens(request_values: dict) -> Response:
    '''
    Creates a job to predict a function name based on the tokens supplied
    '''
    request_values = request.get_json()

    try:
        model_name = request_values.get("modelName")
        data = request_values
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    try:
        prediction_request: PredictionRequest = PredictionRequest(
            Predictor().get_uuid(), model_name, data)
        Predictor().start_prediction(prediction_request)

        return jsonify(uuid=prediction_request.uuid), 201
    except TypeError as type_error:
        logging.error(type_error)
        return jsonify(error="type error"), 400


@app.route("/getStatus", methods=["GET"])
@swag_from("swagger/status.yml")
def get_status():
    '''
    Handles a GET request to obtain the supplied uuid task status
    '''
    args = request.args
    status: str
    status_code: int

    try:
        job_uuid: str = args['uuid']
        if job_uuid == "all":
            status = "test"
            status_code = 200
        else:
            status = Trainer().get_status(job_uuid)
            if status == "UUID Not Found":
                status_code = 404
            else:
                status_code = 200
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    return jsonify(status=status), status_code


@app.route("/getModels", methods=["GET"])
@swag_from("swagger/models.yml")
def get_list_models():
    '''
    Handles a GET request to obtain all models available
    '''
    models: set[str] = MLPersistanceUtil.get_models_list()

    headers = request.headers
    accept = headers.get("Accept")
    if "text/html" not in accept:
        return jsonify(models=list(models)), 200

    models_status: dict = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"
    return render_template("get_models.html", title="Models List", models=models_status)


@app.route("/getPredictions", methods=["GET"])
@swag_from("swagger/predictions.yml")
def get_list_predictions():
    '''
    Handles a GET request to obtain all predictions available
    '''
    predictions: set[str] = PredictionPersistanceUtil.get_predictions_list()

    headers = request.headers
    accept = headers.get("Accept")

    if "text/html" not in accept:
        predictions_list: list[dict] = []
        for prediction in predictions:
            predictions_list.append(prediction.__dict__)

        return jsonify(predictions=list(predictions_list)), 200

    return render_template("get_predictions.html", title="Predictions List", predictions=predictions)


@app.route("/getPrediction", methods=["GET"])
@swag_from("swagger/prediction.yml")
def get_predictions():
    '''
    Handles a GET request to obtain all predictions from one task available
    '''

    args = request.args

    try:
        model_name = args["modelName"]
        task_name = args["taskName"]
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not model_name or not task_name:
        return jsonify(error="invalid request"), 400

    prediction: Prediction = PredictionPersistanceUtil.get_predictions(
        task_name, model_name)

    headers = request.headers
    accept = headers.get("Accept")
    if "text/html" not in accept:
        pred: dict = prediction.__dict__
        return jsonify(prediction=pred), 200

    return render_template("get_prediction.html", title="Prediction", model_name=prediction.model_name, task_name=prediction.task_name, prediction=prediction)


@app.route("/deleteModel", methods=["DELETE"])
@swag_from("swagger/delete_model.yml")
def delete_model():
    '''
    Handles a GET request to delete a supplied model by name
    '''
    args = request.args

    try:
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not model_name:
        return jsonify(error="invalid model name"), 400

    try:
        MLPersistanceUtil.delete_model(model_name)
        PredictionPersistanceUtil.delete_model_predictions(model_name)
    except Exception as e:
        logging.error(e)
    return jsonify(), 200


@app.route("/getFunctions", methods=["GET"])
@swag_from("swagger/get_functions.yml")
def get_functions():
    '''
    Handles a GET request to return all identified functions associated with a model
    '''
    args = request.args
    try:
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not model_name:
        return jsonify(error="invalid model name"), 400

    functions: list = FunctionPersistanceUtil.get_functions(model_name)

    headers = request.headers
    accept = headers.get("Accept")
    if "text/html" not in accept:
        return jsonify(functions=functions), 200

    return render_template("get_symbols.html", bin_name="test",
                           model_name=model_name, functions=functions)


@app.route("/getFunction", methods=["GET"])
@swag_from("swagger/get_function.yml")
def get_function():
    '''
    Handles a GET request to return all identified functions associated with a model
    '''
    args = request.args
    try:
        function_name = args.get("functionName").strip()
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not model_name or not function_name:
        return jsonify(error="invalid model or function name"), 400

    function_information: str = FunctionPersistanceUtil.get_function(
        model_name, function_name)

    function_name = function_information[1]
    function_entry: str = function_information[2]
    function_tokens: str = function_information[3]
    function_tokens = format_code(function_tokens)

    headers = request.headers
    accept = headers.get("Accept")
    if "text/html" not in accept:
        return jsonify(functions=function_information), 200

    return render_template("get_function.html", model_name=model_name, function_name=function_name,
                           function_entry=function_entry, tokens=function_tokens)


@app.route("/deleteFunction", methods=["DELETE"])
@swag_from("swagger/delete_function.yml")
def delete_function():
    '''
    Handles a DELETE request to delete a function from a model
    '''
    args = request.args
    try:
        function_name = args.get("functionName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not function_name:
        return jsonify(error="invalid function name"), 400

    FunctionPersistanceUtil.delete_function(function_name)
    return jsonify(), 200


@app.route("/uploadBinary", methods=["GET"])
def get_upload_binary():
    '''
    Handles GET and POST request to load the webpage and to handle binary file uploads
    '''
    headers = request.headers
    accept = headers.get("Accept")

    if request.method == "GET":
        if "text/html" not in accept:
            return jsonify(error="API calls can only be POST"), 200

        models: set[str] = MLPersistanceUtil.get_models_list()
        allow_prediction = len(models) > 0
        return render_template("upload.html", allow_prediction=allow_prediction, models=models)


@app.route("/uploadBinary", methods=["POST"])
@swag_from("swagger/upload_binary.yml")
def post_upload_binary():
    '''
    Handles GET and POST request to load the webpage and to handle binary file uploads
    '''
    headers = request.headers
    accept = headers.get("Accept")

    if request.method == "POST":
        if "binaryFile" not in request.files:
            return jsonify(error="no file found"), 400

        args = request.form

        try:
            is_training_data: bool = args.get("trainingData")
            model_name: str = args.get("modelName").strip()
            task_name: str = args.get("taskName").strip()
            ml_class_type: str = args.get("mlClassType").strip()
        except KeyError as key_error:
            logging.error(key_error)
            return key_error

        if not model_name or not ml_class_type:
            return jsonify(error="invalid request, missing query strings"), 400

        file = request.files["binaryFile"]

        magic_num = file.read()[:4]
        if magic_num != b'\x7fELF':
            return jsonify(error="incorrect magic number"), 400

        if len(file.filename) == 0:
            return jsonify(error="no file found"), 400

        if file:
            filename = secure_filename(file.filename)
            if not os.path.exists(app.config["UPLOAD_FOLDER"]):
                os.mkdir(app.config["UPLOAD_FOLDER"])
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            ghidra_task: GhidraRequest = GhidraRequest(
                filename, is_training_data, model_name, task_name, ml_class_type)
            Ghidra().start_task(ghidra_task)

        if "text/html" in accept:
            return render_template("upload.html")


@app.route("/listBins", methods=["GET"])
@swag_from("swagger/list_bins.yml")
def list_bins():
    '''
    Handles a GET request to retrieve all available binaries
    '''
    files: list[str] = []
    directory_path = app.config['UPLOAD_FOLDER']
    for _, _, files_found in os.walk(directory_path):
        if files_found:
            for file in files_found:
                files.append(file[0])
    return jsonify(files=files), 200


@app.route("/deletePrediction", methods=["DELETE"])
@swag_from("swagger/delete_prediction.yml")
def delete_bin():
    '''
    Handles a GET request to delete a prediction
    '''
    args = request.args

    try:
        task_name = args.get("taskName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not task_name:
        return jsonify(error="invalid task name"), 400

    PredictionPersistanceUtil.delete_prediction(task_name)
    return jsonify(), 200


@app.route("/statusUpdate", methods=["POST"])
@swag_from("swagger/status_update.yml")
def update_status():
    '''
    Handles a POST request from Ghidra to update the current status of a task
    '''
    args = request.args

    try:
        status = args.get("status").strip()
        uuid = args.get("uuid").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return key_error

    if not status or not uuid:
        return jsonify(error="Invalid request, missing query strings"), 400

    updated: bool = Trainer().set_status(uuid, status)
    if not updated:
        return jsonify(error="UUID not found"), 404

    return jsonify(), 200


@app.route("/error", methods=["GET"])
def error_page():
    '''
    Used for displaying errors
    '''
    args = request.args
    error_type = args.get("type")
    message = "Uh oh! An unknown error has occured"

    if error_type == "uploadError":
        message = "Uh oh! It looks like the binary file is not of type ELF, if it's PE don't worry, we are working on implementing PE capabilities."
    return render_template("error.html", message=message)


@app.route("/getPredictionDetails", methods=["GET"])
@swag_from("swagger/get_prediction_details.yml")
def get_prediction_details():
    '''
    Used for displaying details of a prediction
    '''
    args = request.args

    try:
        model_name = args["modelName"].strip()
        function_name = args["functionName"].strip()
        task_name = args["taskName"].strip()
    except KeyError as key_error:
        return key_error

    if not model_name or not function_name or not task_name:
        return jsonify(error="Invalid model, task, or function name"), 400

    try:
        model_function_information: str = FunctionPersistanceUtil.get_function(
            model_name, function_name)
        prediction = FunctionPersistanceUtil.get_prediction_function(
            task_name, model_name, function_name)

        model_tokens = format_code(model_function_information[3])
        prediction_tokens = format_code(prediction["tokens"])
    except TypeError as type_error:
        logging.error(type_error)

    return render_template("prediction_function_details.html", task_name=task_name, model_name=model_name, function_name=function_name,
                           model_tokens=model_tokens, prediction_tokens=prediction_tokens)
