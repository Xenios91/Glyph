"""Repository for prediction database operations."""

import logging
import pickle
from io import BytesIO

import joblib

from app.database.models import Prediction
from app.database.session_handler import get_session

logger = logging.getLogger(__name__)


class PredictionRepository:
    """Repository for managing prediction data in the database."""

    @staticmethod
    def save_predictions(task_name: str, model_name: str, functions: list) -> Prediction:
        """Save predictions to the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model used.
            functions: List of function predictions to save.

        Returns:
            The created Prediction instance.
        """
        with get_session("predictions") as session:
            # Serialize functions
            functions_buffer = BytesIO()
            joblib.dump(functions, functions_buffer)
            functions_bytes = functions_buffer.getvalue()

            # Create prediction instance
            prediction = Prediction(
                task_name=task_name,
                model_name=model_name,
                functions_data=functions_bytes,
            )
            session.add(prediction)
            return prediction

    @staticmethod
    def get_predictions_list() -> list[Prediction]:
        """Get the list of all predictions from the database.

        Returns:
            A list of Prediction instances.
        """
        with get_session("predictions") as session:
            return session.query(Prediction).all()

    @staticmethod
    def get_prediction(task_name: str, model_name: str) -> Prediction | None:
        """Retrieve a prediction from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.

        Returns:
            The Prediction instance if found, otherwise None.
        """
        with get_session("predictions") as session:
            prediction = (
                session.query(Prediction)
                .filter(Prediction.task_name == task_name, Prediction.model_name == model_name)
                .first()
            )
            return prediction

    @staticmethod
    def get_prediction_functions(task_name: str, model_name: str) -> list | None:
        """Retrieve and deserialize prediction functions from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.

        Returns:
            List of function predictions if found, otherwise None.
        """
        prediction = PredictionRepository.get_prediction(task_name, model_name)
        if prediction is None:
            return None

        try:
            functions = joblib.load(BytesIO(prediction.functions_data))
            if not isinstance(functions, list):
                logger.warning(
                    "Prediction data for task '%s' is not a list, expected list got %s",
                    task_name,
                    type(functions).__name__,
                )
                return None
            return functions
        except (pickle.UnpicklingError, EOFError, ValueError, OSError) as exc:
            logger.error("Failed to deserialize prediction for task '%s': %s", task_name, exc)
            return None

    @staticmethod
    def get_prediction_function(task_name: str, model_name: str, function_name: str) -> dict | None:
        """Get a specific function prediction from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            function_name: Name of the function to retrieve.

        Returns:
            Dictionary containing function prediction data, or None if not found.
        """
        functions = PredictionRepository.get_prediction_functions(task_name, model_name)
        if functions is None:
            return None

        for function in functions:
            if isinstance(function, dict) and function.get("functionName") == function_name:
                return function
        return None

    @staticmethod
    def delete_prediction(task_name: str) -> bool:
        """Delete a prediction from the database.

        Args:
            task_name: Name of the task to delete.

        Returns:
            True if the prediction was deleted, False if not found.
        """
        with get_session("predictions") as session:
            prediction = session.query(Prediction).filter(Prediction.task_name == task_name).first()
            if prediction:
                session.delete(prediction)
                logger.info("Prediction '%s' deleted successfully.", task_name)
                return True
            logger.warning("Prediction '%s' not found for deletion.", task_name)
            return False

    @staticmethod
    def delete_model_predictions(model_name: str) -> int:
        """Delete all predictions for a model from the database.

        Args:
            model_name: Name of the model.

        Returns:
            Number of predictions deleted.
        """
        with get_session("predictions") as session:
            result = session.query(Prediction).filter(Prediction.model_name == model_name).delete()
            logger.info("Deleted %d predictions for model '%s'.", result, model_name)
            return result

    @staticmethod
    def task_name_exists(task_name: str) -> bool:
        """Check if a task name already exists in the predictions database.

        Args:
            task_name: Name of the task to check.

        Returns:
            True if the task name exists, False otherwise.
        """
        with get_session("predictions") as session:
            count = session.query(Prediction).filter(Prediction.task_name == task_name).count()
            return count > 0
