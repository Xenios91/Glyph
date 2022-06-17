import os
import threading

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

import _version
from config import GlyphConfig
from persistance_util import FunctionPersistanceUtil, MLPersistanceUtil, PredictionPersistanceUtil
from request_handler import GhidraRequest, Prediction, PredictionRequest, TrainingRequest
from services import TaskService
from task_management import Ghidra, Predictor, TaskManager, Trainer
from templates.utils import format_code

app = Flask(__name__)
UPLOAD_FOLDER = './binaries'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1000 * 1000  # max file size 500mb
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

threading.Thread(target=TaskService().start_service, daemon=True).start()
GlyphConfig.load_config()


@app.route("/")
def home():
    '''
    Loads the homepage of Glyph
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")
    if not user_agent:
        return jsonify(version=_version)
    return render_template("main.html")


@app.route("/train", methods=["POST"])
def train_model():
    '''
    Handles a POST request to start a training job
    '''
    request_values: dict = request.get_json()
    model_name = request_values.get("model_name")
    data = request_values.get("data")
    overwrite_model = request_values.get("overwrite_model")

    if overwrite_model is None and MLPersistanceUtil.check_name(model_name):
        return jsonify(error="model name already taken"), 400

    try:
        training_request: TrainingRequest = TrainingRequest(
            Trainer().get_uuid(), data, model_name)
        Trainer().start_training(training_request)
        FunctionPersistanceUtil.add_model_functions(training_request)

        return jsonify(uuid=training_request.uuid), 201
    except Exception as tr_exception:
        print(tr_exception)
        return jsonify("error"), 400


@app.route("/predict", methods=["POST"])
def predict_tokens():
    '''
    Creates a job to predict a function name based on the tokens supplied
    '''
    request_values = request.get_json()
    model_name = request_values.get("model_name")
    data = request_values.get("data")
    try:
        prediction_request: PredictionRequest = PredictionRequest(
            Predictor().get_uuid(), model_name, data)
        Predictor().start_prediction(prediction_request)

        return jsonify(uuid=prediction_request.uuid), 201
    except Exception as p_exception:
        print(p_exception)
        return jsonify("error"), 400


@app.route("/getStatus", methods=["GET"])
def get_status():
    '''
    Handles a GET request to obtain the supplied uuid task status
    '''
    args = request.args
    status: str
    status_code: int
    if 'uuid' in args:
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
    else:
        status = "invalid request"
        status_code = 400
    return jsonify(status=status), status_code


@app.route("/getModels", methods=["GET"])
def get_list_models():
    '''
    Handles a GET request to obtain all models available
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")
    models: set[str] = MLPersistanceUtil.get_models_list()

    if not user_agent:
        return jsonify(models=list(models)), 200

    models_status: dict = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"
    return render_template("get_models.html", title="Models List", models=models_status)


@app.route("/getPredictions", methods=["GET"])
def get_list_predictions():
    '''
    Handles a GET request to obtain all predictions available
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")
    predictions: set[str] = PredictionPersistanceUtil.get_predictions_list()

    if not user_agent:
        return jsonify(predictions=list(predictions)), 200

    return render_template("get_predictions.html", title="Predictions List", predictions=predictions)


@app.route("/getPrediction", methods=["GET"])
def get_predictions():
    '''
    Handles a GET request to obtain all predictions from one task available
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")

    args = request.args
    model_name = args["modelName"]
    task_name = args["taskName"]
    prediction: Prediction = PredictionPersistanceUtil.get_predictions(
        task_name, model_name)

    if not user_agent:
        return jsonify(prediction=prediction), 200

    return render_template("get_prediction.html", title="Prediction", model_name=prediction.model_name, task_name=prediction.task_name, prediction=prediction)


@app.route("/deleteModel", methods=["GET"])
def delete_model():
    '''
    Handles a GET request to delete a supplied model by name
    '''
    args = request.args
    model_name = args.get("modelName")
    MLPersistanceUtil.delete_model(model_name)
    return jsonify(), 200


@app.route("/getFunctions", methods=["GET"])
def get_functions():
    '''
    Handles a GET request to return all identified functions associated with a model
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")

    args = request.args
    model_name = args.get("modelName")
    functions: list = FunctionPersistanceUtil.get_functions(model_name)
    if not user_agent:
        return jsonify(functions=functions), 200

    return render_template("get_symbols.html", bin_name="test",
                           model_name=model_name, functions=functions)


@app.route("/getFunction", methods=["GET"])
def get_function():
    '''
    Handles a GET request to return all identified functions associated with a model
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")

    args = request.args
    function_name = args.get("functionName")
    model_name = args.get("modelName")

    function_information: str = FunctionPersistanceUtil.get_function(
        model_name, function_name)

    function_name = function_information[1]
    function_entry: str = function_information[2]
    function_tokens: str = function_information[3]
    function_tokens = format_code(function_tokens)
    if not user_agent:
        return jsonify(functions=function_information), 200

    return render_template("get_function.html", model_name=model_name, function_name=function_name,
                           function_entry=function_entry, tokens=function_tokens)


@app.route("/deleteFunction", methods=["DELETE"])
def delete_function():
    '''
    Handles a DELETE request to delete a function from a model
    '''
    args = request.args
    function_name = args.get("function_name")
    FunctionPersistanceUtil.delete_function(function_name)
    return jsonify(), 200


@app.route("/uploadBinary", methods=["GET", "POST"])
def upload_binary():
    '''
    Handles GET and POST request to load the webpage and to handle binary file uploads
    '''
    headers = request.headers
    user_agent = headers.get("User-Agent")

    if request.method == "GET":
        if not user_agent:
            return jsonify(error="API calls can only be POST"), 200

        models: set[str] = MLPersistanceUtil.get_models_list()
        allow_prediction = len(models) > 0
        return render_template("upload.html", allow_prediction=allow_prediction)

    if request.method == "POST":
        if "binaryFile" not in request.files:
            return jsonify(error="no file found"), 400

        args = request.form
        is_training_data: bool = args.get("trainingData")
        model_name: str = args.get("modelName")
        ml_class_type: str = args.get("mlClassType")

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
                filename, is_training_data, model_name, ml_class_type)
            Ghidra().start_task(ghidra_task)
        if user_agent:
            return render_template("upload.html")


@app.route("/listBins", methods=["GET"])
def list_bins():
    '''
    Handles a GET request to retrieve all available binaries
    '''
    files: set = set()
    directory_path = app.config['UPLOAD_FOLDER']
    files_iter = os.walk(directory_path)
    for (_, _, file) in files_iter:
        files.add(file[0])
    return jsonify(files=list(files)), 200


@app.route("/deleteBin", methods=["GET"])
def delete_bin():
    '''
    Handles a GET request to delete a binary file
    '''
    args = request.args
    filename = secure_filename(args.get("filename"))
    directory_path = app.config['UPLOAD_FOLDER']
    file_to_delete = os.path.join(directory_path, filename)
    os.remove(file_to_delete)
    return jsonify(), 200


@app.route("/statusUpdate", methods=["POST"])
def update_status():
    '''
    Handles a POST request from Ghidra to update the current status of a task
    '''
    args = request.args
    status = args.get("status")
    uuid = args.get("uuid")
    Trainer().set_status(uuid, status)
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
