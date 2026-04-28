"""Persistence utilities for ML models and predictions."""

from io import BytesIO
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from app.database.models import Function as FunctionModel
from app.database.sql_service import SQLUtil
from app.services.request_handler import Prediction, PredictionRequest, TrainingRequest
from loguru import logger
from app.utils.secure_deserializer import secure_load, SecureDeserializationError


class MLTask:
    """ML pipeline configuration."""

    @staticmethod
    def get_multi_class_pipeline() -> Pipeline:
        """Get a multi-class classification pipeline.

        Returns:
            A configured sklearn Pipeline with TF-IDF and Naive Bayes.
        """
        return Pipeline(
            [
                (
                    "preprocessor",
                    TfidfVectorizer(ngram_range=(2, 4), norm="l2", sublinear_tf=True)),
                ("clf", MultinomialNB(alpha=1e-8)),
            ]
        )


class PredictionPersistanceUtil:
    """Persistence utilities for predictions."""

    @staticmethod
    async def get_predictions_list() -> list[Prediction]:
        """Get a list of all predictions.

        Returns:
            List of Prediction objects from the database.
        """
        return await SQLUtil.get_predictions_list()

    @staticmethod
    async def get_predictions(task_name: str, model_name: str) -> Prediction:
        """Get a prediction by task and model name.

        Args:
            task_name: The task name.
            model_name: The model name.

        Returns:
            The Prediction object.

        Raises:
            ValueError: If task_name or model_name is empty, or prediction not found.
        """
        if not task_name or not model_name:
            raise ValueError("task_name and model_name must be non-empty strings")
        prediction: Prediction | None = await SQLUtil.get_predictions(task_name, model_name)
        if prediction is None:
            raise ValueError(
                f"Prediction for task '{task_name}' with model '{model_name}' not found."
            )
        return prediction

    @staticmethod
    async def delete_prediction(task_name: str) -> None:
        """Delete a prediction by task name.

        Args:
            task_name: The task name to delete.

        Raises:
            ValueError: If task_name is empty.
        """
        if not task_name:
            raise ValueError("task_name must be a non-empty string")
        await SQLUtil.delete_prediction(task_name)

    @staticmethod
    async def delete_model_predictions(model_name: str) -> None:
        """Delete all predictions for a model.

        Args:
            model_name: The model name.

        Raises:
            ValueError: If model_name is empty.
        """
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        await SQLUtil.delete_model_predictions(model_name)

    @staticmethod
    async def is_task_name_unique(task_name: str) -> bool:
        """Check if a task name is unique (does not exist in the database).

        Args:
            task_name: The task name to check.

        Returns:
            True if the task name is unique, False if it already exists.
        """
        if not task_name:
            raise ValueError("task_name must be a non-empty string")
        return not await SQLUtil.task_name_exists(task_name)


class MLPersistanceUtil:
    """Persistence utilities for ML models."""

    @staticmethod
    async def save_model(model_name: str, label_encoder: Any, pipeline: Pipeline) -> None:
        """Save a model and label encoder to the database.

        Args:
            model_name: The model name.
            label_encoder: The label encoder to save.
            pipeline: The sklearn pipeline to save.

        Raises:
            ValueError: If model_name is empty or parameters are None.
            RuntimeError: If serialization fails.
        """
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        if pipeline is None:
            raise ValueError("pipeline must not be None")
        if label_encoder is None:
            raise ValueError("label_encoder must not be None")

        try:
            model_buffer = BytesIO()
            joblib.dump(pipeline, model_buffer)
            serialized_model = model_buffer.getvalue()

            encoder_buffer = BytesIO()
            joblib.dump(label_encoder, encoder_buffer)
            serialized_encoder = encoder_buffer.getvalue()

            await SQLUtil.save_model(model_name, serialized_encoder, serialized_model)
        except Exception as error:
            logger.exception("Failed to serialize model '{}'", model_name)
            raise RuntimeError(
                f"Could not serialize model data for '{model_name}'"
            ) from error

    @staticmethod
    async def load_model(model_name: str) -> tuple[Any, Any]:
        """Load a model and label encoder from the database.

        Args:
            model_name: The model name.

        Returns:
            A tuple of (loaded_model, label_encoder).

        Raises:
            ValueError: If model_name is empty or model not found.
            RuntimeError: If deserialization fails.
        """
        if not model_name:
            raise ValueError("model_name must be a non-empty string")

        model_row = await SQLUtil.get_model(model_name)

        if model_row is None:
            logger.error("Model '{}' not found in database", model_name)
            raise ValueError(f"Model '{model_name}' not found.")

        try:
            model_buffer = BytesIO(model_row.model_data)
            loaded_model = secure_load(model_buffer)

            encoder_buffer = BytesIO(model_row.label_encoder_data)
            label_encoder = secure_load(encoder_buffer)

            return loaded_model, label_encoder
        except SecureDeserializationError as error:
            logger.exception(
                "Secure deserialization blocked model '{}'", model_name)
            raise RuntimeError(
                f"Model data for '{model_name}' failed security validation"
            ) from error
        except Exception as error:
            logger.exception(
                "Failed to deserialize model '{}'", model_name)
            raise RuntimeError(
                f"Could not deserialize model data for '{model_name}'"
            ) from error

    @staticmethod
    async def get_models_list() -> set[str]:
        """Get a list of all model names.

        Returns:
            A set of model names.
        """
        return await SQLUtil.get_models_list()

    @staticmethod
    async def check_name(model_name: str) -> bool:
        """Check if a model name exists.

        Uses an EXISTS subquery for O(1) performance instead of fetching
        all model names into memory.

        Args:
            model_name: The model name to check.

        Returns:
            True if the model exists, False otherwise.
        """
        if not model_name:
            return False
        return await SQLUtil.model_name_exists(model_name)

    @staticmethod
    async def delete_model(model_name: str) -> None:
        """Delete a model from the database.

        Args:
            model_name: The model name to delete.

        Raises:
            ValueError: If model_name is empty.
        """
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        await SQLUtil.delete_model(model_name)


class FunctionPersistanceUtil:
    """Persistence utilities for functions."""

    @staticmethod
    async def get_functions(model_name: str) -> list[FunctionModel]:
        """Get functions for a model.

        Args:
            model_name: The model name.

        Returns:
            A list of Function ORM objects.

        Raises:
            ValueError: If model_name is empty.
        """
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        functions: list[FunctionModel] = await SQLUtil.get_functions(model_name)
        return functions if functions else []

    @staticmethod
    async def get_function(model_name: str, function_name: str) -> FunctionModel | None:
        """Get a specific function by name.

        Args:
            model_name: The model name.
            function_name: The function name.

        Returns:
            The Function ORM object or None.

        Raises:
            ValueError: If model_name or function_name is empty.
        """
        if not model_name or not function_name:
            raise ValueError("model_name and function_name must be non-empty strings")
        return await SQLUtil.get_function(model_name, function_name)

    @staticmethod
    async def add_model_functions(training_request: TrainingRequest) -> None:
        """Add functions from a training request to the database.

        Args:
            training_request: The training request containing functions.

        Raises:
            ValueError: If training_request is None.
        """
        if training_request is None:
            raise ValueError("training_request must not be None")
        functions: list = training_request.get_functions() or []
        if functions:
            await SQLUtil.save_functions(training_request.model_name, functions)

    @staticmethod
    async def add_prediction_functions(
        prediction_request: PredictionRequest, predictions: list[str]
    ) -> None:
        """Add prediction functions to the database.

        Args:
            prediction_request: The prediction request.
            predictions: List of predicted labels.

        Raises:
            ValueError: If prediction_request or predictions is None.
            TypeError: If predictions is not a list.
        """
        if prediction_request is None:
            raise ValueError("prediction_request must not be None")
        if predictions is None:
            raise ValueError("predictions must not be None")
        if not isinstance(predictions, list):
            raise TypeError("predictions must be a list")

        functions: list = prediction_request.get_functions() or []
        task_name = prediction_request.task_name

        if functions and len(functions) == len(predictions):
            for ctr, function in enumerate(functions):
                updated_function = function.copy()
                updated_function["functionName"] = predictions[ctr]
                functions[ctr] = updated_function
            await SQLUtil.save_predictions(
                task_name, prediction_request.model_name, functions
            )
        elif functions:
            logger.warning(
                "Mismatch between functions ({}) and predictions ({}) for task '{}'",
                len(functions),
                len(predictions),
                task_name,
            )

    @staticmethod
    async def get_prediction_function(
        task_name: str, model_name: str, function_name: str
    ) -> dict:
        """Get a prediction function by task, model, and function name.

        Args:
            task_name: The task name.
            model_name: The model name.
            function_name: The function name.

        Returns:
            The prediction function dictionary.

        Raises:
            ValueError: If any argument is empty or function not found.
        """
        if not task_name or not model_name or not function_name:
            raise ValueError("All arguments must be non-empty strings")
        result: dict = await SQLUtil.get_prediction_function(
            task_name, model_name, function_name
        )
        if not result:
            raise ValueError(
                f"Prediction function for task '{task_name}', model '{model_name}', function '{function_name}' not found."
            )
        return result
