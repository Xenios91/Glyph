"""Repository for Binary and BinaryFunction entity database operations."""

from typing import Any

from loguru import logger
from sqlalchemy import delete, exc as sa_exc, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Binary, BinaryFunction, get_utc_now
from app.database.session_handler import close_async_session, get_async_session


class BinaryRepository:
    """Repository for Binary and BinaryFunction entity CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

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
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save binary '{}'", name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get(binary_id: int) -> Binary | None:
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
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def count_by_user(user_id: int) -> int:
        """Count the number of binaries uploaded by a specific user.

        Args:
            user_id: The user primary key.

        Returns:
            Total count of binaries for the user.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(func.count()).where(Binary.uploaded_by == user_id))
            return result.scalar_one()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to count binaries for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def count_functions(binary_id: int) -> int:
        """Count the number of functions for a specific binary.

        Args:
            binary_id: The binary primary key.

        Returns:
            Total count of functions for the binary.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(func.count()).where(BinaryFunction.binary_id == binary_id))
            return result.scalar_one()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to count functions for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_by_user(user_id: int, *, offset: int = 0, limit: int = 50) -> list[Binary]:
        """List binaries uploaded by a specific user with pagination.

        Args:
            user_id: The user primary key.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of Binary ORM objects (expunged from session).
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(
                select(Binary)
                .where(Binary.uploaded_by == user_id)
                .order_by(Binary.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            binaries = result.scalars().all()
            for b in binaries:
                session.expunge(b)
            return list(binaries)
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to list binaries for user {}", user_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete(binary_id: int) -> None:
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
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def save_functions(binary_id: int, functions: list[dict[str, Any]]) -> None:
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
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save functions for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_functions(binary_id: int, offset: int = 0, limit: int | None = None) -> list[BinaryFunction]:
        """Load raw functions for a binary with optional pagination.

        Args:
            binary_id: Parent binary primary key.
            offset: Number of rows to skip (for pagination).
            limit: Maximum number of rows to return (for pagination).

        Returns:
            List of BinaryFunction ORM objects (expunged).
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            query = (
                select(BinaryFunction)
                .where(BinaryFunction.binary_id == binary_id)
                .order_by(BinaryFunction.function_name)
            )
            if offset > 0:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            result = await session.execute(query)
            functions = result.scalars().all()
            for f in functions:
                session.expunge(f)
            return list(functions)
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to load functions for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_all_ids() -> list[int]:
        """Return every binary id in the database.

        Returns:
            List of binary id integers.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(Binary.id))
            return list(result.scalars().all())
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to list binary ids")
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_name(binary_id: int) -> str | None:
        """Return the human-readable name for a binary.

        Args:
            binary_id: The binary primary key.

        Returns:
            Binary name or None if not found.
        """
        session: AsyncSession = await get_async_session("binaries")
        try:
            result = await session.execute(select(Binary.name).where(Binary.id == binary_id))
            return result.scalars().first()
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to get name for binary {}", binary_id)
            raise
        finally:
            await close_async_session(session)
