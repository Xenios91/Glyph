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

    async def test_counts_own_and_unowned_rows(self, fresh_predictions_table: Any) -> None:
        """A user sees their own rows plus unowned (legacy) rows."""
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=1)
        await _insert_prediction("task_c", "model_a", user_id=None)
        await _insert_prediction("task_d", "model_a", user_id=2)

        assert await PredictionRepository.count_for_user(1) == 3

    async def test_excludes_rows_owned_by_other_users(self, fresh_predictions_table: Any) -> None:
        """Rows owned by another user are not counted."""
        await _insert_prediction("task_a", "model_a", user_id=2)
        await _insert_prediction("task_b", "model_a", user_id=3)

        assert await PredictionRepository.count_for_user(1) == 0

    async def test_anonymous_user_counts_only_unowned(self, fresh_predictions_table: Any) -> None:
        """The anonymous user (id 0) sees only unowned rows."""
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=None)
        await _insert_prediction("task_c", "model_a", user_id=None)

        assert await PredictionRepository.count_for_user(0) == 2

    async def test_returns_zero_when_no_rows(self, fresh_predictions_table: Any) -> None:
        """An empty table yields a count of zero."""
        assert await PredictionRepository.count_for_user(1) == 0
        assert await PredictionRepository.count_for_user(0) == 0


class TestGetTaskNamesForUser:
    """Ownership-scoped retrieval of prediction task names (no BLOB load)."""

    async def test_returns_own_and_unowned_task_names(self, fresh_predictions_table: Any) -> None:
        """A user sees their own tasks plus unowned (legacy) tasks."""
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=1)
        await _insert_prediction("task_c", "model_a", user_id=None)
        await _insert_prediction("task_d", "model_a", user_id=2)

        assert sorted(await PredictionRepository.get_task_names_for_user(1)) == [
            "task_a",
            "task_b",
            "task_c",
        ]

    async def test_excludes_tasks_owned_by_other_users(self, fresh_predictions_table: Any) -> None:
        """Tasks owned by another user are not returned."""
        await _insert_prediction("task_a", "model_a", user_id=2)
        await _insert_prediction("task_b", "model_a", user_id=3)

        assert await PredictionRepository.get_task_names_for_user(1) == []

    async def test_anonymous_user_sees_only_unowned(self, fresh_predictions_table: Any) -> None:
        """The anonymous user (id 0) sees only unowned tasks."""
        await _insert_prediction("task_a", "model_a", user_id=1)
        await _insert_prediction("task_b", "model_a", user_id=None)
        await _insert_prediction("task_c", "model_a", user_id=None)

        assert sorted(await PredictionRepository.get_task_names_for_user(0)) == [
            "task_b",
            "task_c",
        ]

    async def test_returns_empty_list_when_no_rows(self, fresh_predictions_table: Any) -> None:
        """An empty table yields an empty list."""
        assert await PredictionRepository.get_task_names_for_user(1) == []
        assert await PredictionRepository.get_task_names_for_user(0) == []
