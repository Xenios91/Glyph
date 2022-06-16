from asyncio import subprocess
import os
from tabnanny import check
import uuid
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
from sklearn import preprocessing
from sklearn.pipeline import Pipeline

from config import GlyphConfig
from persistance_util import FunctionPersistanceUtil, MLPersistanceUtil, MLTask
from request_handler import GhidraRequest, PredictionRequest, TrainingRequest
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
                status = task[0].uuid
                break
        return status

    @classmethod
    def get_all_status(cls) -> dict:
        status_list: dict = {}
        queue_list: list = list(TaskService().service_queue.queue)
        for task in queue_list:
            status: str = task[0].status
            model_name: str = task[0].model_name
            status_list[model_name] = status
        return status_list

    @classmethod
    def set_status(cls, job_uuid: str, status: str) -> bool:
        queue_list: list = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                task[0].status = status
                break
        return status


class Trainer(TaskManager):

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls._train_model, training_request)
        TaskService().service_queue.put((training_request, future))

    @classmethod
    def _train_model(cls, training_request: TrainingRequest):
        pipeline: Pipeline = MLTask.get_multi_class_pipeline()
        try:
            X: pd.Series = training_request.data["tokens"]
            y = preprocessing.LabelEncoder().fit_transform(
                training_request.data["functionName"])

            labels = ",".join(list(training_request.data["functionName"]))

            pipeline.fit(X, y)
            MLPersistanceUtil.save_model("test_pipeline", labels, pipeline)
            training_request.status = "complete"
        except Exception as e:
            print(e)
            training_request.status = "error"


class Predictor(TaskManager):

    @classmethod
    def start_prediction(cls, prediction_request: PredictionRequest):
        future = cls.exec_pool.submit(cls._run_prediction, prediction_request)
        TaskService().service_queue.put((prediction_request, future))

    @classmethod
    def _run_prediction(cls, prediction_request: PredictionRequest):
        try:
            model, labels = MLPersistanceUtil.load_model(prediction_request.model_name)
            predictions = model.predict(prediction_request.data["tokens"])
            predicted_labels = [labels[prediction] for prediction in predictions]
            FunctionPersistanceUtil.add_prediction_functions(
                prediction_request, predicted_labels)
            return predicted_labels
        except Exception as exception:
            print(exception)


class Ghidra(TaskManager):

    @classmethod
    def start_task(cls, ghidra_request: GhidraRequest):
        future = cls.exec_pool.submit(cls._run_analysis, ghidra_request)
        TaskService().service_queue.put((ghidra_request, future))

    @classmethod
    def _run_analysis(cls, ghidra_request: GhidraRequest):
        ghidra_location = GlyphConfig.get_config_value("ghidra_loction")
        ghidra_project_name = GlyphConfig.get_config_value("ghidra_project")
        ghidra_project_location = GlyphConfig.get_config_value(
            "ghidra_project_location")
        glyph_script_location = GlyphConfig.get_config_value(
            "glyph_script_location")

        ghidra_headless_location = os.path.join(
            ghidra_location, f"support{os.sep}analyzeHeadless")

        subprocess.run([ghidra_headless_location, ghidra_project_location,
                        ghidra_project_name, "-import", os.path.join("./binaries", ghidra_request.file_name), "-overwrite", "-postscript", os.path.join(glyph_script_location, "ClangTokenGenerator.java")], check=True)
