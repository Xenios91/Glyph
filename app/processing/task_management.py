"""Task management module for Glyph application."""

import atexit
import logging
import os
import signal
import subprocess
import uuid
from concurrent.futures import Future, ProcessPoolExecutor
from typing import Any

import pandas as pd
from sklearn import preprocessing
from sklearn.pipeline import Pipeline

from app.config.settings import get_settings, MAX_CPU_CORES
from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil, MLTask
from app.services.request_handler import GhidraRequest, PredictionRequest, TrainingRequest
from app.services.task_service import TaskService
from app.processing import ghidra_processor

class TaskManager:
    """Base class for managing tasks in Glyph application."""

    exec_pool: ProcessPoolExecutor | None = None
    __instance: "TaskManager | None" = None

    def __init_subclass__(cls, **kwargs) -> None:
        """Initialize the process pool executor for subclasses."""
        super().__init_subclass__(**kwargs)
        if cls.exec_pool is None:
            cls.exec_pool = ProcessPoolExecutor(max_workers=MAX_CPU_CORES)
            # Register cleanup handlers
            atexit.register(cls._shutdown_executor)
            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGTERM, cls._signal_handler)
            signal.signal(signal.SIGINT, cls._signal_handler)

    def __new__(cls) -> "TaskManager":
        """Create or return the singleton instance of TaskManager."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def _get_executor(cls) -> ProcessPoolExecutor:
        """Get or create the process pool executor.

        Returns:
            The ProcessPoolExecutor instance.
        """
        if cls.exec_pool is None or cls.exec_pool._shutdown:
            cls.exec_pool = ProcessPoolExecutor(max_workers=MAX_CPU_CORES)
        return cls.exec_pool

    @classmethod
    def _shutdown_executor(cls) -> None:
        """Shutdown the executor gracefully.

        This method is called on application exit or shutdown signals.
        """
        if cls.exec_pool is not None:
            cls.exec_pool.shutdown(wait=False, cancel_futures=True)
            cls.exec_pool = None
            logging.info("ProcessPoolExecutor shut down successfully")

    @classmethod
    def _signal_handler(cls, signum: int, _frame: Any) -> None:
        """Handle shutdown signals.

        Args:
            signum: The signal number received.
            _frame: The current stack frame (unused).
        """
        logging.info("Received signal %d, shutting down executor...", signum)
        cls._shutdown_executor()

    @classmethod
    def get_uuid(cls) -> str:
        """Generate a unique UUID.

        UUID4 uses 122 random bits, making collision probability
        approximately 1 in 5.3×10^36 - statistically impossible for practical use.

        Returns:
            A unique UUID string.
        """
        return str(uuid.uuid4())

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        """Get the status of a job by its UUID.

        Args:
            job_uuid: The UUID of the job.

        Returns:
            The status of the job or "UUID Not Found".
        """
        status: str = "UUID Not Found"
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                status = task[0].status
                break
        return status

    @classmethod
    def get_all_status(cls) -> dict[str, str]:
        """Get the status of all jobs in the queue.

        Returns:
            A dictionary mapping model names to their statuses.
        """
        status_list: dict[str, str] = {}
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            status: str = task[0].status
            model_name: str = task[0].model_name
            status_list[model_name] = status
        return status_list

    @classmethod
    def set_status(cls, job_uuid: str, status: str) -> bool:
        """Set the status of a job by its UUID.

        Args:
            job_uuid: The UUID of the job.
            status: The new status to set.

        Returns:
            True if the status was set, False if the UUID was not found.
        """
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                task[0].status = status
                return True
        return False


class Trainer(TaskManager):
    """Task manager for training machine learning models."""

    __instance: "Trainer | None" = None

    def __new__(cls) -> "Trainer":
        """Create or return the singleton instance of Trainer."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def start_training(cls, training_request: TrainingRequest) -> None:
        """Start training a model with the given request.

        Args:
            training_request: The training request containing model data.
        """
        future: Future = cls._get_executor().submit(cls._train_model, training_request)
        TaskService().service_queue.put((training_request, future))

    @classmethod
    def _train_model(cls, training_request: TrainingRequest) -> None:
        """Train a model using the provided training request.

        Args:
            training_request: The training request containing model data.
        """
        pipeline: Pipeline = MLTask.get_multi_class_pipeline()
        label_encoder = preprocessing.LabelEncoder()
        try:
            _x: pd.Series = training_request.data["tokens"]
            fit_encoder = label_encoder.fit(
                training_request.data["functionName"])
            _y = fit_encoder.transform(
                training_request.data["functionName"])

            pipeline.fit(_x, _y)
            MLPersistanceUtil.save_model(
                training_request.model_name, label_encoder, pipeline)
            training_request.status = "complete"
        except Exception as error:
            logging.error("Training error: %s", error)
            training_request.status = "error"


class Predictor(TaskManager):
    """Task manager for running predictions on binary functions."""

    __instance: "Predictor | None" = None

    def __new__(cls) -> "Predictor":
        """Create or return the singleton instance of Predictor."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def get_threshold(cls) -> float:
        """Get the prediction probability threshold from config.

        Returns:
            The threshold value as a float.
        """
        settings = get_settings()
        return settings.prediction_probability_threshold

    @classmethod
    def start_prediction(cls, prediction_request: PredictionRequest) -> None:
        """Start a prediction task with the given request.

        Args:
            prediction_request: The prediction request containing data.
        """
        future: Future = cls._get_executor().submit(
            cls._run_prediction, prediction_request)
        TaskService().service_queue.put((prediction_request, future))

    @classmethod
    def _run_prediction(cls, prediction_request: PredictionRequest) -> PredictionRequest:
        """Run prediction on the provided request.

        Args:
            prediction_request: The prediction request containing data.

        Returns:
            The prediction request with results.
        """
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
            logging.error("Prediction error: %s", exception)

        return prediction_request

    @classmethod
    def _filter_uncertainty(cls, prediction_probability: Any,
                            predicted_labels: list[str]) -> None:
        """Filter predictions below the probability threshold.

        Args:
            prediction_probability: Array of prediction probabilities.
            predicted_labels: List of predicted labels to modify.
        """
        threshold = cls.get_threshold()
        for ctr, probability in enumerate(prediction_probability):
            if probability.max() < threshold:
                predicted_labels[ctr] = 'Unknown'


class Ghidra(TaskManager):
    """Task manager for running Ghidra analysis on binaries."""

    @classmethod
    def start_task(cls, ghidra_request: GhidraRequest) -> None:
        """Start a Ghidra analysis task.

        Args:
            ghidra_request: The Ghidra request containing analysis parameters.
        """
        future: Future = cls._get_executor().submit(cls._run_analysis, ghidra_request)
        TaskService().service_queue.put((ghidra_request, future))

    @classmethod
    def _run_analysis(cls, ghidra_request: GhidraRequest) -> None:
        """Run Ghidra analysis on the provided binary.

        Args:
            ghidra_request: The Ghidra request containing analysis parameters.
        """
        settings = get_settings()
        ghidra_location = settings.ghidra_location
        ghidra_project_name = settings.ghidra_project_name
        ghidra_project_location = settings.ghidra_project_location
        glyph_script_location = settings.glyph_script_location

        ghidra_headless_location: str = os.path.join(
            ghidra_location, f"support{os.sep}analyzeHeadless")

        ghidra_type: str | None = None
        if ghidra_request.is_training == "true":
            ghidra_type = "training"
        else:
            ghidra_type = "prediction"

        #TODO fix this junk and fix clanker garbage
        file_path: str = os.path.join("./binaries", ghidra_request.file_name)
        results = ghidra_processor.analyze_binary_and_decompile(file_path)

