from flask import Flask, jsonify, request, Response

import _version
from training import Trainer
from training_request import TrainingRequest

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify(version=_version.__version__)


@app.route("/train", methods=["POST"])
def train_model():
    data = request.get_data().decode()
    trainer = Trainer()
    try:
        training_request = TrainingRequest(trainer.get_uuid(), data)
        Trainer().start_training(training_request)
        return Response(status=201)
    except Exception as tr_exception:
        return Response(tr_exception, status=400)
