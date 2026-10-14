"""Prediction service for Glyph application.

Handles retrieval, listing, deletion, and persistence of prediction
results.
"""

from typing import Any

from loguru import logger

from app.database.prediction_repository import PredictionRepository
from app.exceptions import PredictionNotFoundError
from app.services.request_handler import PredictionRequest
from app.utils.common import format_code


class PredictionService:
    """Service for prediction workflow management.

    Encapsulates business logic for creating prediction tasks, executing
    the ML prediction pipeline, retrieving results, and managing
    prediction lifecycle.
    """

    # --- Task Creation ---

    @staticmethod
    async def check_task_name_unique(task_name: str) -> bool:
        """Check whether a task name already exists among predictions.

        Despite the method name, this reports *existence*: it returns True
        when the task name is already taken (i.e. not unique).

        Args:
            task_name: The task name to check.

        Returns:
            True if the task name already exists (is not unique), False otherwise.

        """
        return await PredictionRepository.task_name_exists(task_name)

    # --- Query Operations ---

    @staticmethod
    async def get_predictions_list(
        user_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get a paginated list of prediction metadata for a user.

        Uses a lightweight metadata-only query that does not deserialize the
        ``functions_data`` BLOBs, and scopes the result to the rows the user
        may access (own + legacy/unowned).

        Args:
            user_id: The current user's id (0 for anonymous).
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (metadata list, total count). Each metadata item is a
            dict with ``task_name``, ``model_name``, ``function_count`` and
            ``user_id``.

        """
        all_predictions = await PredictionRepository.get_predictions_metadata_for_user(user_id)
        total = len(all_predictions)
        page_predictions = all_predictions[offset : offset + limit]
        return page_predictions, total

    @staticmethod
    async def get_prediction(
        task_name: str,
        model_name: str,
    ) -> Any:
        """Get a single prediction result.

        Args:
            task_name: The prediction task name.
            model_name: The model name used for prediction.

        Returns:
            PredictionResult object.

        Raises:
            PredictionNotFoundError: If prediction does not exist.

        """
        prediction = await PredictionRepository.get(task_name, model_name)
        if prediction is None:
            raise PredictionNotFoundError(task_name, model_name)
        return prediction

    @staticmethod
    async def get_prediction_function_details(
        task_name: str,
        model_name: str,
        function_name: str,
    ) -> tuple[dict[str, Any], str]:
        """Fetch a single function's prediction data and its formatted tokens.

        Shared core for the ``getPredictionDetails`` endpoints. The raw
        prediction data is returned alongside the formatted tokens so callers
        can apply their own presence checks (404 vs. placeholder) before
        rendering.

        Args:
            task_name: The prediction task name.
            model_name: The model name used for prediction.
            function_name: The function to retrieve details for.

        Returns:
            Tuple of (raw prediction data, formatted prediction tokens). The
            data dict is empty when no prediction exists for the function, and
            the tokens string is empty in that case as well.

        """
        prediction_data = await PredictionRepository.get_prediction_function(
            task_name, model_name, function_name,
        )
        prediction_tokens = format_code(prediction_data.get("tokens", "") if prediction_data else "")
        return prediction_data, prediction_tokens

    # --- Deletion ---

    @staticmethod
    async def delete_prediction(
        task_name: str,
        model_name: str | None = None,
    ) -> None:
        """Delete a prediction task.

        Args:
            task_name: The prediction task name to delete.
            model_name: Optional model name to scope the deletion.

        """
        await PredictionRepository.delete(task_name, model_name)
        logger.info("Prediction deleted: task_name={}, model_name={}", task_name, model_name)

    @staticmethod
    async def delete_predictions_for_model(model_name: str) -> None:
        """Delete all predictions for a given model.

        Args:
            model_name: The model whose predictions should be deleted.

        """
        await PredictionRepository.delete_model_predictions(model_name)
        logger.info("All predictions deleted for model: {}", model_name)

    # --- Prediction Persistence ---

    @staticmethod
    async def save_prediction_functions(
        prediction_request: "PredictionRequest", predictions: list[str],
    ) -> None:
        """Merge predictions with functions and persist to database.

        Args:
            prediction_request: The prediction request containing functions.
            predictions: List of predicted labels.

        """
        functions: list[dict[str, Any]] = prediction_request.get_functions() or []
        task_name = prediction_request.task_name

        if functions and len(functions) == len(predictions):
            for ctr, function in enumerate(functions):
                updated_function = function.copy()
                updated_function["prediction"] = predictions[ctr]
                functions[ctr] = updated_function
            await PredictionRepository.save(
                task_name, prediction_request.model_name, functions, user_id=prediction_request.user_id,
            )
        elif functions:
            logger.warning(
                "Mismatch between functions (%d) and predictions (%d) for task '%s'",
                len(functions),
                len(predictions),
                task_name,
            )
