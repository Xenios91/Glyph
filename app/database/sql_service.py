"""SQL utility module for database operations using SQLAlchemy ORM.

This module acts as a thin facade that delegates to entity-specific repository
classes, maintaining backward compatibility for all existing callers.

.. deprecated::
    SQLUtil is deprecated. Use the corresponding repository classes directly:
    :class:`~app.database.binary_repository.BinaryRepository`,
    :class:`~app.database.function_repository.FunctionRepository`,
    :class:`~app.database.model_repository.ModelRepository`,
    :class:`~app.database.prediction_repository.PredictionRepository`,
    :class:`~app.database.similarity_repository.SimilarityRepository`.
"""

import warnings
from typing import Any

from loguru import logger

from app.database.binary_repository import BinaryRepository
from app.database.function_repository import FunctionRepository
from app.database.model_repository import ModelRepository
from app.database.prediction_repository import PredictionRepository
from app.database.similarity_repository import SimilarityRepository

warnings.warn(
    "SQLUtil is deprecated. Use the corresponding repository classes directly "
    "(BinaryRepository, FunctionRepository, ModelRepository, PredictionRepository, SimilarityRepository).",
    DeprecationWarning,
    stacklevel=2,
)


class SQLUtil:
    """Utility class for SQLite database operations using SQLAlchemy ORM.

    .. deprecated::
        Use the corresponding repository classes directly instead of this facade.

    All methods are async and delegate to entity-specific repository classes.
    This facade maintains backward compatibility with existing callers.
    """

    @staticmethod
    async def init_db() -> None:
        """Initialize the database tables.

        This is now a no-op since tables are created by init_async_databases()
        in session_handler.py which uses Base.metadata.create_all.
        Kept for API compatibility with existing callers.
        """
        logger.debug("Database tables managed by async session handler")

    # ------------------------------------------------------------------
    # Model operations
    # ------------------------------------------------------------------

    @staticmethod
    async def save_model(model_name: str, label_encoder: bytes, model: bytes) -> None:
        """Save or update a model in the models database."""
        await ModelRepository.save(model_name=model_name, label_encoder=label_encoder, model=model)

    @staticmethod
    async def get_models_list() -> set[str]:
        """Get the list of model names from the database."""
        return await ModelRepository.get_models_list()

    @staticmethod
    async def get_model(model_name: str) -> Any:
        """Retrieve a model from the database."""
        return await ModelRepository.get(model_name=model_name)

    @staticmethod
    async def delete_model(model_name: str) -> None:
        """Delete a model and all associated data from the database.

        Deletes associated predictions, functions, and the model itself.
        """
        await SQLUtil.delete_model_predictions(model_name)
        await SQLUtil.delete_functions(model_name)
        await ModelRepository.delete(model_name=model_name)

    @staticmethod
    async def model_name_exists(model_name: str) -> bool:
        """Check if a model name already exists in the models database."""
        return await ModelRepository.exists(model_name=model_name)

    # ------------------------------------------------------------------
    # Prediction operations
    # ------------------------------------------------------------------

    @staticmethod
    async def get_predictions_list() -> list[Any]:
        """Get the list of all predictions from the database."""
        return await PredictionRepository.get_predictions_list()

    @staticmethod
    async def get_predictions(task_name: str, model_name: str) -> Any:
        """Retrieve and deserialize a Prediction object from the database."""
        return await PredictionRepository.get(task_name=task_name, model_name=model_name)

    @staticmethod
    async def save_predictions(name: str, model_name: str, functions: list[Any]) -> None:
        """Save or update predictions in the database."""
        await PredictionRepository.save(name=name, model_name=model_name, functions=functions)

    @staticmethod
    async def get_prediction_function(task_name: str, model_name: str, function_name: str) -> dict[str, Any]:
        """Get a specific function prediction from the database."""
        return await PredictionRepository.get_prediction_function(
            task_name=task_name, model_name=model_name, function_name=function_name,
        )

    @staticmethod
    async def delete_prediction(task_name: str, model_name: str | None = None) -> None:
        """Delete a prediction from the database."""
        await PredictionRepository.delete(task_name=task_name, model_name=model_name)

    @staticmethod
    async def delete_model_predictions(model_name: str) -> None:
        """Delete all predictions for a model from the database."""
        await PredictionRepository.delete_model_predictions(model_name=model_name)

    @staticmethod
    async def task_name_exists(task_name: str) -> bool:
        """Check if a task name already exists in the predictions database."""
        return await PredictionRepository.task_name_exists(task_name=task_name)

    # ------------------------------------------------------------------
    # Function operations
    # ------------------------------------------------------------------

    @staticmethod
    async def save_functions(model_name: str, functions: list[dict[str, Any]]) -> None:
        """Save or update functions in the functions database."""
        await FunctionRepository.save(model_name=model_name, functions=functions)

    @staticmethod
    async def get_functions(model_name: str) -> list[Any]:
        """Get all functions for a model from the database."""
        return await FunctionRepository.get_functions(model_name=model_name)

    @staticmethod
    async def get_function(model_name: str, function_name: str) -> Any:
        """Get a specific function from the database."""
        return await FunctionRepository.get(model_name=model_name, function_name=function_name)

    @staticmethod
    async def delete_functions(model_name: str) -> None:
        """Delete all functions for a model from the database."""
        await FunctionRepository.delete(model_name=model_name)

    # ------------------------------------------------------------------
    # Binary & BinaryFunction operations
    # ------------------------------------------------------------------

    @staticmethod
    async def save_binary(
        name: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        uploaded_by: int,
    ) -> int:
        """Save binary metadata and return the new binary id."""
        return await BinaryRepository.save_binary(
            name=name, file_path=file_path, file_size=file_size, mime_type=mime_type, uploaded_by=uploaded_by,
        )

    @staticmethod
    async def get_binary(binary_id: int) -> Any:
        """Retrieve a binary by its id."""
        return await BinaryRepository.get(binary_id=binary_id)

    @staticmethod
    async def count_binaries_by_user(user_id: int) -> int:
        """Count the number of binaries uploaded by a specific user."""
        return await BinaryRepository.count_by_user(user_id=user_id)

    @staticmethod
    async def count_binary_functions(binary_id: int) -> int:
        """Count the number of functions for a specific binary."""
        return await BinaryRepository.count_functions(binary_id=binary_id)

    @staticmethod
    async def get_binaries_by_user(user_id: int, *, offset: int = 0, limit: int = 50) -> list[Any]:
        """List binaries uploaded by a specific user with pagination."""
        return await BinaryRepository.get_by_user(user_id=user_id, offset=offset, limit=limit)

    @staticmethod
    async def delete_binary(binary_id: int) -> None:
        """Delete a binary and all its associated functions."""
        await BinaryRepository.delete(binary_id=binary_id)

    @staticmethod
    async def save_binary_functions(binary_id: int, functions: list[dict[str, Any]]) -> None:
        """Save raw decompiled functions for a binary."""
        await BinaryRepository.save_functions(binary_id=binary_id, functions=functions)

    @staticmethod
    async def get_binary_functions(binary_id: int, offset: int = 0, limit: int | None = None) -> list[Any]:
        """Load raw functions for a binary with optional pagination."""
        return await BinaryRepository.get_functions(binary_id=binary_id, offset=offset, limit=limit)

    @staticmethod
    async def get_all_binary_ids() -> list[int]:
        """Return every binary id in the database."""
        return await BinaryRepository.get_all_ids()

    @staticmethod
    async def get_binary_name(binary_id: int) -> str | None:
        """Return the human-readable name for a binary."""
        return await BinaryRepository.get_name(binary_id=binary_id)

    # ------------------------------------------------------------------
    # Similarity computation operations
    # ------------------------------------------------------------------

    @staticmethod
    async def create_similarity_computation(
        task_name: str,
        computed_by: int,
        binary_count: int,
        status: str = "pending",
    ) -> Any:
        """Create a new similarity computation record."""
        return await SimilarityRepository.create(
            task_name=task_name, computed_by=computed_by, binary_count=binary_count, status=status,
        )

    @staticmethod
    async def update_similarity_computation_status(
        computation_id: int,
        status: str,
        total_comparisons: int | None = None,
    ) -> None:
        """Update status (and optionally total_comparisons) of a computation."""
        await SimilarityRepository.update_status(
            computation_id=computation_id, status=status, total_comparisons=total_comparisons,
        )

    @staticmethod
    async def save_similarity_pairs(
        computation_id: int,
        pairs: list[Any],
    ) -> None:
        """Bulk-insert similarity pair results."""
        await SimilarityRepository.save_pairs(computation_id=computation_id, pairs=pairs)

    @staticmethod
    async def get_similarity_computation(computation_id: int) -> Any:
        """Retrieve a similarity computation with its pairs."""
        return await SimilarityRepository.get(computation_id=computation_id)

    @staticmethod
    async def list_similarity_computations(
        computed_by: int | None = None,
    ) -> list[Any]:
        """List similarity computations, optionally filtered by user."""
        return await SimilarityRepository.list_all(computed_by=computed_by)

    @staticmethod
    async def delete_similarity_computation(computation_id: int) -> None:
        """Delete a similarity computation and its pairs."""
        await SimilarityRepository.delete(computation_id=computation_id)
