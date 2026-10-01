"""Repository for per-user LLM endpoint configuration."""

from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import LLMConfig, get_settings
from app.database.models import LLMUserConfig
from app.database.session_handler import close_async_session, get_async_session

#: Fields shared between the LLMUserConfig row and the LLMConfig model.
_LLM_FIELDS: tuple[str, ...] = tuple(LLMConfig.model_fields.keys())


class LLMUserConfigRepository:
    """Repository for per-user LLM configuration CRUD operations.

    All methods manage their own database sessions via
    get_async_session/close_async_session.
    """

    @staticmethod
    async def get_for_user(user_id: int) -> LLMUserConfig | None:
        """Retrieve the stored LLM configuration for a user.

        Args:
            user_id: The user's primary key.

        Returns:
            The LLMUserConfig row if one exists, None otherwise.

        """
        session: AsyncSession = await get_async_session("auth")
        try:
            row = (
                await session.execute(select(LLMUserConfig).where(LLMUserConfig.user_id == user_id))
            ).scalar_one_or_none()
            if row is not None:
                session.expunge(row)
            return row
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve LLM configuration for user {}", user_id)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def upsert(user_id: int, updates: dict[str, Any]) -> LLMUserConfig:
        """Create or update the LLM configuration row for a user.

        A missing row is created by starting from the global defaults in
        config.yml and applying the provided updates on top. An existing row
        has only the provided fields overwritten.

        Args:
            user_id: The user's primary key.
            updates: Dict of field name to normalized value (validated upstream).

        Returns:
            The persisted LLMUserConfig row (detached from the session).

        Raises:
            sa_exc.SQLAlchemyError: When the write fails (rolled back).

        """
        session: AsyncSession = await get_async_session("auth")
        try:
            row = (
                await session.execute(select(LLMUserConfig).where(LLMUserConfig.user_id == user_id))
            ).scalar_one_or_none()
            if row is None:
                defaults = get_settings().llm
                row = LLMUserConfig(
                    user_id=user_id,
                    **{name: getattr(defaults, name) for name in _LLM_FIELDS},
                )
                session.add(row)
            for name, value in updates.items():
                setattr(row, name, value)
            await session.commit()
            session.expunge(row)
            logger.info("Saved LLM configuration for user {}", user_id)
            return row
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save LLM configuration for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_for_user(user_id: int) -> bool:
        """Delete the stored LLM configuration for a user.

        Args:
            user_id: The user's primary key.

        Returns:
            True when a row was deleted, False when nothing was stored.

        """
        from sqlalchemy import delete

        session: AsyncSession = await get_async_session("auth")
        try:
            result = await session.execute(
                delete(LLMUserConfig).where(LLMUserConfig.user_id == user_id),
            )
            await session.commit()
            deleted = (result.rowcount or 0) > 0
            if deleted:
                logger.info("Deleted LLM configuration for user {}", user_id)
            return deleted
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete LLM configuration for user {}", user_id)
            raise
        finally:
            await close_async_session(session)


async def resolve_user_llm_config(user_id: int) -> LLMConfig:
    """Resolve the effective LLM configuration for a user.

    The user's stored row (if any) takes precedence over the global defaults
    from config.yml, field by field. When the user has no stored row, the
    global configuration is returned unchanged.

    Args:
        user_id: The user's primary key.

    Returns:
        An LLMConfig instance with the user's effective values.

    """
    row = await LLMUserConfigRepository.get_for_user(user_id)
    if row is None:
        return get_settings().llm
    return LLMConfig(**{name: getattr(row, name) for name in _LLM_FIELDS})
