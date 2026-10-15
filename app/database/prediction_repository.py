"""Repository for Prediction entity database operations."""

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.database.models import Prediction, get_utc_now
from app.database.session_handler import close_async_session, get_async_session
from app.services.request_handler import Prediction as PredictionResult
from app.utils.secure_deserializer import SecureDeserializationError, secure_dump, secure_load_bytes


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
                    raw_preds = await asyncio.to_thread(secure_load_bytes, pred.functions_data)
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
                            user_id=pred.user_id,
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
    async def count_for_user(user_id: int) -> int:
        """Count the predictions the given user may access.

        Mirrors the ownership rule used by ``can_access``: unowned rows
        (``user_id IS NULL``) are visible to everyone, while owned rows are
        visible only to their owner. The anonymous user (auth disabled,
        id 0) sees only unowned rows.

        This is a single ``COUNT(*)`` query and, unlike
        :meth:`get_predictions_list`, does not load or deserialize the
        ``functions_data`` BLOBs.

        Args:
            user_id: The current user's id (0 for anonymous).

        Returns:
            Number of predictions the user may access.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            if user_id == 0:
                where: ColumnElement[bool] = Prediction.user_id.is_(None)
            else:
                where = or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            result = await session.execute(select(func.count()).select_from(Prediction).where(where))
            return result.scalar_one()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to count predictions for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_task_names_for_user(user_id: int) -> list[str]:
        """Get distinct prediction task names the given user may access.

        Mirrors the ownership rule used by ``can_access``: unowned rows
        (``user_id IS NULL``) are visible to everyone, while owned rows are
        visible only to their owner. The anonymous user (auth disabled,
        id 0) sees only unowned rows.

        This is a single query selecting only ``task_name`` and, unlike
        :meth:`get_predictions_list`, does not load or deserialize the
        ``functions_data`` BLOBs.

        Args:
            user_id: The current user's id (0 for anonymous).

        Returns:
            A list of distinct task names the user may access.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            if user_id == 0:
                where: ColumnElement[bool] = Prediction.user_id.is_(None)
            else:
                where = or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            result = await session.execute(select(Prediction.task_name).where(where).distinct())
            return list(result.scalars().all())
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve prediction task names for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_predictions_metadata_for_user(
        user_id: int,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get lightweight prediction metadata (no BLOB deserialization).

        Selects only the plain columns ``task_name``, ``model_name``,
        ``function_count`` and ``user_id`` for the rows the given user may
        access. Mirrors the ownership rule used by ``can_access``: unowned
        rows (``user_id IS NULL``) are visible to everyone, owned rows only
        to their owner, and the anonymous user (auth disabled, id 0) sees
        only unowned rows.

        Unlike :meth:`get_predictions_list`, this never loads or
        deserializes the ``functions_data`` BLOBs, so it stays fast and
        memory-light even for predictions with large function sets.

        Args:
            user_id: The current user's id (0 for anonymous).
            offset: Number of rows to skip (pagination).
            limit: Maximum number of rows to return; ``None`` returns all.

        Returns:
            A list of dicts with keys ``task_name``, ``model_name``,
            ``function_count`` and ``user_id``, ordered by task name.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            where: ColumnElement[bool] = (
                Prediction.user_id.is_(None)
                if user_id == 0
                else or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            )
            stmt = (
                select(
                    Prediction.task_name,
                    Prediction.model_name,
                    Prediction.function_count,
                    Prediction.user_id,
                )
                .where(where)
                .order_by(Prediction.task_name)
            )
            stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [
                {
                    "task_name": row.task_name,
                    "model_name": row.model_name,
                    "function_count": row.function_count or 0,
                    "user_id": row.user_id,
                }
                for row in result.all()
            ]
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve prediction metadata for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get(task_name: str, model_name: str, user_id: int | None = None) -> PredictionResult | None:
        """Retrieve and deserialize a Prediction object from the database.

        Scoped to the caller when ``user_id`` is provided so a same-named row
        owned by another user is never returned (the per-user unique key allows
        two users to share a (task_name, model_name) pair). When ``user_id`` is
        None the lookup is unscoped (legacy behavior).

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            user_id: The caller's user id (0 for anonymous). When provided, only
                the caller's own row and unowned/legacy rows are considered.

        Returns:
            PredictionResult object if found, otherwise None.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            where: ColumnElement[bool] = (Prediction.task_name == task_name) & (Prediction.model_name == model_name)
            if user_id is not None:
                if user_id == 0:
                    where = where & Prediction.user_id.is_(None)
                else:
                    where = where & or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            result = await session.execute(select(Prediction).where(where))
            row = result.scalar_one_or_none()
            if row is None:
                return None

            try:
                raw_prediction_data = await asyncio.to_thread(secure_load_bytes, row.functions_data)
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

            return PredictionResult(
                task_name=task_name, model_name=model_name, pred=prediction_data, user_id=row.user_id
            )
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve predictions for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def save(name: str, model_name: str, functions: list[Any], user_id: int | None = None) -> None:
        """Save or update predictions in the database.

        Uses SQLAlchemy 2.0's on_conflict_do_update() for an efficient upsert in
        a single query on the per-user composite key (task_name, model_name,
        user_id). Two users may therefore share a (task_name, model_name) pair;
        only a repeat save by the *same* owner updates the existing row.

        Args:
            name: Name of the task.
            model_name: Name of the model used.
            functions: List of function predictions to save.
            user_id: Owner of the prediction (None for legacy/unowned).

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            # Serialize + compress off the event loop so the payload stays
            # under SQLite's 2 GiB BLOB limit for large function sets.
            functions_serialized = await asyncio.to_thread(secure_dump, functions)

            now = get_utc_now()
            ins = sqlite_insert(Prediction).values(
                task_name=name,
                model_name=model_name,
                functions_data=functions_serialized,
                function_count=len(functions),
                user_id=user_id,
                created_at=now,
                modified_at=now,
            )
            # The conflict target must match the per-user unique constraint.
            # (A NULL user_id is distinct in the unique index, so a legacy
            # unowned save simply inserts a new row rather than updating.)
            stmt = ins.on_conflict_do_update(
                index_elements=[Prediction.task_name, Prediction.model_name, Prediction.user_id],
                set_={
                    Prediction.functions_data: ins.excluded.functions_data,
                    Prediction.function_count: ins.excluded.function_count,
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
    async def get_prediction_function(
        task_name: str,
        model_name: str,
        function_name: str,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Get a specific function prediction from the database.

        Scoped to the caller when ``user_id`` is provided so a same-named row
        owned by another user is never returned (the per-user unique key allows
        two users to share a (task_name, model_name) pair). When ``user_id`` is
        None the lookup is unscoped (legacy behavior).

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            function_name: Name of the function to retrieve.
            user_id: The caller's user id (0 for anonymous). When provided, only
                the caller's own row and unowned/legacy rows are considered.

        Returns:
            Dictionary containing function prediction data, or empty dict if not found.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            where: ColumnElement[bool] = (Prediction.model_name == model_name) & (Prediction.task_name == task_name)
            if user_id is not None:
                if user_id == 0:
                    where = where & Prediction.user_id.is_(None)
                else:
                    where = where & or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            result = await session.execute(select(Prediction).where(where))
            row = result.scalar_one_or_none()
            if row is None:
                return {}

            try:
                raw_predictions = await asyncio.to_thread(secure_load_bytes, row.functions_data)
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
    async def delete(
        task_name: str,
        model_name: str | None = None,
        user_id: int | None = None,
    ) -> None:
        """Delete a prediction from the database.

        Uses bulk DELETE statement for better performance.

        Args:
            task_name: Name of the task to delete.
            model_name: Optional model name to narrow the delete scope.
                When provided, only predictions matching both task_name and
                model_name are deleted. When None, all predictions for the
                task_name are deleted (legacy behavior).
            user_id: When provided, the DELETE is additionally scoped to rows
                owned by this user, so a logic error cannot delete another
                user's same-named row. When None, no user scoping is applied
                (used for admin/legacy cleanup paths).

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            if model_name is not None:
                stmt = delete(Prediction).where(
                    Prediction.task_name == task_name,
                    Prediction.model_name == model_name,
                )
            else:
                stmt = delete(Prediction).where(Prediction.task_name == task_name)
            if user_id is not None:
                stmt = stmt.where(Prediction.user_id == user_id)
            await session.execute(stmt)
            if model_name is not None:
                logger.info("Prediction for task '{}' model '{}' deleted", task_name, model_name)
            else:
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
    async def get_owner_by_task(task_name: str, user_id: int) -> int | None:
        """Return the owner of *the caller's* prediction with this task name.

        Scoped to ``user_id``: returns the caller's own ``user_id`` when they
        own a prediction with this name, or ``None`` when they do not (the
        name may still exist for another user, but that is not the caller's
        row). This is the per-user replacement for the old global lookup.

        Args:
            task_name: Name of the task.
            user_id: The caller's user id.

        Returns:
            The caller's user_id if they own a prediction with this name,
            otherwise None.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                select(Prediction.user_id).where(
                    Prediction.task_name == task_name,
                    Prediction.user_id == user_id,
                ),
            )
            return result.scalars().first()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve owner of prediction for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_for_user(task_name: str, user_id: int) -> Prediction | None:
        """Return the caller's prediction with this task name, or None.

        Scoped to ``user_id`` so a same-named row owned by another user is
        never returned. Used by the ``/scan`` taskName branch to locate the
        caller's own row before asserting ownership.

        Args:
            task_name: Name of the task.
            user_id: The caller's user id.

        Returns:
            The matching Prediction row, or None if the caller owns no such
            task.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            result = await session.execute(
                select(Prediction).where(
                    Prediction.task_name == task_name,
                    Prediction.user_id == user_id,
                ),
            )
            return result.scalars().first()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve prediction for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_owner(task_name: str, model_name: str, user_id: int | None = None) -> int | None:
        """Return the owner (user_id) of a prediction without deserializing it.

        Scoped to the caller when ``user_id`` is provided so a same-named row
        owned by another user is never reported (the per-user unique key allows
        two users to share a (task_name, model_name) pair). When ``user_id`` is
        None the lookup is unscoped (legacy behavior).

        Args:
            task_name: Name of the task.
            model_name: Name of the model.
            user_id: The caller's user id (0 for anonymous). When provided, only
                the caller's own row and unowned/legacy rows are considered.

        Returns:
            The owning user_id, or None if the prediction does not exist
            or is unowned/legacy.

        """
        session: AsyncSession = await get_async_session("predictions")
        try:
            where: ColumnElement[bool] = (Prediction.task_name == task_name) & (Prediction.model_name == model_name)
            if user_id is not None:
                if user_id == 0:
                    where = where & Prediction.user_id.is_(None)
                else:
                    where = where & or_(Prediction.user_id == user_id, Prediction.user_id.is_(None))
            result = await session.execute(select(Prediction.user_id).where(where))
            return result.scalar_one_or_none()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve owner of prediction for task '{}'", task_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def task_name_exists(task_name: str, user_id: int) -> bool:
        """Check if a task name already exists *for the given user*.

        Scoped to ``user_id``: a name owned by another user does not count.
        Uses exists() subquery for better performance than func.count().

        Args:
            task_name: Name of the task to check.
            user_id: The caller's user id.

        Returns:
            True if the user already owns a prediction with this name,
            False otherwise.

        """
        session: AsyncSession | None = None
        try:
            session = await get_async_session("predictions")
            result = await session.execute(
                select(
                    exists().where(
                        Prediction.task_name == task_name,
                        Prediction.user_id == user_id,
                    )
                )
            )
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
