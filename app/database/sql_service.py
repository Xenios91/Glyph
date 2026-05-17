"""SQL utility module for database operations using SQLAlchemy ORM."""

from io import BytesIO
from typing import Any, cast

import joblib  # type: ignore[import-no-untyped]
from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Model, Prediction, Function, get_utc_now
from app.database.session_handler import get_async_session, close_async_session
from app.services.request_handler import Prediction as PredictionResult
from loguru import logger
from app.utils.secure_deserializer import secure_load, SecureDeserializationError


class SQLUtil:
    """Utility class for SQLite database operations using SQLAlchemy ORM.

    All methods are async and use the appropriate database session
    based on the entity type (models, predictions, or functions).
    """

    # Database name mapping for each entity type
    _DB_MAP = {
        "models": "models",
        "predictions": "predictions",
        "functions": "functions",
    }

    @staticmethod
    async def init_db() -> None:
        """Initialize the database tables.

        This is now a no-op since tables are created by init_async_databases()
        in session_handler.py which uses Base.metadata.create_all.
        Kept for API compatibility with existing callers.
        """
        # Tables are created by init_async_databases() in session_handler.py
        logger.debug("Database tables managed by async session handler")

    @staticmethod
    async def save_model(model_name: str, label_encoder: bytes, model: bytes) -> None:
        """Save or update a model in the models database.

        Uses SQLAlchemy 2.0's on_conflict_do_update() for efficient upserts
        in a single query, avoiding the need for a separate existence check.

        Args:
            model_name: Name of the model to save.
            label_encoder: Serialized label encoder bytes.
            model: Serialized model bytes.
        """
        session: AsyncSession = await get_async_session("models")
        try:
            now = get_utc_now()
            ins = sqlite_insert(Model).values(
                model_name=model_name,
                model_data=model,
                label_encoder_data=label_encoder,
                created_at=now,
                modified_at=now,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[Model.model_name],
                set_={
                    Model.model_data: ins.excluded.model_data,
                    Model.label_encoder_data: ins.excluded.label_encoder_data,
                    Model.modified_at: ins.excluded.modified_at,
                }
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Model '{}' saved", model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to save model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_models_list() -> set[str]:
        """Get the list of model names from the database.

        Uses scalars() for efficient single-column result extraction
        instead of row indexing.

        Returns:
            A set of model names.
        """
        models_set: set[str] = set()
        session: AsyncSession = await get_async_session("models")
        try:
            result = await session.execute(select(Model.model_name))
            models_set = set(result.scalars().all())
        except Exception:
            logger.exception("Failed to retrieve models list")
        finally:
            await close_async_session(session)
        return models_set

    @staticmethod
    async def get_model(model_name: str) -> Model | None:
        """Retrieve a model from the database.

        Uses session.expunge() to explicitly detach the ORM object before
        closing the session, preserving loaded attribute values for the
        caller to access without triggering DetachedInstanceError.

        Args:
            model_name: Name of the model to retrieve.

        Returns:
            The Model ORM object if found, otherwise None.
        """
        session: AsyncSession = await get_async_session("models")
        try:
            result = await session.execute(
                select(Model).where(Model.model_name == model_name)
            )
            model = result.scalar_one_or_none()
            if model is None:
                logger.warning("Model '{}' not found", model_name)
            else:
                # Expunge the object to detach it from the session while
                # preserving its loaded attribute values. This allows the
                # caller to access scalar attributes without the session
                # being open, avoiding DetachedInstanceError with AsyncAttrs.
                session.expunge(model)
            return model
        except Exception:
            logger.exception("Failed to retrieve model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_model(model_name: str) -> None:
        """Delete a model and all associated data from the database.

        Deletes associated predictions, functions, and the model itself
        using bulk DELETE statements for better performance and to avoid
        loading rows into the identity map unnecessarily.

        Args:
            model_name: Name of the model to delete.
        """
        # Delete associated predictions first using bulk delete
        await SQLUtil.delete_model_predictions(model_name)

        # Delete associated functions using bulk delete
        await SQLUtil.delete_functions(model_name)

        session: AsyncSession = await get_async_session("models")
        try:
            await session.execute(
                delete(Model).where(Model.model_name == model_name)
            )
            await session.commit()
            logger.info("Model '{}' deleted", model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

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
                    preds: list[dict[str, Any]] = cast(list[dict[str, Any]], raw_preds)
                    prediction_results.append(
                        PredictionResult(
                            task_name=pred.task_name,
                            model_name=pred.model_name,
                            pred=preds,
                        )
                    )
                except SecureDeserializationError:
                    logger.exception(
                        "Secure deserialization blocked prediction '{}'", pred.task_name
                    )
                except Exception:
                    logger.exception(
                        "Failed to deserialize prediction '{}'", pred.task_name
                    )
        except Exception:
            logger.exception("Failed to retrieve predictions list")
        finally:
            await close_async_session(session)
        return prediction_results

    @staticmethod
    async def get_predictions(task_name: str, model_name: str) -> PredictionResult | None:
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
                )
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
                prediction_data: list[dict[str, Any]] = cast(
                    list[dict[str, Any]], raw_prediction_data
                )
            except SecureDeserializationError:
                logger.exception(
                    "Secure deserialization blocked prediction for task '{}'", task_name
                )
                return None
            except Exception:
                logger.exception(
                    "Failed to deserialize prediction for task '{}'", task_name
                )
                return None

            return PredictionResult(
                task_name=task_name, model_name=model_name, pred=prediction_data
            )
        except Exception:
            logger.exception("Failed to retrieve predictions for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def save_predictions(name: str, model_name: str, functions: list[Any]) -> None:
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
            joblib.dump(functions, functions_buffer)  # type: ignore[call-overload]
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
                }
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Prediction for task '{}' with model '{}' saved", name, model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to save predictions for task '{}'", name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_prediction_function(
        task_name: str, model_name: str, function_name: str
    ) -> dict[str, Any]:
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
                )
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
                predictions: list[dict[str, Any]] = cast(
                    list[dict[str, Any]], raw_predictions
                )
                for function in predictions:
                    if function.get("functionName") == function_name:
                        return function
            except SecureDeserializationError:
                logger.exception("Secure deserialization blocked predictions")
                return {}
            except Exception:
                logger.exception("Failed to deserialize predictions")
                return {}
        except Exception:
            logger.exception(
                "Failed to retrieve prediction function '{}' from task '{}'",
                function_name,
                task_name,
            )
        finally:
            await close_async_session(session)
        return {}

    @staticmethod
    async def save_functions(model_name: str, functions: list[dict[str, Any]]) -> None:
        """Save or update functions in the functions database.

        Uses SQLAlchemy 2.0's on_conflict_do_update() for efficient upserts
        on the composite key (model_name, function_name), avoiding duplicate
        rows when the same model is trained multiple times.

        Args:
            model_name: Name of the model.
            functions: List of functions to save.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            now = get_utc_now()
            func_mappings = [
                {
                    "model_name": model_name,
                    "function_name": function["functionName"],
                    "entrypoint": function["lowAddress"],
                    "tokens": " ".join(function["tokenList"]),
                    "created_at": now,
                    "modified_at": now,
                }
                for function in functions
            ]
            ins = sqlite_insert(Function).values(func_mappings)
            stmt = ins.on_conflict_do_update(
                index_elements=[Function.model_name, Function.function_name],
                set_={
                    Function.entrypoint: ins.excluded.entrypoint,
                    Function.tokens: ins.excluded.tokens,
                    Function.modified_at: ins.excluded.modified_at,
                }
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Saved {} functions to model '{}'", len(functions), model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to save functions for model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_functions(model_name: str) -> list[Function]:
        """Get all functions for a model from the database.

        Uses session.expunge_all() to explicitly detach all loaded ORM
        objects before closing the session, preserving their loaded
        attribute values for the caller to access.

        Args:
            model_name: Name of the model.

        Returns:
            List of Function ORM objects.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            result = await session.execute(
                select(Function).where(Function.model_name == model_name)
            )
            functions = list(result.scalars().all())
            # Expunge all loaded objects to detach them from the session
            # while preserving their loaded attribute values.
            session.expunge_all()
            return functions
        except Exception:
            logger.exception("Failed to retrieve functions for model '{}'", model_name)
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_function(model_name: str, function_name: str) -> Function | None:
        """Get a specific function from the database.

        Uses session.expunge() to explicitly detach the ORM object before
        closing the session, preserving loaded attribute values.

        Args:
            model_name: Name of the model.
            function_name: Name of the function.

        Returns:
            Function ORM object or None.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            result = await session.execute(
                select(Function).where(
                    Function.model_name == model_name,
                    Function.function_name == function_name,
                )
            )
            function = result.scalar_one_or_none()
            if function is not None:
                # Expunge to detach from session while preserving attributes.
                session.expunge(function)
            return function
        except Exception:
            logger.exception(
                "Failed to retrieve function '{}' from model '{}'",
                function_name,
                model_name,
            )
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_functions(model_name: str) -> None:
        """Delete all functions for a model from the database.

        Uses bulk DELETE statement for better performance instead of
        loading rows individually.

        Args:
            model_name: Name of the model.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            await session.execute(
                delete(Function).where(Function.model_name == model_name)
            )
            await session.commit()
            logger.info(
                "Functions for model '{}' deleted", model_name
            )
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete functions for model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_prediction(task_name: str, model_name: str | None = None) -> None:
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
                    )
                )
                logger.info("Prediction for task '{}' model '{}' deleted", task_name, model_name)
            else:
                await session.execute(
                    delete(Prediction).where(Prediction.task_name == task_name)
                )
                logger.info("Prediction for task '{}' deleted", task_name)
            await session.commit()
        except Exception:
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
            await session.execute(
                delete(Prediction).where(Prediction.model_name == model_name)
            )
            await session.commit()
            logger.info("Predictions for model '{}' deleted", model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete predictions for model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def model_name_exists(model_name: str) -> bool:
        """Check if a model name already exists in the models database.

        Uses exists() subquery for better performance than fetching all model names.

        Args:
            model_name: Name of the model to check.

        Returns:
            True if the model name exists, False otherwise.
        """
        session: AsyncSession = await get_async_session("models")
        try:
            result = await session.execute(
                select(exists().where(Model.model_name == model_name))
            )
            return result.scalar_one() is True
        except Exception:
            logger.exception("Failed to check if model '{}' exists", model_name)
            return False
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
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                select(exists().where(Prediction.task_name == task_name))
            )
            return result.scalar_one() is True
        except Exception:
            logger.exception("Failed to check if task '{}' exists", task_name)
            return False
        finally:
            await close_async_session(session)
