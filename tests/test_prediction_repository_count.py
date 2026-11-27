"""Tests for PredictionRepository.count_for_user (ownership-scoped COUNT)."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.database.models import Base, Prediction
from app.database.prediction_repository import PredictionRepository
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    init_async_databases,
)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def prediction_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for prediction count tests."""
    await init_async_databases()

    target_tables = DB_TABLE_MAP.get("predictions")
    if target_tables and "predictions" in async_engines:
        async with async_engines["predictions"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def fresh_predictions_table() -> AsyncGenerator[None, None]:
    """Drop and recreate the predictions table before each test."""
    target_tables = DB_TABLE_MAP.get("predictions")
    if target_tables and "predictions" in async_engines:
        async with async_engines["predictions"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield


async def _insert_prediction(task_name: str, model_name: str, user_id: int | None) -> None:
    """Insert a minimal Prediction row (functions_data is not read by the count)."""
    await PredictionRepository.save(task_name, model_name, [{}], user_id=user_id)


class TestCountForUser:
    """Ownership-scoped counting of predictions for a user."""

    async def test_counts_only_own_rows(self, fresh_predictions_table: Any) -> None:
        """A user sees only their own rows; unowned and foreign rows are excluded.

        Deny-by-default, matching ``can_access``: unowned (legacy) rows
        (``user_id IS NULL``) and rows owned by another user are not counted.
        """
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=1)
        await _insert_prediction("task_c", "model_a", user_id=None)
        await _insert_prediction("task_d", "model_a", user_id=2)

        assert await PredictionRepository.count_for_user(1) == 2

    async def test_excludes_rows_owned_by_other_users(self, fresh_predictions_table: Any) -> None:
        """Rows owned by another user are not counted."""
        await _insert_prediction("task_a", "model_a", user_id=2)
        await _insert_prediction("task_b", "model_a", user_id=3)

        assert await PredictionRepository.count_for_user(1) == 0

    async def test_anonymous_user_counts_only_own_rows(self, fresh_predictions_table: Any) -> None:
        """The anonymous user (id 0) sees only rows created with user_id 0.

        Deny-by-default: unowned rows (``user_id IS NULL``) are not counted
        for the anonymous user either.
        """
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=None)
        await _insert_prediction("task_c", "model_a", user_id=0)

        assert await PredictionRepository.count_for_user(0) == 1

    async def test_returns_zero_when_no_rows(self, fresh_predictions_table: Any) -> None:
        """An empty table yields a count of zero."""
        assert await PredictionRepository.count_for_user(1) == 0
        assert await PredictionRepository.count_for_user(0) == 0


class TestGetTaskNamesForUser:
    """Ownership-scoped retrieval of prediction task names (no BLOB load)."""

    async def test_returns_only_own_task_names(self, fresh_predictions_table: Any) -> None:
        """A user sees only their own tasks; unowned and foreign tasks are excluded.

        Deny-by-default, matching ``can_access``: unowned (legacy) tasks
        (``user_id IS NULL``) and tasks owned by another user are not returned.
        """
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=1)
        await _insert_prediction("task_c", "model_a", user_id=None)
        await _insert_prediction("task_d", "model_a", user_id=2)

        assert sorted(await PredictionRepository.get_task_names_for_user(1)) == [
            "task_a",
            "task_b",
        ]

    async def test_excludes_tasks_owned_by_other_users(self, fresh_predictions_table: Any) -> None:
        """Tasks owned by another user are not returned."""
        await _insert_prediction("task_a", "model_a", user_id=2)
        await _insert_prediction("task_b", "model_a", user_id=3)

        assert await PredictionRepository.get_task_names_for_user(1) == []

    async def test_anonymous_user_sees_only_own_tasks(self, fresh_predictions_table: Any) -> None:
        """The anonymous user (id 0) sees only tasks created with user_id 0.

        Deny-by-default: unowned tasks (``user_id IS NULL``) are not returned
        to the anonymous user.
        """
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=None)
        await _insert_prediction("task_c", "model_a", user_id=0)

        assert sorted(await PredictionRepository.get_task_names_for_user(0)) == [
            "task_c",
        ]

    async def test_returns_empty_list_when_no_rows(self, fresh_predictions_table: Any) -> None:
        """An empty table yields an empty list."""
        assert await PredictionRepository.get_task_names_for_user(1) == []
        assert await PredictionRepository.get_task_names_for_user(0) == []


class TestGetPredictionsMetadataPagination:
    """SQL-level OFFSET/LIMIT pagination for prediction metadata."""

    async def test_limit_caps_rows_returned(self, fresh_predictions_table: Any) -> None:
        """Only ``limit`` rows are returned even when more exist."""
        for i in range(5):
            await _insert_prediction(f"task_{i:02d}", "model_a", user_id=1)

        rows = await PredictionRepository.get_predictions_metadata_for_user(1, limit=2)

        assert len(rows) == 2
        # Ordered by task_name, so the first two are the alphabetically earliest.
        assert [r["task_name"] for r in rows] == ["task_00", "task_01"]

    async def test_offset_selects_correct_slice(self, fresh_predictions_table: Any) -> None:
        """``offset`` skips the leading rows and the slice is correct."""
        for i in range(5):
            await _insert_prediction(f"task_{i:02d}", "model_a", user_id=1)

        rows = await PredictionRepository.get_predictions_metadata_for_user(1, offset=2, limit=2)

        assert [r["task_name"] for r in rows] == ["task_02", "task_03"]

    async def test_offset_beyond_range_returns_empty(self, fresh_predictions_table: Any) -> None:
        """An offset past the end of the data returns no rows."""
        await _insert_prediction("task_a", "model_a", user_id=1)

        rows = await PredictionRepository.get_predictions_metadata_for_user(1, offset=5, limit=10)

        assert rows == []

    async def test_no_limit_returns_all(self, fresh_predictions_table: Any) -> None:
        """With no limit the full (ordered) set is returned."""
        for i in range(3):
            await _insert_prediction(f"task_{i:02d}", "model_a", user_id=1)

        rows = await PredictionRepository.get_predictions_metadata_for_user(1)

        assert [r["task_name"] for r in rows] == ["task_00", "task_01", "task_02"]

    async def test_list_excludes_unowned_rows_for_all_users(self, fresh_predictions_table: Any) -> None:
        """The list query must NOT return unowned rows to any user (deny-by-default).

        Regression test for the ownership-model fix: list filters previously
        returned ``user_id == caller OR user_id IS NULL``, exposing unowned
        (legacy) rows to every authenticated user -- inconsistent with the
        single-resource 404. Unowned rows are now excluded from list results.
        """
        await _insert_prediction("task_unowned", "model_a", user_id=None)

        for uid in (0, 1, 2):
            rows = await PredictionRepository.get_predictions_metadata_for_user(uid)
            assert [r["task_name"] for r in rows] == [], (
                f"user {uid} must not see unowned rows in the list"
            )

    async def test_list_returns_only_own_rows(self, fresh_predictions_table: Any) -> None:
        """The list query SHOULD return the owner's own rows (and only those)."""
        await _insert_prediction("task_own_1", "model_a", user_id=1)
        await _insert_prediction("task_own_2", "model_a", user_id=1)
        await _insert_prediction("task_unowned", "model_a", user_id=None)
        await _insert_prediction("task_foreign", "model_a", user_id=2)

        rows = await PredictionRepository.get_predictions_metadata_for_user(1)

        assert [r["task_name"] for r in rows] == ["task_own_1", "task_own_2"]
        assert all(r["user_id"] == 1 for r in rows)
