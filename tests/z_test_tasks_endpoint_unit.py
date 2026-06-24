"""Unit tests for tasks API v1 endpoints with mocking to ensure full coverage."""
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Mock heavy modules BEFORE any app imports to prevent ProcessPoolExecutor spawning
_MOCKED_MODULES = [
    "app.processing.task_management",
    "app.processing.pipeline",
    "app.processing.steps",
    "app.services.request_handler",
    "app.utils.persistence_util",
    "app.services.binary_similarity_service",
    "app.services.code_reuse_detector",
    "app.services.dangerous_function_scanner",
]
_original_modules: dict[str, Any] = {}
for _mod in _MOCKED_MODULES:
    _original_modules[_mod] = sys.modules.get(_mod)
    sys.modules[_mod] = MagicMock()

import pytest  # noqa: E402

from app.api.v1.endpoints.tasks import (  # noqa: E402
    _run_code_reuse_task,  # noqa: F401
    _run_dangerous_functions_task,  # noqa: F401
    _run_ml_task,  # noqa: F401
    _run_similarity_computation_task,  # noqa: F401
    delete_similarity_computation,
    execute_task,
    get_similarity_computation,
    get_task_results,
    get_task_status,
    list_similarity_computations,
    start_similarity_computation,
)
from app.database.models import User  # noqa: E402
from app.utils.request_context import CapturedContext  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _module_sys_modules_isolation() -> Any:
    """Restore original modules after this file's tests complete.

    The module-level code (lines 17-20) already replaced modules with MagicMock
    at import time. This fixture restores the originals after all tests in this
    module have run, preventing sys.modules pollution from leaking to other tests.
    """
    yield
    # Restore original modules so other test files are not affected.
    for _mod in _MOCKED_MODULES:
        if _original_modules[_mod] is not None:
            sys.modules[_mod] = _original_modules[_mod]
        else:
            sys.modules.pop(_mod, None)


@pytest.fixture(autouse=True)
def _restore_sys_modules() -> Any:
    """Re-apply fresh mocks after each test to ensure clean state.

    Do NOT restore original modules here because subsequent tests in this
    file depend on the mocks being present in sys.modules. The parent
    _module_sys_modules_isolation fixture handles restoring originals.
    """
    yield
    # Re-apply mocks to ensure clean state for next test.
    for _mod in _MOCKED_MODULES:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_current_user() -> User:
    """Create a mock current user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_binary() -> MagicMock:
    """Create a mock binary owned by the test user."""
    binary = MagicMock()
    binary.id = 1
    binary.name = "test.elf"
    binary.uploaded_by = 1  # matches mock_current_user.id
    return binary


@pytest.fixture
def mock_background_tasks() -> MagicMock:
    """Create a mock BackgroundTasks instance."""
    return MagicMock()


@pytest.fixture
def mock_tm() -> Any:
    """Configure TaskManager mock with proper get_uuid return."""
    with patch("app.api.v1.endpoints.tasks.TaskManager") as mock:
        mock().get_uuid.return_value = "test-task-uuid"
        yield mock


# ---------------------------------------------------------------------------
# Background task: _run_code_reuse_task
# ---------------------------------------------------------------------------

class TestRunCodeReuseTask:
    """Tests for _run_code_reuse_task background task."""

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_success(self, mock_tm: Any) -> None:
        """Test code reuse task completes successfully with comparisons."""
        # Mock binary function with required attributes
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")
        mock_sql_util.get_all_binary_ids = AsyncMock(return_value=[1, 2])

        # Configure PipelineContext mock
        mock_ctx = MagicMock()
        mock_ctx.error = None

        sys.modules["app.processing.pipeline"].PipelineContext.return_value = mock_ctx

        # Configure TokenizeStep and FilterStep to return context without error
        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        mock_filter = MagicMock()
        mock_filter.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].FilterStep.return_value = mock_filter

        # Configure compare_binaries
        mock_compare = AsyncMock(return_value={"target_id": 2, "matches": []})
        sys.modules["app.services.code_reuse_detector"].compare_binaries = mock_compare

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_code_reuse_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-reuse",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_no_functions(self, mock_tm: Any) -> None:
        """Test code reuse task errors when no functions found."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_code_reuse_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-reuse",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_no_targets(self, mock_tm: Any) -> None:
        """Test code reuse task completes when no other binaries to compare."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")
        mock_sql_util.get_all_binary_ids = AsyncMock(return_value=[1])

        mock_ctx = MagicMock()
        mock_ctx.error = None
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = mock_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        mock_filter = MagicMock()
        mock_filter.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].FilterStep.return_value = mock_filter

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_code_reuse_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-reuse",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_tokenization_error(self, mock_tm: Any) -> None:
        """Test code reuse task handles tokenization failure."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        mock_ctx = MagicMock()
        mock_ctx.error = "Tokenization failed"
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = mock_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_code_reuse_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-reuse",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_filter_error(self, mock_tm: Any) -> None:
        """Test code reuse task handles filtering failure."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        good_ctx = MagicMock()
        good_ctx.error = None
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = good_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=good_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        error_ctx = MagicMock()
        error_ctx.error = "Filter failed"
        mock_filter = MagicMock()
        mock_filter.execute = AsyncMock(return_value=error_ctx)
        sys.modules["app.processing.steps"].FilterStep.return_value = mock_filter

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_code_reuse_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-reuse",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_exception(self, mock_tm: Any) -> None:
        """Test code reuse task handles exceptions."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(side_effect=RuntimeError("DB error"))

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    with pytest.raises(RuntimeError):
                        await _run_code_reuse_task(
                            binary_id=1,
                            task_uuid="test-uuid",
                            task_name="test-reuse",
                        )
                    mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_code_reuse_task_with_context(self, mock_tm: Any) -> None:
        """Test code reuse task with captured request context."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[])

        captured_ctx = MagicMock(spec=CapturedContext)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.restore_request_context") as mock_restore:
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    await _run_code_reuse_task(
                        binary_id=1,
                        task_uuid="test-uuid",
                        task_name="test-reuse",
                        captured_ctx=captured_ctx,
                    )
                    mock_restore.assert_called_once()


# ---------------------------------------------------------------------------
# Background task: _run_dangerous_functions_task
# ---------------------------------------------------------------------------

class TestRunDangerousFunctionsTask:
    """Tests for _run_dangerous_functions_task background task."""

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_success(self, mock_tm: Any) -> None:
        """Test dangerous functions task completes successfully."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        mock_ctx = MagicMock()
        mock_ctx.error = None
        mock_ctx.get = MagicMock(return_value=[])
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = mock_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        mock_filter = MagicMock()
        mock_filter.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].FilterStep.return_value = mock_filter

        mock_report = MagicMock()
        mock_report.total_functions_scanned = 1
        mock_report.total_found = 0
        mock_report.critical_count = 0
        mock_report.high_count = 0
        mock_report.medium_count = 0
        mock_report.low_count = 0
        mock_report.results = []

        mock_generate = MagicMock(return_value=mock_report)
        sys.modules["app.services.dangerous_function_scanner"].generate_report = mock_generate

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_dangerous_functions_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-dangerous",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_no_functions(self, mock_tm: Any) -> None:
        """Test dangerous functions task errors when no functions found."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_dangerous_functions_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-dangerous",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_tokenization_error(self, mock_tm: Any) -> None:
        """Test dangerous functions task handles tokenization failure."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        mock_ctx = MagicMock()
        mock_ctx.error = "Tokenization failed"
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = mock_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=mock_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_dangerous_functions_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-dangerous",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_filter_error(self, mock_tm: Any) -> None:
        """Test dangerous functions task handles filtering failure."""
        mock_bf = MagicMock()
        mock_bf.function_name = "func1"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main(void) { return 0; }"

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[mock_bf])
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        good_ctx = MagicMock()
        good_ctx.error = None
        sys.modules["app.processing.pipeline"].PipelineContext.return_value = good_ctx

        mock_tokenize = MagicMock()
        mock_tokenize.execute = AsyncMock(return_value=good_ctx)
        sys.modules["app.processing.steps"].TokenizeStep.return_value = mock_tokenize

        error_ctx = MagicMock()
        error_ctx.error = "Filter failed"
        mock_filter = MagicMock()
        mock_filter.execute = AsyncMock(return_value=error_ctx)
        sys.modules["app.processing.steps"].FilterStep.return_value = mock_filter

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_dangerous_functions_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_name="test-dangerous",
                )
                mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_exception(self, mock_tm: Any) -> None:
        """Test dangerous functions task handles exceptions."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(side_effect=RuntimeError("DB error"))

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    with pytest.raises(RuntimeError):
                        await _run_dangerous_functions_task(
                            binary_id=1,
                            task_uuid="test-uuid",
                            task_name="test-dangerous",
                        )
                    mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_dangerous_functions_task_with_context(self, mock_tm: Any) -> None:
        """Test dangerous functions task with captured request context."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_binary_functions = AsyncMock(return_value=[])

        captured_ctx = MagicMock(spec=CapturedContext)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.restore_request_context") as mock_restore:
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    await _run_dangerous_functions_task(
                        binary_id=1,
                        task_uuid="test-uuid",
                        task_name="test-dangerous",
                        captured_ctx=captured_ctx,
                    )
                    mock_restore.assert_called_once()


# ---------------------------------------------------------------------------
# Background task: _run_ml_task
# ---------------------------------------------------------------------------

class TestRunMLTask:
    """Tests for _run_ml_task background task."""

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_training_success(self, mock_tm: Any) -> None:
        """Test ML training task completes successfully."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False
        mock_result.get = MagicMock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            await _run_ml_task(
                binary_id=1,
                task_uuid="test-uuid",
                task_type=TaskType.ML_TRAINING,
                task_name="test-training",
                model_name="test-model",
                ml_class_type="malware",
            )
            mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_prediction_success(self, mock_tm: Any) -> None:
        """Test ML prediction task completes successfully."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False
        mock_result.get = MagicMock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            await _run_ml_task(
                binary_id=1,
                task_uuid="test-uuid",
                task_type=TaskType.ML_PREDICTION,
                task_name="test-prediction",
                model_name="test-model",
            )
            mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_error_result(self, mock_tm: Any) -> None:
        """Test ML task handles pipeline error result."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = "Something failed"
        mock_result.exc_info = None
        mock_result.get = MagicMock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            await _run_ml_task(
                binary_id=1,
                task_uuid="test-uuid",
                task_type=TaskType.ML_TRAINING,
                task_name="test-training",
                model_name="test-model",
                ml_class_type="malware",
            )
            mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_exception(self, mock_tm: Any) -> None:
        """Test ML task handles unexpected exceptions."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_pipeline.execute = AsyncMock(side_effect=RuntimeError("Pipeline crash"))

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            with pytest.raises(RuntimeError):
                await _run_ml_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_type=TaskType.ML_TRAINING,
                    task_name="test-training",
                    model_name="test-model",
                    ml_class_type="malware",
                )
            mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_with_context(self, mock_tm: Any) -> None:
        """Test ML task with captured request context."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False
        mock_result.get = MagicMock(return_value=None)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        captured_ctx = MagicMock(spec=CapturedContext)

        with patch("app.api.v1.endpoints.tasks.restore_request_context") as mock_restore:
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                await _run_ml_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_type=TaskType.ML_TRAINING,
                    task_name="test-training",
                    model_name="test-model",
                    ml_class_type="malware",
                    captured_ctx=captured_ctx,
                )
                mock_restore.assert_called_once()

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_training_with_functions(self, mock_tm: Any) -> None:
        """Test ML training task persists functions when available."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False

        def _get(key, default=None):
            if key == "filtered_functions":
                return ["func1"]
            if key == "errored_functions":
                return []
            return default

        mock_result.get = MagicMock(side_effect=_get)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        mock_persist = sys.modules["app.utils.persistence_util"]
        mock_persist.FunctionPersistanceUtil.add_model_functions = AsyncMock()

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            await _run_ml_task(
                binary_id=1,
                task_uuid="test-uuid",
                task_type=TaskType.ML_TRAINING,
                task_name="test-training",
                model_name="test-model",
                ml_class_type="malware",
            )
            mock_persist.FunctionPersistanceUtil.add_model_functions.assert_called_once()
            mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_prediction_with_predictions(self, mock_tm: Any) -> None:
        """Test ML prediction task persists predictions when available."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False

        def _get(key, default=None):
            if key == "filtered_functions":
                return ["func1"]
            if key == "predictions":
                return ["pred1"]
            if key == "errored_functions":
                return []
            return default

        mock_result.get = MagicMock(side_effect=_get)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        mock_persist = sys.modules["app.utils.persistence_util"]
        mock_persist.FunctionPersistanceUtil.add_prediction_functions = AsyncMock()

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            await _run_ml_task(
                binary_id=1,
                task_uuid="test-uuid",
                task_type=TaskType.ML_PREDICTION,
                task_name="test-prediction",
                model_name="test-model",
            )
            mock_persist.FunctionPersistanceUtil.add_prediction_functions.assert_called_once()
            mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_training_persistence_error(self, mock_tm: Any) -> None:
        """Test ML training task raises when persistence fails."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False

        def _get(key, default=None):
            if key == "filtered_functions":
                return ["func1"]
            if key == "errored_functions":
                return []
            return default

        mock_result.get = MagicMock(side_effect=_get)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        mock_persist = sys.modules["app.utils.persistence_util"]
        mock_persist.FunctionPersistanceUtil.add_model_functions = AsyncMock(side_effect=RuntimeError("Persist failed"))

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            with pytest.raises(RuntimeError):
                await _run_ml_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_type=TaskType.ML_TRAINING,
                    task_name="test-training",
                    model_name="test-model",
                    ml_class_type="malware",
                )
            mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_ml_task_prediction_persistence_error(self, mock_tm: Any) -> None:
        """Test ML prediction task raises when persistence fails."""
        from app.api.v1.endpoints.tasks import TaskType

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.error = False

        def _get(key, default=None):
            if key == "filtered_functions":
                return ["func1"]
            if key == "predictions":
                return ["pred1"]
            if key == "errored_functions":
                return []
            return default

        mock_result.get = MagicMock(side_effect=_get)
        mock_pipeline.execute = AsyncMock(return_value=mock_result)

        mock_pipeline_cls = sys.modules["app.processing.pipeline"]
        mock_pipeline_cls.ProcessingPipeline.return_value = mock_pipeline

        mock_persist = sys.modules["app.utils.persistence_util"]
        mock_persist.FunctionPersistanceUtil.add_prediction_functions = AsyncMock(side_effect=RuntimeError("Persist failed"))

        with patch("app.api.v1.endpoints.tasks.clear_request_context"):
            with pytest.raises(RuntimeError):
                await _run_ml_task(
                    binary_id=1,
                    task_uuid="test-uuid",
                    task_type=TaskType.ML_PREDICTION,
                    task_name="test-prediction",
                    model_name="test-model",
                )
            mock_tm.set_status.assert_any_call("test-uuid", "error")


# ---------------------------------------------------------------------------
# Background task: _run_similarity_computation_task
# ---------------------------------------------------------------------------

class TestRunSimilarityComputationTask:
    """Tests for _run_similarity_computation_task background task."""

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_similarity_task_success(self, mock_tm: Any) -> None:
        """Test similarity computation task completes successfully."""
        mock_sql_util = MagicMock()
        mock_computation = MagicMock()
        mock_computation.id = 42
        mock_sql_util.create_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.save_similarity_pairs = AsyncMock()
        mock_sql_util.update_similarity_computation_status = AsyncMock()

        mock_service = MagicMock()
        mock_entry = MagicMock()
        mock_entry.binary_a_id = 1
        mock_entry.binary_b_id = 2
        mock_entry.overall_similarity = 0.85
        mock_entry.matched_function_count = 10
        mock_entry.total_function_comparisons = 20
        mock_service.compute_similarity_matrix = AsyncMock(return_value=[mock_entry])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.services.binary_similarity_service.BinarySimilarityService", mock_service):
                with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                    with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                        await _run_similarity_computation_task(
                            binary_ids=[1, 2],
                            task_uuid="test-uuid",
                            task_name="test-similarity",
                            match_threshold=0.7,
                            user_id=1,
                        )
                        mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_similarity_task_exception(self, mock_tm: Any) -> None:
        """Test similarity computation task handles exceptions."""
        mock_sql_util = MagicMock()
        mock_sql_util.create_similarity_computation = AsyncMock(side_effect=RuntimeError("DB error"))

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    with pytest.raises(RuntimeError):
                        await _run_similarity_computation_task(
                            binary_ids=[1, 2],
                            task_uuid="test-uuid",
                            task_name="test-similarity",
                            match_threshold=0.7,
                            user_id=1,
                        )
                    mock_tm.set_status.assert_any_call("test-uuid", "error")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_similarity_task_with_context(self, mock_tm: Any) -> None:
        """Test similarity computation task with captured request context."""
        mock_sql_util = MagicMock()
        mock_computation = MagicMock()
        mock_computation.id = 42
        mock_sql_util.create_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.save_similarity_pairs = AsyncMock()
        mock_sql_util.update_similarity_computation_status = AsyncMock()

        mock_service = MagicMock()
        mock_service.compute_similarity_matrix = AsyncMock(return_value=[])

        captured_ctx = MagicMock(spec=CapturedContext)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.services.binary_similarity_service.BinarySimilarityService", mock_service):
                with patch("app.api.v1.endpoints.tasks.restore_request_context") as mock_restore:
                    with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                        await _run_similarity_computation_task(
                            binary_ids=[1, 2],
                            task_uuid="test-uuid",
                            task_name="test-similarity",
                            match_threshold=0.7,
                            user_id=1,
                            captured_ctx=captured_ctx,
                        )
                        mock_restore.assert_called_once()

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_similarity_task_empty_matrix(self, mock_tm: Any) -> None:
        """Test similarity computation with empty matrix."""
        mock_sql_util = MagicMock()
        mock_computation = MagicMock()
        mock_computation.id = 42
        mock_sql_util.create_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.save_similarity_pairs = AsyncMock()
        mock_sql_util.update_similarity_computation_status = AsyncMock()

        mock_service = MagicMock()
        mock_service.compute_similarity_matrix = AsyncMock(return_value=[])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.services.binary_similarity_service.BinarySimilarityService", mock_service):
                with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                    await _run_similarity_computation_task(
                        binary_ids=[1, 2],
                        task_uuid="test-uuid",
                        task_name="test-similarity",
                        match_threshold=0.7,
                        user_id=1,
                    )
                    mock_tm.set_status.assert_any_call("test-uuid", "completed")

    @patch("app.api.v1.endpoints.tasks.TaskManager")
    async def test_run_similarity_task_error_persists_state(self, mock_tm: Any) -> None:
        """Test similarity task persists error state when main body fails."""
        mock_sql_util = MagicMock()
        # First call (main body) raises, second call (error cleanup) succeeds
        mock_computation = MagicMock()
        mock_computation.id = 42
        mock_sql_util.create_similarity_computation = AsyncMock(
            side_effect=[RuntimeError("Main failure"), mock_computation]
        )
        mock_sql_util.update_similarity_computation_status = AsyncMock()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.clear_request_context"):
                with pytest.raises(RuntimeError):
                    await _run_similarity_computation_task(
                        binary_ids=[1, 2],
                        task_uuid="test-uuid",
                        task_name="test-similarity",
                        match_threshold=0.7,
                        user_id=1,
                    )
                # Verify error state was persisted
                mock_sql_util.update_similarity_computation_status.assert_called_once_with(
                    computation_id=42,
                    status="error",
                )


# ---------------------------------------------------------------------------
# Endpoint: execute_task
# ---------------------------------------------------------------------------

class TestExecuteTask:
    """Tests for execute_task endpoint."""

    @pytest.mark.asyncio
    async def test_execute_task_code_reuse(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test execute_task queues code reuse task."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = TaskExecutionRequest(
                    binary_id=1,
                    task_type=TaskType.CODE_REUSE,
                    task_name="test-reuse",
                )
                result = await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == TaskType.CODE_REUSE.value
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_dangerous_functions(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test execute_task queues dangerous functions task."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = TaskExecutionRequest(
                    binary_id=1,
                    task_type=TaskType.DANGEROUS_FUNCTIONS,
                    task_name="test-dangerous",
                )
                result = await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == TaskType.DANGEROUS_FUNCTIONS.value
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_ml_training(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test execute_task queues ML training task."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = TaskExecutionRequest(
                    binary_id=1,
                    task_type=TaskType.ML_TRAINING,
                    task_name="test-training",
                    model_name="test-model",
                    ml_class_type="malware",
                )
                result = await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == TaskType.ML_TRAINING.value
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_ml_prediction(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test execute_task queues ML prediction task."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = TaskExecutionRequest(
                    binary_id=1,
                    task_type=TaskType.ML_PREDICTION,
                    task_name="test-prediction",
                    model_name="test-model",
                )
                result = await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == TaskType.ML_PREDICTION.value
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_similarity(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test execute_task queues similarity computation task."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = TaskExecutionRequest(
                    binary_id=1,
                    task_type=TaskType.SIMILARITY_COMPUTATION,
                    task_name="test-similarity",
                )
                result = await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == TaskType.SIMILARITY_COMPUTATION.value
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_binary_not_found(self, mock_background_tasks: Any, mock_current_user: Any) -> None:
        """Test execute_task returns 404 when binary not found."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=None)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = TaskExecutionRequest(
                binary_id=999,
                task_type=TaskType.CODE_REUSE,
                task_name="test-reuse",
            )
            with pytest.raises(HTTPException) as exc_info:
                await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_task_access_denied(self, mock_background_tasks: Any, mock_current_user: Any) -> None:
        """Test execute_task returns 403 for other user's binary."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        other_binary = MagicMock()
        other_binary.id = 1
        other_binary.uploaded_by = 999  # different user

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=other_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.CODE_REUSE,
                task_name="test-reuse",
            )
            with pytest.raises(HTTPException) as exc_info:
                await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_execute_task_ml_training_missing_model(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any) -> None:
        """Test execute_task returns 400 when model_name missing for ML training."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.ML_TRAINING,
                task_name="test-training",
            )
            with pytest.raises(HTTPException) as exc_info:
                await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_task_ml_training_missing_class_type(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any) -> None:
        """Test execute_task returns 400 when ml_class_type missing for ML training."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.ML_TRAINING,
                task_name="test-training",
                model_name="test-model",
            )
            with pytest.raises(HTTPException) as exc_info:
                await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_task_ml_prediction_missing_model(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any) -> None:
        """Test execute_task returns 400 when model_name missing for ML prediction."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest, TaskType

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.ML_PREDICTION,
                task_name="test-prediction",
            )
            with pytest.raises(HTTPException) as exc_info:
                await execute_task(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Endpoint: get_task_results
# ---------------------------------------------------------------------------

class TestGetTaskResults:
    """Tests for get_task_results endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_results_success(self, mock_current_user: Any) -> None:
        """Test get_task_results returns results for completed task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "completed"
            mock_tm.get_task_result.return_value = {"key": "value"}

            result = await get_task_results(
                task_uuid="test-uuid",
                current_user=mock_current_user,
            )
            assert result.data["task_uuid"] == "test-uuid"
            assert result.data["result"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_task_results_not_found(self, mock_current_user: Any) -> None:
        """Test get_task_results returns 404 for unknown task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "UUID Not Found"

            with pytest.raises(HTTPException) as exc_info:
                await get_task_results(
                    task_uuid="unknown-uuid",
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_results_no_result_completed(self, mock_current_user: Any) -> None:
        """Test get_task_results returns 404 when no result for completed task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "completed"
            mock_tm.get_task_result.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_task_results(
                    task_uuid="test-uuid",
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_results_processing(self, mock_current_user: Any) -> None:
        """Test get_task_results returns None result for processing task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "processing"
            mock_tm.get_task_result.return_value = None

            result = await get_task_results(
                task_uuid="test-uuid",
                current_user=mock_current_user,
            )
            assert result.data["status"] == "processing"


# ---------------------------------------------------------------------------
# Endpoint: get_task_status
# ---------------------------------------------------------------------------

class TestGetTaskStatus:
    """Tests for get_task_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, mock_current_user: Any) -> None:
        """Test get_task_status returns status for existing task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "processing"

            result = await get_task_status(
                task_uuid="test-uuid",
                current_user=mock_current_user,
            )
            assert result.data["task_uuid"] == "test-uuid"
            assert result.data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, mock_current_user: Any) -> None:
        """Test get_task_status returns 404 for unknown task."""
        with patch("app.api.v1.endpoints.tasks.TaskManager") as mock_tm:
            mock_tm.get_status.return_value = "UUID Not Found"

            with pytest.raises(HTTPException) as exc_info:
                await get_task_status(
                    task_uuid="unknown-uuid",
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint: start_similarity_computation
# ---------------------------------------------------------------------------

class TestStartSimilarityComputation:
    """Tests for start_similarity_computation endpoint."""

    @pytest.mark.asyncio
    async def test_start_similarity_success(self, mock_background_tasks: Any, mock_binary: Any, mock_current_user: Any, mock_tm: Any) -> None:
        """Test start_similarity_computation queues task successfully."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=mock_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with patch("app.api.v1.endpoints.tasks.capture_request_context", return_value=None):
                request = SimilarityComputationRequest(
                    binary_ids=[1, 2],
                    task_name="test-similarity",
                    match_threshold=0.7,
                )
                result = await start_similarity_computation(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
                assert result.data.task_type == "similarity_computation"
                mock_background_tasks.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_similarity_binary_not_found(self, mock_background_tasks: Any, mock_current_user: Any) -> None:
        """Test start_similarity returns 404 when binary not found."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=None)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = SimilarityComputationRequest(
                binary_ids=[999, 1000],
                task_name="test-similarity",
                match_threshold=0.7,
            )
            with pytest.raises(HTTPException) as exc_info:
                await start_similarity_computation(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_start_similarity_access_denied(self, mock_background_tasks: Any, mock_current_user: Any) -> None:
        """Test start_similarity returns 403 for other user's binary."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        other_binary = MagicMock()
        other_binary.id = 1
        other_binary.uploaded_by = 999

        mock_sql_util = MagicMock()
        mock_sql_util.get_binary = AsyncMock(return_value=other_binary)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            request = SimilarityComputationRequest(
                binary_ids=[1, 2],
                task_name="test-similarity",
                match_threshold=0.7,
            )
            with pytest.raises(HTTPException) as exc_info:
                await start_similarity_computation(
                    background_tasks=mock_background_tasks,
                    request_values=request,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Endpoint: list_similarity_computations
# ---------------------------------------------------------------------------

class TestListSimilarityComputations:
    """Tests for list_similarity_computations endpoint."""

    @pytest.mark.asyncio
    async def test_list_similarity_computations_success(self, mock_current_user: Any) -> None:
        """Test list_similarity_computations returns computations."""
        mock_computation = MagicMock()
        mock_computation.id = 1
        mock_computation.task_name = "test-comp"
        mock_computation.binary_count = 3
        mock_computation.total_comparisons = 3
        mock_computation.status = "completed"
        mock_computation.created_at = None

        mock_sql_util = MagicMock()
        mock_sql_util.list_similarity_computations = AsyncMock(return_value=[mock_computation])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_similarity_computations(
                current_user=mock_current_user,
            )
            assert len(result.data) == 1
            assert result.data[0]["task_name"] == "test-comp"

    @pytest.mark.asyncio
    async def test_list_similarity_computations_empty(self, mock_current_user: Any) -> None:
        """Test list_similarity_computations returns empty list."""
        mock_sql_util = MagicMock()
        mock_sql_util.list_similarity_computations = AsyncMock(return_value=[])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_similarity_computations(
                current_user=mock_current_user,
            )
            assert result.data == []

    @pytest.mark.asyncio
    async def test_list_similarity_computations_with_timestamp(self, mock_current_user: Any) -> None:
        """Test list_similarity_computations includes created_at timestamp."""
        from datetime import datetime

        mock_computation = MagicMock()
        mock_computation.id = 1
        mock_computation.task_name = "test-comp"
        mock_computation.binary_count = 2
        mock_computation.total_comparisons = 1
        mock_computation.status = "completed"
        mock_computation.created_at = datetime(2024, 1, 1, 12, 0, 0)

        mock_sql_util = MagicMock()
        mock_sql_util.list_similarity_computations = AsyncMock(return_value=[mock_computation])

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await list_similarity_computations(
                current_user=mock_current_user,
            )
            assert result.data[0]["created_at"] == "2024-01-01T12:00:00"


# ---------------------------------------------------------------------------
# Endpoint: get_similarity_computation
# ---------------------------------------------------------------------------

class TestGetSimilarityComputation:
    """Tests for get_similarity_computation endpoint."""

    @pytest.mark.asyncio
    async def test_get_similarity_computation_success(self, mock_current_user: Any) -> None:
        """Test get_similarity_computation returns computation detail."""
        mock_pair = MagicMock()
        mock_pair.binary_a_id = 1
        mock_pair.binary_b_id = 2
        mock_pair.overall_similarity = 0.85
        mock_pair.matched_function_count = 10
        mock_pair.total_function_comparisons = 20

        mock_computation = MagicMock()
        mock_computation.id = 1
        mock_computation.task_name = "test-comp"
        mock_computation.binary_count = 2
        mock_computation.total_comparisons = 1
        mock_computation.status = "completed"
        mock_computation.computed_by = 1  # matches current user
        mock_computation.pairs = [mock_pair]

        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.get_binary_name = AsyncMock(return_value="test.elf")

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await get_similarity_computation(
                computation_id=1,
                current_user=mock_current_user,
            )
            assert result.data.computation_id == 1
            assert len(result.data.matrix) == 1

    @pytest.mark.asyncio
    async def test_get_similarity_computation_not_found(self, mock_current_user: Any) -> None:
        """Test get_similarity_computation returns 404 when not found."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=None)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await get_similarity_computation(
                    computation_id=999,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_similarity_computation_access_denied(self, mock_current_user: Any) -> None:
        """Test get_similarity_computation returns 403 for other user's computation."""
        mock_computation = MagicMock()
        mock_computation.computed_by = 999  # different user

        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=mock_computation)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await get_similarity_computation(
                    computation_id=1,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_similarity_computation_fallback_names(self, mock_current_user: Any) -> None:
        """Test get_similarity_computation uses fallback names when binary_name is None."""
        mock_pair = MagicMock()
        mock_pair.binary_a_id = 1
        mock_pair.binary_b_id = 2
        mock_pair.overall_similarity = 0.5
        mock_pair.matched_function_count = 5
        mock_pair.total_function_comparisons = 10

        mock_computation = MagicMock()
        mock_computation.id = 1
        mock_computation.task_name = "test-comp"
        mock_computation.binary_count = 2
        mock_computation.total_comparisons = 1
        mock_computation.status = "completed"
        mock_computation.computed_by = 1
        mock_computation.pairs = [mock_pair]

        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.get_binary_name = AsyncMock(return_value=None)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await get_similarity_computation(
                computation_id=1,
                current_user=mock_current_user,
            )
            assert result.data.matrix[0].binary_a_name == "binary_1"
            assert result.data.matrix[0].binary_b_name == "binary_2"


# ---------------------------------------------------------------------------
# Endpoint: delete_similarity_computation
# ---------------------------------------------------------------------------

class TestDeleteSimilarityComputation:
    """Tests for delete_similarity_computation endpoint."""

    @pytest.mark.asyncio
    async def test_delete_similarity_computation_success(self, mock_current_user: Any) -> None:
        """Test delete_similarity_computation succeeds."""
        mock_computation = MagicMock()
        mock_computation.id = 1
        mock_computation.computed_by = 1  # matches current user

        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=mock_computation)
        mock_sql_util.delete_similarity_computation = AsyncMock()

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            result = await delete_similarity_computation(
                computation_id=1,
                current_user=mock_current_user,
            )
            assert result.message == "Similarity computation deleted"
            mock_sql_util.delete_similarity_computation.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_similarity_computation_not_found(self, mock_current_user: Any) -> None:
        """Test delete_similarity_computation returns 404 when not found."""
        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=None)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await delete_similarity_computation(
                    computation_id=999,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_similarity_computation_access_denied(self, mock_current_user: Any) -> None:
        """Test delete_similarity_computation returns 403 for other user's computation."""
        mock_computation = MagicMock()
        mock_computation.computed_by = 999  # different user

        mock_sql_util = MagicMock()
        mock_sql_util.get_similarity_computation = AsyncMock(return_value=mock_computation)

        with patch("app.database.sql_service.SQLUtil", mock_sql_util):
            with pytest.raises(HTTPException) as exc_info:
                await delete_similarity_computation(
                    computation_id=1,
                    current_user=mock_current_user,
                )
            assert exc_info.value.status_code == 403
