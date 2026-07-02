"""Repository for Model entity database operations."""

from loguru import logger
from sqlalchemy import delete, exc as sa_exc, exists, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Model, get_utc_now
from app.database.session_handler import close_async_session, get_async_session


class ModelRepository:
    """Repository for Model entity CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def save(model_name: str, label_encoder: bytes, model: bytes) -> None:
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
                },
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Model '{}' saved", model_name)
        except sa_exc.SQLAlchemyError:
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
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve models list")
        finally:
            await close_async_session(session)
        return models_set

    @staticmethod
    async def get(model_name: str) -> Model | None:
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
            result = await session.execute(select(Model).where(Model.model_name == model_name))
            model = result.scalar_one_or_none()
            if model is None:
                logger.warning("Model '{}' not found", model_name)
            else:
                session.expunge(model)
            return model
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def exists(model_name: str) -> bool:
        """Check if a model name already exists in the models database.

        Uses exists() subquery for better performance than fetching all model names.

        Args:
            model_name: Name of the model to check.

        Returns:
            True if the model name exists, False otherwise.
        """
        session: AsyncSession | None = None
        try:
            session = await get_async_session("models")
            result = await session.execute(select(exists().where(Model.model_name == model_name)))
            return result.scalar_one() is True
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to check if model '{}' exists", model_name)
            return False
        finally:
            if session is not None:
                await close_async_session(session)

    @staticmethod
    async def delete(model_name: str) -> None:
        """Delete a model from the database.

        Args:
            model_name: Name of the model to delete.
        """
        session: AsyncSession = await get_async_session("models")
        try:
            await session.execute(delete(Model).where(Model.model_name == model_name))
            await session.commit()
            logger.info("Model '{}' deleted", model_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)
