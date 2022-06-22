import logging
import os
import uuid
from asyncio import subprocess
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Optional

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
                return True
        return False


class Trainer(TaskManager):
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_training(cls, training_request: TrainingRequest):
        future = cls.exec_pool.submit(cls._train_model, training_request)
        TaskService().service_queue.put((training_request, future))

    @classmethod
    def _train_model(cls, training_request: TrainingRequest):
        pipeline: Pipeline = MLTask.get_multi_class_pipeline()
        label_encoder = preprocessing.LabelEncoder()
        try:
            X: pd.Series = training_request.data["tokens"]
            fit_encoder = label_encoder.fit(
                training_request.data["functionName"])
            y = fit_encoder.transform(
                training_request.data["functionName"])

            pipeline.fit(X, y)
            MLPersistanceUtil.save_model(
                "test_pipeline", label_encoder, pipeline)
            training_request.status = "complete"
        except Exception as e:
            logging.error(e)
            training_request.status = "error"


class Predictor(TaskManager):
    __instance = None
    probability_limit_threshold: float

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        super().__init__()
        threshold_value: Optional[Any] = GlyphConfig().get_config_value(
            "prediction_probability_threshold")
        if not isinstance(threshold_value, float):
            raise TypeError(
                "ERROR: prediction_probability_threshold is not type float or int in config.yml")
        self.probability_limit_threshold = threshold_value

    @classmethod
    def start_prediction(cls, prediction_request: PredictionRequest):
        future = Predictor.exec_pool.submit(
            Predictor._run_prediction, prediction_request)
        TaskService().service_queue.put((prediction_request, future))

    @classmethod
    def _run_prediction(cls, prediction_request: PredictionRequest) -> PredictionRequest:
        try:
            model, label_encoder = MLPersistanceUtil.load_model(
                prediction_request.model_name)
            predictions = model.predict(prediction_request.data["tokens"])
            prediction_probability = model.predict_proba(
                prediction_request.data["tokens"]) * 100
            predicted_labels = label_encoder.inverse_transform(predictions)
            Predictor._filter_uncertainty(
                prediction_probability, predicted_labels)
            FunctionPersistanceUtil.add_prediction_functions(
                prediction_request, predicted_labels)

            prediction_request.set_prediction_values(predicted_labels)
        except Exception as exception:
            logging.error(exception)

        return prediction_request

    @classmethod
    def _filter_uncertainty(cls, prediction_probability, predicted_labels):
        for ctr, probability in enumerate(prediction_probability):
            if probability.max() < Predictor().probability_limit_threshold:
                predicted_labels[ctr] = 'Unknown'


class Ghidra(TaskManager):

    @classmethod
    def start_task(cls, ghidra_request: GhidraRequest):
        future = cls.exec_pool.submit(cls._run_analysis, ghidra_request)
        TaskService().service_queue.put((ghidra_request, future))

    @classmethod
    def _run_analysis(cls, ghidra_request: GhidraRequest):
        ghidra_location: Optional[Any] = GlyphConfig.get_config_value(
            "ghidra_loction")
        ghidra_project_name: Optional[Any] = GlyphConfig.get_config_value(
            "ghidra_project")
        ghidra_project_location: Optional[Any] = GlyphConfig.get_config_value(
            "ghidra_project_location")
        glyph_script_location = GlyphConfig.get_config_value(
            "glyph_script_location")

        if len(ghidra_location) == 0 or len(ghidra_project_name) == 0 or len(ghidra_project_location) == 0 or len(glyph_script_location) == 0:
            raise ValueError("ERROR: Config.yml cannot have empty values")

        ghidra_headless_location = os.path.join(
            ghidra_location, f"support{os.sep}analyzeHeadless")

        subprocess.run([ghidra_headless_location, ghidra_project_location,
                        ghidra_project_name, "-import", os.path.join("./binaries", ghidra_request.file_name), "-overwrite", "-postscript", os.path.join(glyph_script_location, "ClangTokenGenerator.java")], check=True)
