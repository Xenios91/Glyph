"""SQL utility module for database operations using SQLAlchemy ORM."""

from io import BytesIO
from typing import Any

import joblib
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Model, Prediction, Function
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
        """Save a model to the models database.

        Args:
            model_name: Name of the model to save.
            label_encoder: Serialized label encoder bytes.
            model: Serialized model bytes.
        """
        session: AsyncSession = await get_async_session("models")
        try:
            db_model = Model(
                model_name=model_name,
                model_data=model,
                label_encoder_data=label_encoder,
            )
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
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

        Returns:
            A set of model names.
        """
        models_set: set[str] = set()
        session: AsyncSession = await get_async_session("models")
        try:
            result = await session.execute(select(Model.model_name))
            models_set = {row[0] for row in result.all()}
        except Exception:
            logger.exception("Failed to retrieve models list")
        finally:
            await close_async_session(session)
        return models_set

    @staticmethod
    async def get_model(model_name: str) -> Model | None:
        """Retrieve a model from the database.

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
            return model
        except Exception:
            logger.exception("Failed to retrieve model '{}'", model_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_model(model_name: str) -> None:
        """Delete a model and its associated functions from the database.

        Args:
            model_name: Name of the model to delete.
        """
        # Delete associated functions first
        await SQLUtil.delete_functions(model_name)

        session: AsyncSession = await get_async_session("models")
        try:
            result = await session.execute(
                select(Model).where(Model.model_name == model_name)
            )
            model = result.scalar_one_or_none()
            if model:
                await session.delete(model)
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
                    preds = secure_load(BytesIO(pred.functions_data))
                    if not isinstance(preds, list):
                        logger.warning(
                            "Prediction data for '{}' is not a list, skipping",
                            pred.task_name,
                        )
                        continue
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
                prediction_data = secure_load(BytesIO(row.functions_data))
                if not isinstance(prediction_data, list):
                    logger.warning(
                        "Prediction data for task '{}' is not a list, expected list got {}",
                        task_name,
                        type(prediction_data).__name__,
                    )
                    return None
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
    async def save_predictions(name: str, model_name: str, functions: list) -> None:
        """Save predictions to the database.

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

            pred = Prediction(
                task_name=name,
                model_name=model_name,
                functions_data=functions_serialized,
            )
            session.add(pred)
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
    ) -> dict:
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
                predictions = secure_load(BytesIO(row.functions_data))
                if not isinstance(predictions, list):
                    logger.warning(
                        "Predictions data is not a list, expected list got {}",
                        type(predictions).__name__,
                    )
                    return {}
                for function in predictions:
                    if (
                        isinstance(function, dict)
                        and function.get("functionName") == function_name
                    ):
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
    async def save_functions(model_name: str, functions: list) -> None:
        """Save functions to the functions database.

        Args:
            model_name: Name of the model.
            functions: List of functions to save.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            for function in functions:
                tokens = " ".join(function["tokenList"])
                db_func = Function(
                    model_name=model_name,
                    function_name=function["functionName"],
                    entrypoint=function["lowAddress"],
                    tokens=tokens,
                )
                session.add(db_func)
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
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to retrieve functions for model '{}'", model_name)
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_function(model_name: str, function_name: str) -> Function | None:
        """Get a specific function from the database.

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
            return result.scalars().first()
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
            result = await session.execute(
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
    async def delete_prediction(task_name: str) -> None:
        """Delete a prediction from the database.

        Uses bulk DELETE statement for better performance.

        Args:
            task_name: Name of the task to delete.
        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                delete(Prediction).where(Prediction.task_name == task_name)
            )
            await session.commit()
            logger.info("Prediction for task '{}' deleted", task_name)
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
            return result.scalar() is True
        except Exception:
            logger.exception("Failed to check if task '{}' exists", task_name)
            return False
        finally:
            await close_async_session(session)
