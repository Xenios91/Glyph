"""SQL utility module for database operations using SQLAlchemy ORM."""

from io import BytesIO
from typing import Any, cast

import joblib  # type: ignore[import-no-untyped]
from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Binary, BinaryFunction, Model, Prediction, Function, get_utc_now,
    SimilarityComputation, SimilarityPair,
)
from app.database.session_handler import get_async_session, close_async_session
from app.services.request_handler import Prediction as PredictionResult
from loguru import logger
from app.utils.secure_deserializer import secure_load, SecureDeserializationError


class SQLUtil:
    """Utility class for SQLite database operations using SQLAlchemy ORM.

    All methods are async and use the appropriate database session
    based on the entity type (models, predictions, or functions).
    """

    _DB_MAP = {
        "models": "models",
        "predictions": "predictions",
        "functions": "functions",
        "binaries": "binaries",
    }

    @staticmethod
    async def init_db() -> None:
        """Initialize the database tables.

        This is now a no-op since tables are created by init_async_databases()
        in session_handler.py which uses Base.metadata.create_all.
        Kept for API compatibility with existing callers.
        """
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
        await SQLUtil.delete_model_predictions(model_name)
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

    # ------------------------------------------------------------------
    # Similarity computation helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def create_similarity_computation(
        task_name: str,
        computed_by: int,
        binary_count: int,
        status: str = "pending",
    ) -> SimilarityComputation:
        """Create a new similarity computation record.

        Args:
            task_name: Human-readable name for this computation.
            computed_by: User ID who initiated it.
            binary_count: Number of binaries being compared.
            status: Initial status.

        Returns:
            The created SimilarityComputation instance.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            comp = SimilarityComputation(
                task_name=task_name,
                computed_by=computed_by,
                binary_count=binary_count,
                total_comparisons=0,
                status=status,
            )
            session.add(comp)
            await session.commit()
            await session.refresh(comp)
            logger.info("Similarity computation '{}' created (id={})", task_name, comp.id)
            return comp
        except Exception:
            await session.rollback()
            logger.exception("Failed to create similarity computation '%s'", task_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def update_similarity_computation_status(
        computation_id: int,
        status: str,
        total_comparisons: int | None = None,
    ) -> None:
        """Update status (and optionally total_comparisons) of a computation.

        Args:
            computation_id: Database id.
            status: New status string.
            total_comparisons: Optional override for total comparisons count.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            comp = await session.get(SimilarityComputation, computation_id)
            if comp is None:
                logger.warning("Similarity computation {} not found", computation_id)
                return
            comp.status = status
            if total_comparisons is not None:
                comp.total_comparisons = total_comparisons
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to update computation {}", computation_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def save_similarity_pairs(
        computation_id: int,
        pairs: list[SimilarityPair],
    ) -> None:
        """Bulk-insert similarity pair results.

        Args:
            computation_id: Parent computation id.
            pairs: List of SimilarityPair ORM instances to save.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            for pair in pairs:
                pair.computation_id = computation_id
                session.add(pair)
            await session.commit()
            logger.info(
                "Saved {} similarity pairs for computation {}",
                len(pairs),
                computation_id,
            )
        except Exception:
            await session.rollback()
            logger.exception("Failed to save similarity pairs for computation {}", computation_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_similarity_computation(
        computation_id: int,
    ) -> SimilarityComputation | None:
        """Retrieve a similarity computation with its pairs.

        Args:
            computation_id: Database id.

        Returns:
            SimilarityComputation instance with loaded pairs, or None.
        """
        from sqlalchemy.orm import selectinload

        session: AsyncSession = await get_async_session("intelligence")
        try:
            result = await session.execute(
                select(SimilarityComputation)
                .options(selectinload(SimilarityComputation.pairs))
                .where(SimilarityComputation.id == computation_id)
            )
            comp = result.scalar_one_or_none()
            if comp is not None:
                session.expunge_all()
            return comp
        except Exception:
            logger.exception("Failed to retrieve computation {}", computation_id)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def list_similarity_computations(
        computed_by: int | None = None,
    ) -> list[SimilarityComputation]:
        """List similarity computations, optionally filtered by user.

        Args:
            computed_by: Optional user ID filter.

        Returns:
            List of SimilarityComputation instances.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            stmt = select(SimilarityComputation)
            if computed_by is not None:
                stmt = stmt.where(SimilarityComputation.computed_by == computed_by)
            stmt = stmt.order_by(SimilarityComputation.created_at.desc())
            result = await session.execute(stmt)
            comps = list(result.scalars().all())
            session.expunge_all()
            return comps
        except Exception:
            logger.exception("Failed to list similarity computations")
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_similarity_computation(computation_id: int) -> None:
        """Delete a similarity computation and its pairs.

        Args:
            computation_id: Database id.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            await session.execute(
                delete(SimilarityPair).where(
                    SimilarityPair.computation_id == computation_id
                )
            )
            await session.execute(
                delete(SimilarityComputation).where(
                    SimilarityComputation.id == computation_id
                )
            )
            await session.commit()
            logger.info("Similarity computation {} deleted", computation_id)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete computation {}", computation_id)
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
        """Save binary metadata and return the new binary id.

        Args:
            name: Human-readable name for the binary.
            file_path: Path to the binary file on disk.
            file_size: Size of the binary in bytes.
            mime_type: Detected MIME type.
            uploaded_by: User id of the uploader.

        Returns:
            The auto-generated binary id.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            now = get_utc_now()
            binary = Binary(
                name=name,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                uploaded_by=uploaded_by,
                created_at=now,
                modified_at=now,
            )
            session.add(binary)
            await session.flush()
            await session.commit()
            binary_id = binary.id
            logger.info("Binary '{}' saved with id {}", name, binary_id)
            return binary_id
        except Exception:
            await session.rollback()
            logger.exception("Failed to save binary '{}'", name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_binary(binary_id: int) -> Binary | None:
        """Retrieve a binary by its id.

        Args:
            binary_id: The binary primary key.

        Returns:
            The Binary ORM object or None.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(Binary).where(Binary.id == binary_id))
            binary = result.scalar_one_or_none()
            if binary is not None:
                session.expunge(binary)
            return binary
        except Exception:
            logger.exception("Failed to retrieve binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_binaries_by_user(user_id: int) -> list[Binary]:
        """List all binaries uploaded by a specific user.

        Args:
            user_id: The user primary key.

        Returns:
            List of Binary ORM objects (expunged from session).
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(
                select(Binary)
                .where(Binary.uploaded_by == user_id)
                .order_by(Binary.created_at.desc())
            )
            binaries = result.scalars().all()
            for b in binaries:
                session.expunge(b)
            return list(binaries)
        except Exception:
            logger.exception("Failed to list binaries for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_binary(binary_id: int) -> None:
        """Delete a binary and all its associated functions.

        CASCADE on the foreign key in BinaryFunction handles child rows.

        Args:
            binary_id: The binary primary key.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            await session.execute(delete(Binary).where(Binary.id == binary_id))
            await session.commit()
            logger.info("Binary {} deleted", binary_id)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def save_binary_functions(binary_id: int, functions: list[dict[str, Any]]) -> None:
        """Save raw decompiled functions for a binary.

        Uses upsert on (binary_id, function_name) so re-running is safe.

        Args:
            binary_id: Parent binary primary key.
            functions: List of dicts with keys ``function_name``, ``entrypoint``,
                       and ``raw_code``.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            now = get_utc_now()
            for func_data in functions:
                ins = sqlite_insert(BinaryFunction).values(
                    binary_id=binary_id,
                    function_name=func_data["function_name"],
                    entrypoint=func_data["entrypoint"],
                    raw_code=func_data["raw_code"],
                    created_at=now,
                    modified_at=now,
                )
                stmt = ins.on_conflict_do_update(
                    index_elements=["binary_id", "function_name"],
                    set_={
                        BinaryFunction.raw_code: ins.excluded.raw_code,
                        BinaryFunction.entrypoint: ins.excluded.entrypoint,
                        BinaryFunction.modified_at: ins.excluded.modified_at,
                    },
                )
                await session.execute(stmt)
            await session.commit()
            logger.info("Functions saved for binary {}", binary_id)
        except Exception:
            await session.rollback()
            logger.exception("Failed to save functions for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_binary_functions(binary_id: int) -> list[BinaryFunction]:
        """Load all raw functions for a binary.

        Args:
            binary_id: Parent binary primary key.

        Returns:
            List of BinaryFunction ORM objects (expunged).
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(
                select(BinaryFunction)
                .where(BinaryFunction.binary_id == binary_id)
                .order_by(BinaryFunction.function_name)
            )
            functions = result.scalars().all()
            for f in functions:
                session.expunge(f)
            return list(functions)
        except Exception:
            logger.exception("Failed to load functions for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_all_binary_ids() -> list[int]:
        """Return every binary id in the database.

        Returns:
            List of binary id integers.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(Binary.id))
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to list binary ids")
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_binary_name(binary_id: int) -> str | None:
        """Return the human-readable name for a binary.

        Args:
            binary_id: The binary primary key.

        Returns:
            Binary name or None if not found.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(
                select(Binary.name).where(Binary.id == binary_id)
            )
            return result.scalars().first()
        except Exception:
            logger.exception("Failed to get name for binary {}", binary_id)
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
            return result.scalar_one() is True
        except Exception:
            logger.exception("Failed to check if task '{}' exists", task_name)
            return False
        finally:
            await close_async_session(session)
