import uuid
from concurrent.futures import ProcessPoolExecutor
from training_service import TrainingService

from training_request import TrainingRequest


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
        if value in TrainingService.queue:
            value = cls.get_uuid()
        else:
            return value

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls.train_model, training_request)
        TrainingService.queue[training_request.uuid] = future

    @classmethod
    def train_model(cls, training_request: TrainingRequest):
        # something something scikit
        training_request.status = "complete"

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        if job_uuid in TrainingService.queue:
            return "In Progress"
        else:
            return "UUID Not Found"
