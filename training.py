import queue
import uuid
from concurrent.futures import ProcessPoolExecutor
from io import StringIO

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class TrainingRequest():
    uuid: str
    data: pd.DataFrame
    status: str

    def __init__(self, uuid: str, data: str):
        self.uuid = uuid
        self.data = self.check_training_data(data)
        self.status = "starting"

    def check_training_data(self, data: str) -> pd.DataFrame:
        try:
            contents = StringIO(data)
            data_frame: pd.DataFrame = pd.DataFrame(contents)
            return data_frame
        except Exception as tr_exception:
            raise Exception("invalid dataset") from tr_exception


class Trainer():
    exec_pool = ProcessPoolExecutor(2)
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def get_uuid(cls) -> str:
        value = str(uuid.uuid4())
        if value in list(TrainingService().service_queue.queue):
            value = cls.get_uuid()
        return value

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls.train_model, training_request)
        TrainingService().service_queue.put((training_request, future))

    @classmethod
    def train_model(cls, training_request: TrainingRequest):
        pipeline: Pipeline = MLTask.get_multi_class_pipeline()
        try:
            X = training_request.data["instructions"]
            y = training_request.data["label"]

            pipeline.fit(X, y)
            training_request.status = "complete"
        except:
            training_request.status = "error"

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        status = "UUID Not Found"
        queue_list = list(TrainingService().service_queue.queue)
        for task in queue_list:
            queued_uuid = task[0].uuid
            if job_uuid == queued_uuid:
                status = "In Progress"
                break
        return status


class TrainingService():
    service_queue: queue.Queue = queue.Queue()
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_service(cls):
        while True:
            task = cls.service_queue.get(block=True)
            job_uuid: str = task[0].uuid
            task[1].result()
            print(f"Processing job: {job_uuid}")


class MLTask():

    @staticmethod
    def get_multi_class_pipeline() -> Pipeline:
        pipeline = Pipeline(
            [('preprocessor', TfidfVectorizer(ngram_range=(2, 4), norm='l2', sublinear_tf=True)),
             ('clf', MultinomialNB(alpha=1e-8))])
        return pipeline

    # not implemented yet, need to check algos
    @staticmethod
    def get_single_class_pipeline() -> Pipeline:
        pipeline = Pipeline(
            [('preprocessor', TfidfVectorizer(ngram_range=(2, 4), norm='l2', sublinear_tf=True)),
             ('clf', MultinomialNB(alpha=1e-8))])
        return pipeline
