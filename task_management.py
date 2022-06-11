from concurrent.futures import ProcessPoolExecutor
import uuid
import pandas as pd
from sklearn import preprocessing

from sklearn.pipeline import Pipeline
from machine_learning import MLPersistanceUtil, MLTask
from request_handler import PredictionRequest, TrainingRequest

from services import TaskService


class TaskManager():
    exec_pool = ProcessPoolExecutor(2)
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def get_uuid(cls) -> str:
        value: str = str(uuid.uuid4())
        if value in list(TaskService().service_queue.queue):
            value = cls.get_uuid()
        return value

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        status: str = "UUID Not Found"
        queue_list: list = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                status = "In Progress"
                break
        return status


class Trainer(TaskManager):

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls.train_model, training_request)
        TaskService().service_queue.put((training_request, future))

    @classmethod
    def train_model(cls, training_request: TrainingRequest):
        pipeline: Pipeline = MLTask.get_multi_class_pipeline()
        try:
            X: pd.Series = training_request.data["tokens"]
            y = preprocessing.LabelEncoder().fit_transform(
                training_request.data["functionName"])

            pipeline.fit(X, y)
            MLPersistanceUtil.save_model("test_pipeline", pipeline)
            training_request.status = "complete"
        except Exception as e:
            print(e)
            training_request.status = "error"


class Predictor(TaskManager):

    @classmethod
    def start_prediction(cls, prediction_request: PredictionRequest):
        future = cls.exec_pool.submit(cls.run_prediction, prediction_request)
        TaskService().service_queue.put((prediction_request, future))

    @classmethod
    def run_prediction(cls, prediction_request: PredictionRequest):
        try:
            model = MLPersistanceUtil.load_model(prediction_request.model_name)
            predictions = model.predict(prediction_request.data)
            return predictions
        except:
            pass
