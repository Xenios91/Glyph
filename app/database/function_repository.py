"""Repository for Function entity database operations."""

from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Function, get_utc_now
from app.database.session_handler import close_async_session, get_async_session


class FunctionRepository:
    """Repository for Function entity CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def save(model_name: str, functions: list[dict[str, Any]]) -> None:
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
                },
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
            result = await session.execute(select(Function).where(Function.model_name == model_name))
            functions = list(result.scalars().all())
            session.expunge_all()
            return functions
        except Exception:
            logger.exception("Failed to retrieve functions for model '{}'", model_name)
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def get(model_name: str, function_name: str) -> Function | None:
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
    async def delete(model_name: str) -> None:
        """Delete all functions for a model from the database.

        Uses bulk DELETE statement for better performance instead of
        loading rows individually.

        Args:
            model_name: Name of the model.
        """
        session: AsyncSession = await get_async_session("functions")
        try:
            await session.execute(delete(Function).where(Function.model_name == model_name))
            await session.commit()
            logger.info("Functions for model '{}' deleted", model_name)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete functions for model '{}'", model_name)
            raise
        finally:
            await close_async_session(session)
