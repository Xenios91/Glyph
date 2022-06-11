import threading

from flask import Flask, jsonify, request

import _version
from training import Trainer, TrainingRequest, TrainingService

app = Flask(__name__)

threading.Thread(target=TrainingService().start_service, daemon=True).start()


@app.route("/")
def home():
    return jsonify(version=_version.__version__)


@app.route("/train", methods=["POST"])
def train_model():
    data: str = request.get_data().decode()
    trainer: Trainer = Trainer()
    try:
        training_request: TrainingRequest = TrainingRequest(trainer.get_uuid(), data)
        Trainer().start_training(training_request)
        return jsonify(uuid=training_request.uuid), 201
    except Exception as tr_exception:
        print(tr_exception)
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
