"""Shared repository base for the scan-report tables.

``scan_reports`` (dangerous-function scans) and ``behavioral_scan_reports``
(behavioral scans) share an identical schema and identical CRUD semantics, so
their repositories were near-identical clones. This base implements the shared
logic once; each concrete repository only sets the ORM ``model`` class and a
human-readable ``label`` used in log messages.
"""

import json
from typing import Any

from loguru import logger
from sqlalchemy import delete, or_, select
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.database.session_handler import close_async_session, get_async_session


class ScanReportRepositoryBase:
    """Shared CRUD for the scan-report tables.

    Subclasses set ``model`` (the ORM class for the table) and ``label`` (the
    report label used in log messages, e.g. ``"scan report"`` or
    ``"behavioral scan report"``). All methods are classmethods so they can be
    called on the concrete subclass, matching the original static-method call
    sites.
    """

    model: type[Any]  # set by subclasses; the ORM class for the table
    label: str = "scan report"  # set by subclasses for log messages

    @classmethod
    def _ownership_clause(cls, user_id: int | None) -> ColumnElement[bool]:
        """Build an ownership filter for a report query.

        A report whose ``user_id`` is ``None`` (legacy/unowned) is visible to
        any authenticated user; otherwise only its owner sees it. The anonymous
        user (auth disabled, id 0) may only see unowned reports.

        Args:
            user_id: The current user's id (0 for anonymous).

        Returns:
            A SQLAlchemy boolean clause to add to the query's ``where``.

        """
        if user_id == 0:
            return cls.model.user_id.is_(None)
        return or_(cls.model.user_id == user_id, cls.model.user_id.is_(None))

    @classmethod
    def _save_owner_clause(cls, user_id: int | None) -> ColumnElement[bool]:
        """Build the owner filter for the save (upsert) lookup.

        When saving, an unowned report (``user_id`` is None) is matched to the
        unowned row, while a report owned by a user is matched to that user's
        row. This is intentionally narrower than :meth:`_ownership_clause`,
        which is used for reads and deletes.

        Args:
            user_id: Owner of the report (None for legacy/unowned).

        Returns:
            A SQLAlchemy boolean clause to add to the query's ``where``.

        """
        if user_id is None:
            return cls.model.user_id.is_(None)
        return cls.model.user_id == user_id

    @classmethod
    async def save_report(cls, report: dict[str, Any], user_id: int | None = None) -> None:
        """Insert or update the stored report for its target.

        The report dict is expected to match the API's report-response shape
        (model_name, severity counts, results). Each save replaces the whole
        stored report for the target; individual results are stored as a JSON
        array in results_json.

        Args:
            report: Serialized report (the response model's ``model_dump()``).
            user_id: Owner of the report (None for legacy/unowned).

        """
        target_name = str(report.get("model_name") or "unknown")
        results_json = json.dumps(report.get("results") or [], ensure_ascii=False)
        session: AsyncSession = await get_async_session("intelligence")
        try:
            row = (
                await session.execute(
                    select(cls.model).where(
                        cls.model.target_name == target_name,
                        cls._save_owner_clause(user_id),
                    ),
                )
            ).scalar_one_or_none()
            if row is None:
                row = cls.model(target_name=target_name, user_id=user_id)
                session.add(row)
            row.total_functions_scanned = int(report.get("total_functions_scanned") or 0)
            row.total_found = int(report.get("total_found") or 0)
            row.critical_count = int(report.get("critical_count") or 0)
            row.high_count = int(report.get("high_count") or 0)
            row.medium_count = int(report.get("medium_count") or 0)
            row.low_count = int(report.get("low_count") or 0)
            row.results_json = results_json
            await session.commit()
            logger.info("Saved {} for target '{}'", cls.label, target_name)
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to save {} for target '{}'", cls.label, target_name)
            raise
        finally:
            await close_async_session(session)

    @classmethod
    async def get_report(cls, target_name: str, user_id: int | None = None) -> Any:
        """Retrieve the stored report for a target.

        Args:
            target_name: Stable name of the scanned target.
            user_id: The current user's id (0 for anonymous); scopes the
                query to reports the user may access.

        Returns:
            The report row, or None when nothing is stored yet or the report
            is owned by another user.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            row = (
                await session.execute(
                    select(cls.model).where(
                        cls.model.target_name == target_name,
                        cls._ownership_clause(user_id),
                    ),
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            session.expunge_all()
            return row
        except sa_exc.SQLAlchemyError:
            logger.exception("Failed to retrieve {} for target '{}'", cls.label, target_name)
            return None
        finally:
            await close_async_session(session)

    @classmethod
    async def delete_for_target(cls, target_name: str, user_id: int | None = None) -> bool:
        """Delete the stored report for a target.

        Args:
            target_name: Stable name of the scanned target.
            user_id: The current user's id (0 for anonymous); only reports the
                user may access are deleted.

        Returns:
            True when a report was deleted, False when nothing was stored.

        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            result = await session.execute(
                delete(cls.model).where(
                    cls.model.target_name == target_name,
                    cls._ownership_clause(user_id),
                ),
            )
            await session.commit()
            # Result.rowcount exists at runtime for DELETE statements but is
            # not exposed on the Result[Any] type stub.
            deleted = (result.rowcount or 0) > 0  # type: ignore[attr-defined]
            if deleted:
                logger.info("Deleted {} for target '{}'", cls.label, target_name)
            return deleted
        except sa_exc.SQLAlchemyError:
            await session.rollback()
            logger.exception("Failed to delete {} for target '{}'", cls.label, target_name)
            raise
        finally:
            await close_async_session(session)
