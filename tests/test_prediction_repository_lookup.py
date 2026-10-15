"""Regression tests: prediction single-row reads must be scoped per user.

The Prediction table uses a per-user unique key (task_name, model_name, user_id),
so two users may share a (task_name, model_name) pair (e.g. via a legacy/unowned
model that every user can access). The single-row read methods
(``get``, ``get_prediction_function``, ``get_owner``) must return the caller's own
row in that case instead of misbehaving (a shared pair previously made
``scalar_one_or_none()`` raise ``MultipleResultsFound``, which the broad
``except SQLAlchemyError`` handlers swallowed into a "not found" sentinel --
404s on the caller's own data and an ownership-check bypass).
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from app.database.models import Base
from app.database.prediction_repository import PredictionRepository
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    init_async_databases,
)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def prediction_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for prediction lookup tests."""
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


async def _insert_prediction(task_name: str, model_name: str, user_id: int | None, functions: list) -> None:
    """Insert a prediction row owned by ``user_id`` (None for legacy/unowned)."""
    await PredictionRepository.save(task_name, model_name, functions, user_id=user_id)


class TestSharedTaskNameLookup:
    """Two users sharing a (task_name, model_name) pair must not break reads."""

    async def test_get_returns_caller_row_not_none(self, fresh_predictions_table: Any) -> None:
        """get() for a shared pair must return the caller's own row, not None."""
        await _insert_prediction("task_a", "model_a", user_id=1, functions=[{"functionName": "f1", "prediction": "A"}])
        await _insert_prediction("task_a", "model_a", user_id=2, functions=[{"functionName": "f2", "prediction": "B"}])

        # BUG (pre-fix): scalar_one_or_none() raised MultipleResultsFound, which was
        # swallowed by `except SQLAlchemyError` -> returned None -> endpoint 404s on
        # the caller's own prediction.
        # EXPECTED (post-fix): user 1 gets their own row.
        result = await PredictionRepository.get("task_a", "model_a", user_id=1)
        assert result is not None
        assert result.user_id == 1
        assert [f["functionName"] for f in result.predictions] == ["f1"]

    async def test_get_prediction_function_returns_caller_data(self, fresh_predictions_table: Any) -> None:
        """get_prediction_function() for a shared pair must return the caller's data."""
        await _insert_prediction("task_a", "model_a", user_id=1, functions=[{"functionName": "f1", "prediction": "A"}])
        await _insert_prediction("task_a", "model_a", user_id=2, functions=[{"functionName": "f2", "prediction": "B"}])

        # BUG (pre-fix): swallowed MultipleResultsFound -> returned {} -> endpoint 404s.
        data = await PredictionRepository.get_prediction_function("task_a", "model_a", "f1", user_id=1)
        assert data, "caller's function data should be returned"
        assert data["functionName"] == "f1"

    async def test_get_prediction_function_excludes_foreign_row(self, fresh_predictions_table: Any) -> None:
        """get_prediction_function() must not return another user's function data."""
        await _insert_prediction("task_a", "model_a", user_id=1, functions=[{"functionName": "f1", "prediction": "A"}])
        await _insert_prediction("task_a", "model_a", user_id=2, functions=[{"functionName": "f2", "prediction": "B"}])

        # User 2 does not own a function named "f1" in their row.
        data = await PredictionRepository.get_prediction_function("task_a", "model_a", "f1", user_id=2)
        assert data == {}

    async def test_get_owner_returns_caller_owner(self, fresh_predictions_table: Any) -> None:
        """get_owner() for a shared pair must return the caller's id, not None."""
        await _insert_prediction("task_a", "model_a", user_id=1, functions=[{"functionName": "f1"}])
        await _insert_prediction("task_a", "model_a", user_id=2, functions=[{"functionName": "f2"}])

        # BUG (pre-fix): swallowed MultipleResultsFound -> returned None, which the
        # ownership guard treats as legacy/unowned -> authorization bypass.
        owner = await PredictionRepository.get_owner("task_a", "model_a", user_id=1)
        assert owner == 1

    async def test_single_owner_still_works(self, fresh_predictions_table: Any) -> None:
        """Regression guard: the single-row (no shared pair) case keeps working."""
        await _insert_prediction("task_b", "model_b", user_id=1, functions=[{"functionName": "f1"}])

        result = await PredictionRepository.get("task_b", "model_b", user_id=1)
        assert result is not None
        assert result.user_id == 1

        data = await PredictionRepository.get_prediction_function("task_b", "model_b", "f1", user_id=1)
        assert data["functionName"] == "f1"

        owner = await PredictionRepository.get_owner("task_b", "model_b", user_id=1)
        assert owner == 1

    async def test_unowned_row_visible_to_all(self, fresh_predictions_table: Any) -> None:
        """A legacy/unowned row must remain readable by any user."""
        await _insert_prediction("task_c", "model_c", user_id=None, functions=[{"functionName": "f1"}])

        for uid in (0, 1, 2):
            result = await PredictionRepository.get("task_c", "model_c", user_id=uid)
            assert result is not None
            assert result.user_id is None

        owner = await PredictionRepository.get_owner("task_c", "model_c", user_id=1)
        assert owner is None  # unowned rows report no owner

    async def test_foreign_row_not_leaked(self, fresh_predictions_table: Any) -> None:
        """A row owned by another user must not be returned to the caller."""
        await _insert_prediction("task_d", "model_d", user_id=2, functions=[{"functionName": "f1"}])

        result = await PredictionRepository.get("task_d", "model_d", user_id=1)
        assert result is None

        data = await PredictionRepository.get_prediction_function("task_d", "model_d", "f1", user_id=1)
        assert data == {}

        owner = await PredictionRepository.get_owner("task_d", "model_d", user_id=1)
        assert owner is None
