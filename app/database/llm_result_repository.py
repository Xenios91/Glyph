"""Repository for LLMAnalysisResult entity database operations."""

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LLMAnalysisResult
from app.database.session_handler import close_async_session, get_async_session


class LLMResultRepository:
    """Repository for LLMAnalysisResult CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def upsert_many(target_name: str, results: list[LLMAnalysisResult]) -> None:
        """Insert or update stored LLM analysis results for one target.

        Rows are matched on (target_name, function_name, containing_function,
        entrypoint). Existing rows have status/analysis/error/model_name/
        elapsed_ms overwritten; missing rows are inserted. Duplicate keys
        within the batch collapse to a single row (last occurrence wins).
        The whole batch is persisted with a single commit.

        Args:
            target_name: Stable name of the scanned target (the report's model_name).
            results: LLMAnalysisResult instances to persist (their target_name
                is ignored and taken from the argument instead).

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            seen: dict[tuple[str, str, str, str], LLMAnalysisResult] = {}
            for result in results:
                key = (target_name, result.function_name, result.containing_function, result.entrypoint)
                row = seen.get(key)
                if row is None:
                    row = (
                        await session.execute(
                            select(LLMAnalysisResult).where(
                                LLMAnalysisResult.target_name == target_name,
                                LLMAnalysisResult.function_name == result.function_name,
                                LLMAnalysisResult.containing_function == result.containing_function,
                                LLMAnalysisResult.entrypoint == result.entrypoint,
                            ),
                        )
                    ).scalar_one_or_none()
                    if row is None:
                        row = LLMAnalysisResult(
                            target_name=target_name,
                            function_name=result.function_name,
                            containing_function=result.containing_function,
                            entrypoint=result.entrypoint,
                        )
                        session.add(row)
                    seen[key] = row
                row.status = result.status
                row.analysis = result.analysis
                row.error = result.error
                row.model_name = result.model_name
                row.elapsed_ms = result.elapsed_ms
            await session.commit()
            logger.info("Upserted {} LLM analysis result(s) for target '{}'", len(results), target_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to upsert LLM analysis results for target '{}'", target_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_for_target(target_name: str) -> list[LLMAnalysisResult]:
        """Retrieve all stored LLM analysis results for a target.

        Args:
            target_name: Stable name of the scanned target.

        Returns:
            List of LLMAnalysisResult instances ordered by function name,
            then containing function.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            stmt = (
                select(LLMAnalysisResult)
                .where(LLMAnalysisResult.target_name == target_name)
                .order_by(LLMAnalysisResult.function_name, LLMAnalysisResult.containing_function)
            )
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
            session.expunge_all()
            return rows
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve LLM analysis results for target '{}'", target_name)
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_for_target(target_name: str) -> bool:
        """Delete all stored LLM analysis results for a target.

        Args:
            target_name: Stable name of the scanned target.

        Returns:
            True when at least one row was deleted, False when nothing was stored.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            result = await session.execute(
                delete(LLMAnalysisResult).where(LLMAnalysisResult.target_name == target_name),
            )
            await session.commit()
            deleted = (result.rowcount or 0) > 0
            if deleted:
                logger.info("Deleted LLM analysis results for target '{}'", target_name)
            return deleted
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete LLM analysis results for target '{}'", target_name)
            raise
        finally:
            await close_async_session(session)
