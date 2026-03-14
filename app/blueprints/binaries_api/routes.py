from flask import jsonify, render_template, request
from . import binaries_bp
from flask import current_app
import os
import logging
from flasgger import swag_from
from werkzeug.utils import secure_filename
from persistance_util import MLPersistanceUtil
from request_handler import GhidraRequest
from task_management import Ghidra
from app.helpers import ACCEPT_TYPE


@binaries_bp.route("/uploadBinary", methods=["GET"])
def get_upload_binary():
    """
    Handles GET and POST request to load the webpage and to handle binary file uploads
    """
    headers = request.headers
    accept = headers.get("Accept")

    if request.method == "GET":
        if ACCEPT_TYPE not in accept:
            return jsonify(error="API calls can only be POST"), 200

        models: set[str] = MLPersistanceUtil.get_models_list()
        allow_prediction = len(models) > 0
        return render_template(
            "upload.html", allow_prediction=allow_prediction, models=models
        )


@binaries_bp.route("/uploadBinary", methods=["POST"])
@swag_from("swagger/upload_binary.yml")
def post_upload_binary():
    """
    Handles GET and POST request to load the webpage and to handle binary file uploads
    """
    headers = request.headers
    accept = headers.get("Accept")

    if request.method == "POST":
        if "binaryFile" not in request.files:
            return jsonify(error="no file found"), 400

        args = request.form

        try:
            is_training_data: bool = args.get("trainingData", "").lower() == "true"
            model_name: str = args.get("modelName").strip()

            task_name: str = ""
            if "taskName" in args:
                task_name = args.get("taskName").strip()

            ml_class_type: str = args.get("mlClassType").strip()
        except KeyError as key_error:
            logging.error(key_error)
            return jsonify(error=str(key_error)), 400

        if not model_name or not ml_class_type:
            return jsonify(error="invalid request, missing query strings"), 400

        file = request.files["binaryFile"]

        if len(file.filename) == 0:
            return jsonify(error="no file found"), 400

        if file:
            filename = secure_filename(file.filename)
            if not os.path.exists(current_app.config["UPLOAD_FOLDER"]):
                os.mkdir(current_app.config["UPLOAD_FOLDER"])
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
            ghidra_task: GhidraRequest = GhidraRequest(
                filename, is_training_data, model_name, task_name, ml_class_type
            )
            Ghidra().start_task(ghidra_task)
            return jsonify(), 200

        if "*/*" in accept:
            return render_template("upload.html")


@binaries_bp.route("/listBins", methods=["GET"])
@swag_from("swagger/list_bins.yml")
def list_bins():
    """
    Handles a GET request to retrieve all available binaries
    """
    files: list[str] = []
    directory_path = current_app.config["UPLOAD_FOLDER"]
    for _, _, files_found in os.walk(directory_path):
        if files_found:
            for file in files_found:
                files.append(file)
    return jsonify(files=files), 200
