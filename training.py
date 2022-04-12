import uuid
from concurrent.futures import ProcessPoolExecutor

from training_request import TrainingRequest


class Trainer():
    exec_pool = ProcessPoolExecutor(2)
    futures = {}
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def get_uuid(cls) -> str:
        value = str(uuid.uuid4())
        if value in cls.futures:
            value = cls.get_uuid()
        else:
            return value

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls.__train_model(training_request))
        cls.futures[training_request.uuid] = future

    @classmethod
    def __train_model(cls, training_request: TrainingRequest):
        # something something scikit
        print(training_request.data)
