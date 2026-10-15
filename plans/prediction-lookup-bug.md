# Bug: Prediction read path ignores the per-user unique key

## Summary
The `Prediction` table is keyed per-user, but the single-row read methods query by
only `(task_name, model_name)`. When two rows share a `(task_name, model_name)` pair
(different `user_id`), `scalar_one_or_none()` raises `MultipleResultsFound`. Because
that exception is a `SQLAlchemyError` subclass, the `except sa_exc.SQLAlchemyError`
handlers **swallow it** and return a "not found" sentinel. Net effect: a user's own
prediction becomes inaccessible (404) and the ownership check on `getPredictionDetails`
is bypassed.

## Evidence (confirmed by reading the code)
- `app/database/models.py:108-115` — the schema deliberately allows two users to share
  a `(task_name, model_name)` pair:
  ```
  # Per-user uniqueness: two users may share a (task_name, model_name) pair,
  __table_args__ = (
      UniqueConstraint("task_name", "model_name", "user_id", name="uq_predictions_task_model_user"),
  )
  ```
- `app/database/prediction_repository.py:251-301` — `save()` upserts on the per-user
  composite key `(task_name, model_name, user_id)` (docstring: "Two users may therefore
  share a (task_name, model_name) pair").
- `app/database/prediction_repository.py:200-248` — `get()` selects on
  `(task_name, model_name)` only and uses `result.scalar_one_or_none()` (line 220);
  on collision the `except sa_exc.SQLAlchemyError` (line 244) returns `None`.
- `app/database/prediction_repository.py:303-354` — `get_prediction_function()` selects
  on `(model_name, task_name)` only and uses `result.scalar_one_or_none()` (line 324);
  on collision the `except sa_exc.SQLAlchemyError` (line 346) falls through to
  `return {}` (line 354).
- `app/database/prediction_repository.py:489-515` — `get_owner()` selects on
  `(task_name, model_name)` only and uses `result.scalar_one_or_none()` (line 510);
  on collision the `except sa_exc.SQLAlchemyError` (line 511) returns `None`.

## Why the collision is reachable
`Model.model_name` is **globally unique** (`app/database/models.py:51`), so two users
cannot own models with the same name. The shared `(task_name, model_name)` pair is
therefore reachable only through a **legacy/unowned model** (`user_id IS NULL`), which
`can_access` (`app/auth/dependencies.py:246-265`) exposes to every user:
1. A legacy model "M" (user_id NULL) is usable by any user.
2. `task_name` uniqueness is per-user (`task_name_exists` is scoped to `user_id`), so
   user 1 and user 2 can both name a task "T".
3. Both run a prediction with model "M" and task "T" -> rows `(T, M, 1)` and `(T, M, 2)`.

## Consequences (confirmed by tracing the call paths)
- `get()` -> `PredictionService.get_prediction()` -> `app/web/endpoints/web.py:300-313`
  `getPrediction`: `prediction is None` -> **HTTP 404** even though the caller owns a
  row. The caller's own prediction is inaccessible.
- `get_prediction_function()` -> `PredictionService.get_prediction_function_details()`
  -> `app/web/endpoints/web.py:242-297` and `app/api/v1/endpoints/models.py:199-249`
  `getPredictionDetails`: `prediction_data` is `{}` -> **HTTP 404**.
- `get_owner()` -> `app/api/v1/endpoints/models.py:208-209`: returns `None`, and
  `assert_owned(SimpleNamespace(user_id=None), ...)` treats `user_id=None` as
  legacy/unowned -> **ownership check bypassed** (the guard that should 404 a foreign
  row is skipped). It is currently masked by the downstream 404, but it is a real
  authorization gap on the same code path.

The codebase already has the correct per-user pattern elsewhere (`get_for_user` at
`prediction_repository.py:457-479`, `get_owner_by_task` at `424-455`, and the
`owned_or_unowned_filter` helper) — these three methods simply were not updated to use it.

## Secondary finding (same root cause, lower impact)
`PredictionRepository.delete_model_predictions()` (`prediction_repository.py:402-422`)
deletes by `model_name` only with no `user_id` scope, and is called from
`app/api/v1/endpoints/models.py:48-49` and `91-92` (model delete). Because
`model_name` is globally unique this is less likely to hit a foreign row, but the
delete is still not ownership-scoped. (Flagged for review; not the primary bug.)

## Fix (recommended)
Scope the three read methods to the caller, mirroring the existing `get_for_user`
pattern. Add an optional `user_id` parameter and an ownership filter
(`user_id == caller OR user_id IS NULL`) to:
- `get(task_name, model_name, user_id=None)`
- `get_prediction_function(task_name, model_name, function_name, user_id=None)`
- `get_owner(task_name, model_name, user_id=None)`

and pass `current_user.id` from the endpoints
(`web.py` getPrediction / getPredictionDetails, `models.py` getPredictionDetails).
When `user_id` is provided the query returns at most one row, so
`scalar_one_or_none()` is safe and the ownership check is correct.

## Confirmation test (to be added in Code mode)
New file `tests/test_prediction_repository_lookup.py`, following the fixture pattern in
`tests/test_prediction_repository_count.py`. These tests FAIL before the fix (wrong
sentinel returned on a shared pair) and PASS after the fix.

```python
"""Regression test: prediction reads must be scoped per user.

The Prediction table uses a per-user unique key (task_name, model_name, user_id),
so two users may share a (task_name, model_name) pair (e.g. via a legacy/unowned
model). The single-row read methods must not misbehave when that happens.
"""

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
    target_tables = DB_TABLE_MAP.get("predictions")
    if target_tables and "predictions" in async_engines:
        async with async_engines["predictions"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield


async def _insert(task_name: str, model_name: str, user_id: int | None, functions: list) -> None:
    await PredictionRepository.save(task_name, model_name, functions, user_id=user_id)


class TestSharedTaskNameLookup:
    """Two users sharing a (task_name, model_name) pair must not break reads."""

    async def test_get_returns_caller_row_not_none(self, fresh_predictions_table: Any) -> None:
        """get() for a shared pair must return the caller's own row, not None."""
        await _insert("task_a", "model_a", user_id=1, functions=[{"functionName": "f1", "prediction": "A"}])
        await _insert("task_a", "model_a", user_id=2, functions=[{"functionName": "f2", "prediction": "B"}])

        # BUG (pre-fix): scalar_one_or_none() raises MultipleResultsFound, which is
        # swallowed by `except SQLAlchemyError` -> returns None -> endpoint 404s.
        # EXPECTED (post-fix): user 1 gets their own row.
        result = await PredictionRepository.get("task_a", "model_a", user_id=1)
        assert result is not None
        assert result.user_id == 1

    async def test_get_prediction_function_returns_caller_data(self, fresh_predictions_table: Any) -> None:
        """get_prediction_function() for a shared pair must return the caller's data."""
        await _insert("task_a", "model_a", user_id=1, functions=[{"functionName": "f1", "prediction": "A"}])
        await _insert("task_a", "model_a", user_id=2, functions=[{"functionName": "f2", "prediction": "B"}])

        # BUG (pre-fix): swallowed MultipleResultsFound -> returns {} -> endpoint 404s.
        data = await PredictionRepository.get_prediction_function("task_a", "model_a", "f1", user_id=1)
        assert data, "caller's function data should be returned"

    async def test_get_owner_returns_caller_owner(self, fresh_predictions_table: Any) -> None:
        """get_owner() for a shared pair must return the caller's id, not None."""
        await _insert("task_a", "model_a", user_id=1, functions=[{"functionName": "f1"}])
        await _insert("task_a", "model_a", user_id=2, functions=[{"functionName": "f2"}])

        # BUG (pre-fix): swallowed MultipleResultsFound -> returns None, which the
        # ownership guard treats as legacy/unowned -> authorization bypass.
        owner = await PredictionRepository.get_owner("task_a", "model_a", user_id=1)
        assert owner == 1

    async def test_single_owner_still_works(self, fresh_predictions_table: Any) -> None:
        """Regression guard: the single-row (no shared pair) case keeps working."""
        await _insert("task_b", "model_b", user_id=1, functions=[{"functionName": "f1"}])
        result = await PredictionRepository.get("task_b", "model_b", user_id=1)
        assert result is not None
        assert result.user_id == 1
```

Expected outcome:
- **Before the fix:** the three "shared pair" tests FAIL (each method returns the
  `None`/`{}` sentinel instead of the caller's row), proving the bug.
- **After the fix:** all four tests PASS.

## Out of scope / not bugs (checked and cleared)
- `PredictStep` probability threshold (`app/processing/steps.py:484-505`): probabilities
  are scaled by `* 100` and the config threshold is 0-100 (`app/config/settings.py:69-74`),
  so the comparison is consistent.
- `TrainStep` saves the model itself (`app/processing/steps.py:416-421`), so the
  prediction pipeline's `ModelRepository.load_model` will find it.
- `PredictionRepository.get_predictions_list()` (`prediction_repository.py:25-64`) is
  global (no ownership filter), but it is not referenced by any endpoint (the API list
  path uses the scoped `get_predictions_metadata_for_user`), so it is dead/latent code,
  not an active data leak.
