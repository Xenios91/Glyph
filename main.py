import threading

from flask import Flask, jsonify, request

import _version
from training import Trainer
from training_request import TrainingRequest
from training_service import TrainingService

app = Flask(__name__)

threading.Thread(target=TrainingService().start_service, daemon=True).start()


@app.route("/")
def home():
    return jsonify(version=_version.__version__)


@app.route("/train", methods=["POST"])
def train_model():
    data: str = request.get_data().decode()
    trainer = Trainer()
    try:
        training_request = TrainingRequest(trainer.get_uuid(), data)
        Trainer().start_training(training_request)
        return jsonify(uuid=training_request.uuid), 201
    except Exception as tr_exception:
        return jsonify("error"), 400


@app.route("/status", methods=["GET"])
def get_status():
    args = request.args
    status: str
    if 'uuid' in args:
        job_uuid: str = args['uuid']
        status = Trainer().get_status(job_uuid)
    else:
        status = "invalid request"
    return jsonify(status=status), 400
