import logging
import joblib
from io import BytesIO
from typing import Any, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from app.request_handler import Prediction, PredictionRequest, TrainingRequest
from app.sql_service import SQLUtil

# === Type aliases for clarity ===
ModelRow = Tuple[str, bytes, bytes]  # (model_name, model_blob, encoder_blob)


class MLTask:
    @staticmethod
    def get_multi_class_pipeline() -> Pipeline:
        return Pipeline(
            [
                (
                    "preprocessor",
                    TfidfVectorizer(ngram_range=(2, 4), norm="l2", sublinear_tf=True),
                ),
                ("clf", MultinomialNB(alpha=1e-8)),
            ]
        )

    @staticmethod
    def get_single_class_pipeline() -> Pipeline:
        # TODO: Replace with dedicated algorithm when implemented
        return Pipeline(
            [
                (
                    "preprocessor",
                    TfidfVectorizer(ngram_range=(2, 4), norm="l2", sublinear_tf=True),
                ),
                ("clf", MultinomialNB(alpha=1e-8)),
            ]
        )


class PredictionPersistanceUtil:
    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        predictions_list: list[Prediction] = SQLUtil.get_predictions_list()
        return predictions_list

    @staticmethod
    def get_predictions(task_name: str, model_name: str) -> Prediction:
        if not task_name or not model_name:
            raise ValueError("task_name and model_name must be non-empty strings")
        prediction: Optional[Prediction] = SQLUtil.get_predictions(task_name, model_name)
        if prediction is None:
            raise ValueError(
                f"Prediction for task '{task_name}' with model '{model_name}' not found."
            )
        return prediction

    @staticmethod
    def delete_prediction(task_name: str):
        if not task_name:
            raise ValueError("task_name must be a non-empty string")
        SQLUtil.delete_prediction(task_name)

    @staticmethod
    def delete_model_predictions(model_name: str):
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        SQLUtil.delete_model_predictions(model_name)


class MLPersistanceUtil:
    @staticmethod
    def save_model(model_name: str, label_encoder: Any, pipeline: Pipeline) -> None:
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

            SQLUtil.save_model(model_name, serialized_encoder, serialized_model)

        except Exception as e:
            logging.error(f"Failed to serialize model or encoder for '{model_name}': {e}")
            raise RuntimeError(f"Could not serialize model data for '{model_name}'") from e

    @staticmethod
    def load_model(model_name: str) -> Tuple[Any, Any]:
        if not model_name:
            raise ValueError("model_name must be a non-empty string")

        model_row: Optional[Tuple[Any, ...]] = SQLUtil.get_model(model_name)

        if model_row is None:
            logging.error(f"Model '{model_name}' not found in database")
            raise ValueError(f"Model '{model_name}' not found.")

        if len(model_row) < 3:
            logging.error(
                f"Model '{model_name}' has invalid schema (expected 3 fields, got {len(model_row)})"
            )
            raise ValueError(
                f"Model '{model_name}' data has incorrect structure (expected 3 fields, got {len(model_row)})"
            )

        try:
            model_buffer = BytesIO(model_row[1])
            loaded_model = joblib.load(model_buffer)

            encoder_buffer = BytesIO(model_row[2])
            label_encoder = joblib.load(encoder_buffer)

            return loaded_model, label_encoder

        except Exception as e:
            logging.error(
                f"Failed to deserialize model '{model_name}': {type(e).__name__}: {e}"
            )
            raise RuntimeError(f"Could not deserialize model data for '{model_name}'") from e

    @staticmethod
    def get_models_list() -> set[str]:
        models_list: set[str] = SQLUtil.get_models_list()
        return models_list

    @staticmethod
    def check_name(model_name: str) -> bool:
        if not model_name:
            return False
        models_list: set[str] = SQLUtil.get_models_list()
        return model_name in models_list

    @staticmethod
    def delete_model(model_name: str):
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        SQLUtil.delete_model(model_name)


class FunctionPersistanceUtil:
    @staticmethod
    def get_functions(model_name: str) -> list:
        if not model_name:
            raise ValueError("model_name must be a non-empty string")
        functions: list = SQLUtil.get_functions(model_name)
        return functions if functions else []

    @staticmethod
    def get_function(model_name: str, function_name: str) -> dict:
        if not model_name or not function_name:
            raise ValueError("model_name and function_name must be non-empty strings")
        function: list = SQLUtil.get_function(model_name, function_name)
        return function[0] if function else {}

    @staticmethod
    def add_model_functions(training_request: TrainingRequest) -> None:
        if training_request is None:
            raise ValueError("training_request must not be None")
        functions: list = training_request.get_functions() or []
        if functions:
            SQLUtil.save_functions(training_request.model_name, functions)

    @staticmethod
    def add_prediction_functions(
        prediction_request: PredictionRequest, predictions: list[str]
    ) -> None:
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
            SQLUtil.save_predictions(task_name, prediction_request.model_name, functions)
        elif functions:
            logging.warning(
                f"Mismatch between functions ({len(functions)}) and predictions ({len(predictions)}) "
                f"for task '{task_name}'"
            )

    @staticmethod
    def get_prediction_function(
        task_name: str, model_name: str, function_name: str
    ) -> dict:
        if not task_name or not model_name or not function_name:
            raise ValueError("All arguments must be non-empty strings")
        result: dict = SQLUtil.get_prediction_function(
            task_name, model_name, function_name
        )
        if result is None:
            raise ValueError(
                f"Prediction function for task '{task_name}', model '{model_name}', function '{function_name}' not found."
            )
        return result
