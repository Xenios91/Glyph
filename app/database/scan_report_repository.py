"""Repository for ScanReport entity database operations."""

import json
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ScanReport
from app.database.session_handler import close_async_session, get_async_session


class ScanReportRepository:
    """Repository for ScanReport CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def save_report(report: dict[str, Any]) -> None:
        """Insert or update the stored scan report for its target.

        The report dict is expected to match the API's ScanReportResponse
        shape (model_name, severity counts, results). Each save replaces the
        whole stored report for the target; individual results are stored as
        a JSON array in results_json.

        Args:
            report: Serialized scan report (ScanReportResponse.model_dump()).

        """
        target_name = str(report.get("model_name") or "unknown")
        results_json = json.dumps(report.get("results") or [], ensure_ascii=False)
        session: AsyncSession = await get_async_session("intelligence")
        try:
            row = (
                await session.execute(
                    select(ScanReport).where(ScanReport.target_name == target_name),
                )
            ).scalar_one_or_none()
            if row is None:
                row = ScanReport(target_name=target_name)
                session.add(row)
            row.total_functions_scanned = int(report.get("total_functions_scanned") or 0)
            row.total_found = int(report.get("total_found") or 0)
            row.critical_count = int(report.get("critical_count") or 0)
            row.high_count = int(report.get("high_count") or 0)
            row.medium_count = int(report.get("medium_count") or 0)
            row.low_count = int(report.get("low_count") or 0)
            row.results_json = results_json
            await session.commit()
            logger.info("Saved scan report for target '{}'", target_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save scan report for target '{}'", target_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get_report(target_name: str) -> ScanReport | None:
        """Retrieve the stored scan report for a target.

        Args:
            target_name: Stable name of the scanned target.

        Returns:
            The ScanReport row, or None when nothing is stored yet.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            row = (
                await session.execute(
                    select(ScanReport).where(ScanReport.target_name == target_name),
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            session.expunge_all()
            return row
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve scan report for target '{}'", target_name)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete_for_target(target_name: str) -> bool:
        """Delete the stored scan report for a target.

        Args:
            target_name: Stable name of the scanned target.

        Returns:
            True when a report was deleted, False when nothing was stored.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            result = await session.execute(
                delete(ScanReport).where(ScanReport.target_name == target_name),
            )
            await session.commit()
            deleted = (result.rowcount or 0) > 0
            if deleted:
                logger.info("Deleted scan report for target '{}'", target_name)
            return deleted
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete scan report for target '{}'", target_name)
            raise
        finally:
            await close_async_session(session)
