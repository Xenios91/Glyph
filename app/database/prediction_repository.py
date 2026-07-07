"""Repository for Prediction entity database operations."""

from io import BytesIO
from typing import Any

import joblib
from loguru import logger
from sqlalchemy import delete, exists, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Prediction, get_utc_now
from app.database.session_handler import close_async_session, get_async_session
from app.services.request_handler import Prediction as PredictionResult
from app.utils.secure_deserializer import SecureDeserializationError, secure_load


class PredictionRepository:
    """Repository for Prediction entity CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def get_predictions_list() -> list[PredictionResult]:
        """Get the list of all predictions from the database.

        Returns:
            A list of PredictionResult objects.

        """
        prediction_results: list[PredictionResult] = []
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(select(Prediction))
            predictions = result.scalars().all()
            for pred in predictions:
                try:
                    raw_preds = secure_load(BytesIO(pred.functions_data))
                    if not isinstance(raw_preds, list):
                        logger.warning(
                            "Prediction data for '{}' is not a list, skipping",
                            pred.task_name,
                        )
                        continue
                    preds: list[dict[str, Any]] = _cast_list(raw_preds)
                    prediction_results.append(
                        PredictionResult(
                            task_name=pred.task_name,
                            model_name=pred.model_name,
                            pred=preds,
                        ),
                    )
                except SecureDeserializationError:
                    logger.exception("Secure deserialization blocked prediction '{}'", pred.task_name)
                except Exception:
                    logger.exception("Failed to deserialize prediction '{}'", pred.task_name)
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve predictions list")
        finally:
            await close_async_session(session)
        return prediction_results

    @staticmethod
    async def get(task_name: str, model_name: str) -> PredictionResult | None:
        """Retrieve and deserialize a Prediction object from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.

        Returns:
            PredictionResult object if found, otherwise None.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                select(Prediction).where(
                    Prediction.task_name == task_name,
                    Prediction.model_name == model_name,
                ),
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None

            try:
                raw_prediction_data = secure_load(BytesIO(row.functions_data))
                if not isinstance(raw_prediction_data, list):
                    logger.warning(
                        "Prediction data for task '{}' is not a list, expected list got {}",
                        task_name,
                        type(raw_prediction_data).__name__,
                    )
                    return None
                prediction_data: list[dict[str, Any]] = _cast_list(raw_prediction_data)
            except SecureDeserializationError:
                logger.exception("Secure deserialization blocked prediction for task '{}'", task_name)
                return None
            except Exception:
                logger.exception("Failed to deserialize prediction for task '{}'", task_name)
                return None

            return PredictionResult(task_name=task_name, model_name=model_name, pred=prediction_data)
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve predictions for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def save(name: str, model_name: str, functions: list[Any]) -> None:
        """Save or update predictions in the database.

        Uses SQLAlchemy 2.0's on_conflict_do_update() for efficient upserts
        in a single query on the composite key (task_name, model_name).

        Args:
            name: Name of the task.
            model_name: Name of the model used.
            functions: List of function predictions to save.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            functions_buffer = BytesIO()
            joblib.dump(functions, functions_buffer)
            functions_serialized = functions_buffer.getvalue()

            now = get_utc_now()
            ins = sqlite_insert(Prediction).values(
                task_name=name,
                model_name=model_name,
                functions_data=functions_serialized,
                created_at=now,
                modified_at=now,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[Prediction.task_name, Prediction.model_name],
                set_={
                    Prediction.functions_data: ins.excluded.functions_data,
                    Prediction.modified_at: ins.excluded.modified_at,
                },
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Prediction for task '{}' with model '{}' saved", name, model_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save predictions for task '{}'", name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_prediction_function(task_name: str, model_name: str, function_name: str) -> dict[str, Any]:
        """Get a specific function prediction from the database.

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            function_name: Name of the function to retrieve.

        Returns:
            Dictionary containing function prediction data, or empty dict if not found.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                select(Prediction).where(
                    Prediction.model_name == model_name,
                    Prediction.task_name == task_name,
                ),
            )
            row = result.scalar_one_or_none()
            if row is None:
                return {}

            try:
                raw_predictions = secure_load(BytesIO(row.functions_data))
                if not isinstance(raw_predictions, list):
                    logger.warning(
                        "Predictions data is not a list, expected list got {}",
                        type(raw_predictions).__name__,
                    )
                    return {}
                predictions: list[dict[str, Any]] = _cast_list(raw_predictions)
                for function in predictions:
                    if function.get("functionName") == function_name:
                        return function
            except SecureDeserializationError:
                logger.exception("Secure deserialization blocked predictions")
                return {}
            except Exception:
                logger.exception("Failed to deserialize predictions")
                return {}
        except sa_exc.SQLAlchemyError:
            logger.exception(
                "Failed to retrieve prediction function '{}' from task '{}'",
                function_name,
                task_name,
            )
        finally:
            await close_async_session(session)
        return {}

    @staticmethod
    async def delete(task_name: str, model_name: str | None = None) -> None:
        """Delete a prediction from the database.

        Uses bulk DELETE statement for better performance.

        Args:
            task_name: Name of the task to delete.
            model_name: Optional model name to narrow the delete scope.
                When provided, only predictions matching both task_name and
                model_name are deleted. When None, all predictions for the
                task_name are deleted (legacy behavior).

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            if model_name is not None:
                await session.execute(
                    delete(Prediction).where(
                        Prediction.task_name == task_name,
                        Prediction.model_name == model_name,
                    ),
                )
                logger.info("Prediction for task '{}' model '{}' deleted", task_name, model_name)
            else:
                await session.execute(delete(Prediction).where(Prediction.task_name == task_name))
                logger.info("Prediction for task '{}' deleted", task_name)
            await session.commit()
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete prediction for task '{}'", task_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_model_predictions(model_name: str) -> None:
        """Delete all predictions for a model from the database.

        Uses bulk DELETE statement for better performance.

        Args:
            model_name: Name of the model.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            await session.execute(delete(Prediction).where(Prediction.model_name == model_name))
            await session.commit()
            logger.info("Predictions for model '{}' deleted", model_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete predictions for model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def task_name_exists(task_name: str) -> bool:
        """Check if a task name already exists in the predictions database.

        Uses exists() subquery for better performance than func.count().

        Args:
            task_name: Name of the task to check.

        Returns:
            True if the task name exists, False otherwise.

        """
        session: AsyncSession | None = None
        try:
            session = await get_async_session("predictions")
            result = await session.execute(select(exists().where(Prediction.task_name == task_name)))
            return result.scalar_one() is True
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to check if task '{}' exists", task_name)
            return False
        finally:
            if session is not None:
                await close_async_session(session)


def _cast_list(data: Any) -> list[dict[str, Any]]:
    """Cast data to list[dict[str, Any]].

    Args:
        data: Data to cast.

    Returns:
        Casted data.

    """
    from typing import cast

    return cast(list[dict[str, Any]], data)
