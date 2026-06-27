"""Prediction service for Glyph application.

Handles prediction workflow including task creation, execution,
retrieval, and deletion of prediction results.
"""

from typing import Any

from loguru import logger

from app.database.function_repository import FunctionRepository
from app.database.model_repository import ModelRepository
from app.database.prediction_repository import PredictionRepository
from app.exceptions import (
    ModelNotFoundError,
    PredictionNotFoundError,
    TaskNameExistsError,
    ValidationError,
)
from app.processing.pipeline import PipelineContext
from app.processing.pipeline_configs import ML_PREDICTION_ONLY_PIPELINE
from app.services.request_handler import PredictionRequest


class PredictionService:
    """Service for prediction workflow management.

    Encapsulates business logic for creating prediction tasks, executing
    the ML prediction pipeline, retrieving results, and managing
    prediction lifecycle.
    """

    # --- Task Creation ---

    @staticmethod
    async def validate_task_name(task_name: str) -> str:
        """Validate and normalize the task name.

        Args:
            task_name: Raw task name from the request.

        Returns:
            Stripped task name.

        Raises:
            ValidationError: If task name is empty or whitespace only.
        """
        stripped = task_name.strip()
        if not stripped:
            raise ValidationError("taskName is required for predictions")
        return stripped

    @staticmethod
    async def check_task_name_unique(task_name: str) -> bool:
        """Check if a task name is unique among existing predictions.

        Args:
            task_name: The task name to check.

        Returns:
            True if the task name is unique, False otherwise.
        """
        return await PredictionRepository.task_name_exists(task_name)

    @staticmethod
    async def verify_model_exists(model_name: str) -> None:
        """Verify that a model exists in the database.

        Args:
            model_name: The model name to verify.

        Raises:
            ModelNotFoundError: If the model does not exist.
        """
        model = await ModelRepository.get(model_name)
        if model is None:
            raise ModelNotFoundError(model_name)

    async def create_prediction_task(
        self,
        task_name: str,
        model_name: str,
        data: dict[str, Any],
        req_uuid: str,
    ) -> PredictionRequest:
        """Validate and prepare a prediction request.

        Checks task name uniqueness and model existence before creating
        the PredictionRequest.

        Args:
            task_name: Name of the task (binary) to predict on.
            model_name: Name of the trained model to use.
            data: Raw request data containing functions.
            req_uuid: UUID for this prediction task.

        Returns:
            Validated PredictionRequest instance.

        Raises:
            ValidationError: If task name is invalid.
            TaskNameExistsError: If task name already exists.
            ModelNotFoundError: If model does not exist.
        """
        # Validate task name
        validated_name = await self.validate_task_name(task_name)

        # Check uniqueness
        exists = await self.check_task_name_unique(validated_name)
        if exists:
            raise TaskNameExistsError(validated_name)

        # Verify model exists
        await self.verify_model_exists(model_name)

        # Create and return the prediction request
        prediction_request = PredictionRequest(req_uuid, model_name, data)
        logger.info(
            "Prediction task created: uuid={}, task_name={}, model_name={}",
            req_uuid,
            validated_name,
            model_name,
        )
        return prediction_request

    # --- Execution ---

    @staticmethod
    async def execute_prediction(
        prediction_request: PredictionRequest,
    ) -> list[str]:
        """Execute the ML prediction pipeline and persist results.

        Runs tokenization, filtering, feature extraction, and prediction
        steps using the ProcessingPipeline framework, then saves the
        predictions to the database.

        Args:
            prediction_request: The prediction request containing functions to analyze.

        Returns:
            List of predicted labels.

        Raises:
            RuntimeError: If pipeline execution fails.
        """
        functions = prediction_request.get_functions()

        context = PipelineContext(
            uuid=prediction_request.uuid,
            binary_path="",
            pipeline_type="ml_prediction",
            metadata={
                "model_name": prediction_request.model_name,
                "task_name": prediction_request.task_name,
            },
        )
        context.set("functions", functions)

        result = await ML_PREDICTION_ONLY_PIPELINE.execute(context)

        if result.error:
            raise RuntimeError(result.error)

        # Persist prediction results to the database
        predictions: list[str] = result.get("predictions") or []
        if predictions:
            await PredictionService._persist_predictions(prediction_request, predictions)
            logger.info(
                "Prediction task completed and saved: {} ({} predictions)",
                prediction_request.uuid,
                len(predictions),
            )
        else:
            logger.warning(
                "Prediction task completed but no predictions to save: {}",
                prediction_request.uuid,
            )

        return predictions

    @staticmethod
    async def _persist_predictions(
        prediction_request: PredictionRequest,
        predictions: list[str],
    ) -> None:
        """Save prediction results to the database.

        Args:
            prediction_request: The prediction request with function data.
            predictions: List of predicted labels matching functions order.
        """
        functions: list[dict[str, Any]] = prediction_request.get_functions() or []
        task_name = prediction_request.task_name

        if functions and len(functions) == len(predictions):
            for ctr, function in enumerate(functions):
                updated_function = function.copy()
                updated_function["prediction"] = predictions[ctr]
                functions[ctr] = updated_function
            await PredictionRepository.save(
                task_name, prediction_request.model_name, functions
            )
        elif functions:
            logger.warning(
                "Mismatch between functions ({}) and predictions ({}) for task '{}'",
                len(functions),
                len(predictions),
                task_name,
            )

    # --- Query Operations ---

    @staticmethod
    async def get_predictions_list(
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Any], int]:
        """Get paginated list of all predictions.

        Args:
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (predictions list, total count).
        """
        all_predictions = await PredictionRepository.get_predictions_list()
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
    async def get_prediction_details(
        task_name: str,
        model_name: str,
        function_name: str,
    ) -> tuple[Any, dict[str, Any] | None]:
        """Get detailed prediction results for a specific function.

        Retrieves both the model function data and the prediction function data
        for comparison.

        Args:
            task_name: The prediction task name.
            model_name: The model name used for prediction.
            function_name: The specific function to retrieve details for.

        Returns:
            Tuple of (model_function, prediction_function_dict).

        Raises:
            ValidationError: If arguments are empty.
        """
        if not task_name or not model_name or not function_name:
            raise ValidationError("task_name, model_name, and function_name must be non-empty")

        model_function = await FunctionRepository.get(model_name, function_name)
        if model_function is None:
            raise ValidationError(f"Function '{function_name}' not found in model '{model_name}'")

        try:
            prediction_data = await PredictionRepository.get_prediction_function(
                task_name, model_name, function_name
            )
        except Exception:
            prediction_data = None

        return model_function, prediction_data

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

        Raises:
            PredictionNotFoundError: If prediction does not exist.
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
