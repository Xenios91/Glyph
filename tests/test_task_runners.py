"""Tests for the background task runner functions in ``app.api.v1.task_runners``.

These runners execute *after* the HTTP response has returned, so failures here
leave tasks stuck at ``running`` forever. The tests cover the error paths,
empty-result paths, pipeline dispatch, and the ``finally`` cleanup that clears
the request context and schedules delayed task removal.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.api.types import TaskType
from app.api.v1 import task_runners
from app.processing.pipeline import PipelineContext
from app.processing.task_management import TaskManager


@pytest.fixture(autouse=True)
def _reset_task_manager() -> Any:
    """Reset TaskManager state before and after each test."""
    TaskManager._reset_for_testing()
    yield
    TaskManager._reset_for_testing()


def _mock_binary_function(
    name: str = "main", entrypoint: str = "0x400000", raw_code: str = "int main { return 0 }"
) -> Mock:
    """Create a Mock BinaryFunction ORM object."""
    bf = Mock()
    bf.function_name = name
    bf.entrypoint = entrypoint
    bf.raw_code = raw_code
    return bf


@contextmanager
def _patch_finally() -> Iterator[dict[str, Mock]]:
    """Patch the finally-block helpers so no real background tasks are created.

    Yields:
        A dict of the mocks keyed by ``create`` (create_background_task),
        ``remove`` (remove_task_delayed), and ``clear`` (clear_request_context).

    """
    with (
        patch.object(task_runners, "create_background_task") as mock_create,
        # remove_task_delayed is async; patch with a sync Mock so calling it
        # returns None instead of an un-awaited coroutine (which would be
        # discarded by the mocked create_background_task and trip
        # filterwarnings=["error"]).
        patch.object(task_runners, "remove_task_delayed", new=Mock()) as mock_remove,
        patch.object(task_runners, "clear_request_context") as mock_clear,
    ):
        yield {
            "create": mock_create,
            "remove": mock_remove,
            "clear": mock_clear,
        }


# ---------------------------------------------------------------------------
# run_code_reuse_task
# ---------------------------------------------------------------------------


class TestRunCodeReuseTask:
    """Tests for run_code_reuse_task."""

    @pytest.mark.asyncio
    async def test_run_code_reuse_no_functions_marks_error(self) -> None:
        """Source binary with no functions should mark the task as error."""
        TaskManager.register_task("uuid-1", "starting")
        with patch("app.database.binary_repository.BinaryRepository") as mock_repo:
            mock_repo.get_functions = AsyncMock(return_value=[])
            mock_repo.get_name = AsyncMock(return_value="source.elf")
            with _patch_finally():
                await task_runners.run_code_reuse_task(1, "uuid-1", "t")

        assert TaskManager.get_status("uuid-1") == "error"
        assert TaskManager.get_task_result("uuid-1") is None

    @pytest.mark.asyncio
    async def test_run_code_reuse_no_targets_completes_empty(self) -> None:
        """When no other binaries exist, the task completes with empty comparisons."""
        TaskManager.register_task("uuid-2", "starting")
        with patch("app.database.binary_repository.BinaryRepository") as mock_repo:
            mock_repo.get_functions = AsyncMock(return_value=[_mock_binary_function()])
            mock_repo.get_name = AsyncMock(return_value="source.elf")
            mock_repo.get_all_ids = AsyncMock(return_value=[1])  # only the source binary
            with _patch_finally():
                await task_runners.run_code_reuse_task(1, "uuid-2", "t")

        assert TaskManager.get_status("uuid-2") == "completed"
        result = TaskManager.get_task_result("uuid-2")
        assert result["comparisons"] == []
        assert result["source_binary_id"] == 1

    @pytest.mark.asyncio
    async def test_run_code_reuse_success_sets_result(self) -> None:
        """A successful comparison should store a result with the comparisons."""
        TaskManager.register_task("uuid-3", "starting")
        comparison = {
            "target_binary_id": 2,
            "target_binary_name": "target.elf",
            "matched_functions": [],
            "overall_similarity": 0.8,
        }
        with (
            patch("app.database.binary_repository.BinaryRepository") as mock_repo,
            patch(
                "app.services.code_reuse_detector.compare_binaries",
                new=AsyncMock(return_value=comparison),
            ),
        ):
            mock_repo.get_functions = AsyncMock(return_value=[_mock_binary_function()])
            mock_repo.get_name = AsyncMock(return_value="source.elf")
            mock_repo.get_all_ids = AsyncMock(return_value=[1, 2])
            with _patch_finally():
                await task_runners.run_code_reuse_task(1, "uuid-3", "t")

        assert TaskManager.get_status("uuid-3") == "completed"
        result = TaskManager.get_task_result("uuid-3")
        assert len(result["comparisons"]) == 1
        assert result["comparisons"][0]["target_binary_id"] == 2
        assert result["source_binary_id"] == 1
        assert result["source_binary_name"] == "source.elf"


# ---------------------------------------------------------------------------
# run_ml_task
# ---------------------------------------------------------------------------


def _mock_pipeline(result_ctx: PipelineContext) -> Mock:
    """Create a Mock pipeline whose execute() returns the given context."""
    pipeline = Mock()
    pipeline.execute = AsyncMock(return_value=result_ctx)
    return pipeline


class TestRunMlTask:
    """Tests for run_ml_task pipeline dispatch."""

    @pytest.mark.asyncio
    async def test_run_ml_task_training_dispatch(self) -> None:
        """ML_TRAINING should dispatch to TRAINING_FROM_DB_PIPELINE."""
        TaskManager.register_task("uuid-train", "starting")
        result_ctx = PipelineContext(uuid="uuid-train", binary_path="")
        mock_train_pipeline = _mock_pipeline(result_ctx)
        mock_pred_pipeline = _mock_pipeline(result_ctx)

        with (
            patch("app.processing.pipeline_configs.TRAINING_FROM_DB_PIPELINE", mock_train_pipeline),
            patch("app.processing.pipeline_configs.PREDICTION_FROM_DB_PIPELINE", mock_pred_pipeline),
            _patch_finally(),
        ):
            await task_runners.run_ml_task(
                1,
                "uuid-train",
                TaskType.ML_TRAINING,
                "t",
                "model",
                "classifier",
                user_id=1,
            )

        mock_train_pipeline.execute.assert_awaited_once()
        mock_pred_pipeline.execute.assert_not_awaited()
        assert TaskManager.get_status("uuid-train") == "completed"

    @pytest.mark.asyncio
    async def test_run_ml_task_prediction_dispatch(self) -> None:
        """ML_PREDICTION should dispatch to PREDICTION_FROM_DB_PIPELINE."""
        TaskManager.register_task("uuid-pred", "starting")
        result_ctx = PipelineContext(uuid="uuid-pred", binary_path="")
        mock_train_pipeline = _mock_pipeline(result_ctx)
        mock_pred_pipeline = _mock_pipeline(result_ctx)

        with (
            patch("app.processing.pipeline_configs.TRAINING_FROM_DB_PIPELINE", mock_train_pipeline),
            patch("app.processing.pipeline_configs.PREDICTION_FROM_DB_PIPELINE", mock_pred_pipeline),
            _patch_finally(),
        ):
            await task_runners.run_ml_task(
                1,
                "uuid-pred",
                TaskType.ML_PREDICTION,
                "t",
                "model",
                None,
                user_id=1,
            )

        mock_pred_pipeline.execute.assert_awaited_once()
        mock_train_pipeline.execute.assert_not_awaited()
        assert TaskManager.get_status("uuid-pred") == "completed"


# ---------------------------------------------------------------------------
# run_similarity_computation_task
# ---------------------------------------------------------------------------


class TestRunSimilarityComputationTask:
    """Tests for run_similarity_computation_task."""

    @pytest.mark.asyncio
    async def test_run_similarity_error_marks_computation_error(self) -> None:
        """A failure during computation should mark both the task and the computation as error."""
        TaskManager.register_task("uuid-sim", "starting")
        computation = Mock()
        computation.id = 42

        with (
            patch("app.database.similarity_repository.SimilarityRepository") as mock_sim_repo,
            patch("app.services.binary_similarity_service.BinarySimilarityService") as mock_service,
            _patch_finally(),
        ):
            mock_sim_repo.create = AsyncMock(return_value=computation)
            mock_sim_repo.update_status = AsyncMock()
            mock_service.compute_similarity_matrix = AsyncMock(side_effect=RuntimeError("boom"))
            with pytest.raises(RuntimeError, match="boom"):
                await task_runners.run_similarity_computation_task([1, 2], "uuid-sim", "t", 0.7, 1)

        assert TaskManager.get_status("uuid-sim") == "error"
        # The computation record should be marked as errored.
        mock_sim_repo.update_status.assert_called_once()
        kwargs = mock_sim_repo.update_status.call_args.kwargs
        assert kwargs["status"] == "error"
        assert kwargs["computation_id"] == 42


# ---------------------------------------------------------------------------
# finally-block cleanup
# ---------------------------------------------------------------------------


class TestRunnerFinallyCleanup:
    """Tests that the finally block runs cleanup in all runners."""

    @pytest.mark.asyncio
    async def test_runners_clear_request_context_in_finally(self) -> None:
        """All runners should clear the request context and schedule delayed removal in finally."""
        TaskManager.register_task("uuid-fin", "starting")
        with patch("app.database.binary_repository.BinaryRepository") as mock_repo:
            mock_repo.get_functions = AsyncMock(return_value=[])
            with _patch_finally() as mocks:
                await task_runners.run_code_reuse_task(1, "uuid-fin", "t")

        # The finally block must schedule delayed removal and clear the request context.
        mocks["create"].assert_called_once()
        mocks["clear"].assert_called_once()
