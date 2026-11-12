"""Regression tests: model-scoped prediction deletes must be scopeable per user.

The Prediction table is per-user (unique key ``task_name, model_name, user_id``),
so several users may hold predictions for the same ``model_name`` (e.g. via a
legacy/unowned model that every user can access). The bulk model-delete path
(``delete_model_predictions``) used to delete every row matching ``model_name``
with no ``user_id`` scope. The scoped delete must remove only the caller's own
rows plus unowned/legacy rows -- the same ownership rule as ``get`` /
``get_prediction_function`` / ``get_owner`` -- and never rows owned by another
user.
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
from app.services.prediction_service import PredictionService


@pytest_asyncio.fixture(scope="module", autouse=True)
async def prediction_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for prediction delete tests."""
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
    """Insert a minimal prediction row owned by ``user_id`` (None for legacy/unowned)."""
    await PredictionRepository.save(task_name, model_name, [{}], user_id=user_id)


async def _exists(task_name: str, model_name: str, user_id: int) -> bool:
    """Whether the row is still visible to the given user (own or unowned row)."""
    return await PredictionRepository.get(task_name, model_name, user_id=user_id) is not None


class TestDeleteModelPredictionsScoped:
    """Scoped model deletes must never touch another user's rows."""

    async def test_scoped_delete_removes_only_caller_rows(self, fresh_predictions_table: Any) -> None:
        """A scoped delete removes the caller's rows but keeps another user's rows."""
        await _insert_prediction("task_a", "model_m", user_id=1)
        await _insert_prediction("task_b", "model_m", user_id=2)

        # BUG (pre-fix): delete_model_predictions() had no user_id parameter; the
        # only available call was unscoped and deleted every row for the
        # model_name, including user 2's.
        await PredictionRepository.delete_model_predictions("model_m", user_id=1)

        assert await _exists("task_a", "model_m", user_id=1) is False, "caller's row must be deleted"
        assert await _exists("task_b", "model_m", user_id=2) is True, "another user's row must survive"

    async def test_scoped_delete_removes_unowned_rows(self, fresh_predictions_table: Any) -> None:
        """Unowned (legacy) rows are in the caller's scope and are deleted too."""
        await _insert_prediction("task_a", "model_m", user_id=1)
        await _insert_prediction("task_c", "model_m", user_id=None)

        await PredictionRepository.delete_model_predictions("model_m", user_id=1)

        assert await _exists("task_a", "model_m", user_id=1) is False
        assert await _exists("task_c", "model_m", user_id=1) is False, "unowned row must be deleted"

    async def test_anonymous_scoped_delete_removes_only_unowned(self, fresh_predictions_table: Any) -> None:
        """The anonymous user (id 0) can only delete unowned rows."""
        await _insert_prediction("task_a", "model_m", user_id=1)
        await _insert_prediction("task_c", "model_m", user_id=None)

        await PredictionRepository.delete_model_predictions("model_m", user_id=0)

        assert await _exists("task_a", "model_m", user_id=1) is True, "owned row must survive"
        assert await _exists("task_c", "model_m", user_id=0) is False, "unowned row must be deleted"

    async def test_unscoped_delete_keeps_legacy_behavior(self, fresh_predictions_table: Any) -> None:
        """user_id=None keeps the legacy admin/cleanup behavior (delete all rows)."""
        await _insert_prediction("task_a", "model_m", user_id=1)
        await _insert_prediction("task_b", "model_m", user_id=2)

        await PredictionRepository.delete_model_predictions("model_m")

        assert await _exists("task_a", "model_m", user_id=1) is False
        assert await _exists("task_b", "model_m", user_id=2) is False


class TestDeletePredictionsForModelService:
    """The service layer must forward the caller's user_id to the repository."""

    async def test_service_forwards_user_id(self, fresh_predictions_table: Any) -> None:
        """delete_predictions_for_model() with user_id must keep foreign rows."""
        await _insert_prediction("task_a", "model_m", user_id=1)
        await _insert_prediction("task_b", "model_m", user_id=2)

        await PredictionService.delete_predictions_for_model("model_m", user_id=1)

        assert await _exists("task_a", "model_m", user_id=1) is False
        assert await _exists("task_b", "model_m", user_id=2) is True
