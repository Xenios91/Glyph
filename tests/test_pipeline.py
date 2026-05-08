"""Tests for pipeline orchestration."""

from typing import Any, Optional

import pytest

from app.processing.pipeline import PipelineContext, PipelineStep, ProcessingPipeline


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_init_minimal(self) -> None:
        """Test minimal initialization."""
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        assert ctx.uuid == "test-uuid"
        assert ctx.binary_path == "/test/binary"
        assert ctx.pipeline_type == "generic"
        assert ctx.metadata == {}
        assert ctx.data == {}
        assert ctx.status == "starting"
        assert ctx.error is None

    def test_init_full(self) -> None:
        """Test full initialization."""
        ctx = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            pipeline_type="ml_training",
            metadata={"model_name": "test_model"},
            data={"key": "value"},
            status="running",
            error="test error",
        )
        assert ctx.pipeline_type == "ml_training"
        assert ctx.metadata == {"model_name": "test_model"}
        assert ctx.data == {"key": "value"}
        assert ctx.status == "running"
        assert ctx.error == "test error"

    def test_get_existing_key(self) -> None:
        """Test getting an existing key."""
        ctx = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={"key": "value"},
        )
        assert ctx.get("key") == "value"

    def test_get_missing_key_default(self) -> None:
        """Test getting a missing key returns default."""
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        assert ctx.get("missing") is None
        assert ctx.get("missing", "fallback") == "fallback"

    def test_set_key(self) -> None:
        """Test setting a key."""
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        ctx.set("key", "value")
        assert ctx.data["key"] == "value"

    def test_get_and_set_roundtrip(self) -> None:
        """Test get/set roundtrip."""
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        ctx.set("test_key", {"nested": "value"})
        result = ctx.get("test_key")
        assert result == {"nested": "value"}


class _MockStep(PipelineStep):
    """A mock pipeline step for testing."""

    def __init__(self, name: str, set_error: bool = False, raise_error: bool = False, data_to_set: Optional[dict[str, Any]] = None) -> None:
        self._name = name
        self._set_error = set_error
        self._raise_error = raise_error
        self._data_to_set = data_to_set or {}
        self._executed = False

    async def execute(self, context: PipelineContext) -> PipelineContext:
        self._executed = True
        if self._raise_error:
            raise RuntimeError(f"Step {self._name} failed")
        if self._set_error:
            context.error = f"Error in {self._name}"
            context.status = "error"
        for key, value in self._data_to_set.items():
            context.set(key, value)
        return context

    def get_name(self) -> str:
        return self._name


class TestPipelineStep:
    """Tests for PipelineStep abstract base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Test that PipelineStep cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PipelineStep()  # pyright: ignore[reportAbstractUsage]

    def test_mock_step_name(self) -> None:
        """Test that mock step returns correct name."""
        step = _MockStep("TestStep")
        assert step.get_name() == "TestStep"

    def test_mock_step_description(self) -> None:
        """Test default description."""
        step = _MockStep("TestStep")
        assert step.get_description() == "TestStep step"


class TestProcessingPipeline:
    """Tests for ProcessingPipeline orchestration."""

    def test_init(self) -> None:
        """Test pipeline initialization."""
        steps = [_MockStep("Step1"), _MockStep("Step2")]
        pipeline = ProcessingPipeline("test_pipeline", steps)  # pyright: ignore[reportArgumentType]
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.steps) == 2

    @pytest.mark.asyncio
    async def test_execute_empty_pipeline(self) -> None:
        """Test executing a pipeline with no steps."""
        pipeline = ProcessingPipeline("empty", [])
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)
        assert result.status == "complete"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_single_step_success(self) -> None:
        """Test executing a pipeline with a single successful step."""
        step = _MockStep("Step1", data_to_set={"result": "success"})
        pipeline = ProcessingPipeline("single", [step])  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)
        assert result.status == "complete"
        assert result.get("result") == "success"
        assert step._executed is True  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_execute_multiple_steps_success(self) -> None:
        """Test executing a pipeline with multiple successful steps."""
        steps = [
            _MockStep("Step1", data_to_set={"step1": True}),
            _MockStep("Step2", data_to_set={"step2": True}),
            _MockStep("Step3", data_to_set={"step3": True}),
        ]
        pipeline = ProcessingPipeline("multi", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)

        assert result.status == "complete"
        assert result.get("step1") is True
        assert result.get("step2") is True
        assert result.get("step3") is True
        for step in steps:
            assert step._executed is True  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_execute_step_sets_error(self) -> None:
        """Test that pipeline stops when a step sets an error."""
        steps = [
            _MockStep("Step1", data_to_set={"step1": True}),
            _MockStep("Step2", set_error=True),
            _MockStep("Step3", data_to_set={"step3": True}),
        ]
        pipeline = ProcessingPipeline("error", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)

        assert result.status == "error"
        assert result.error is not None
        assert result.get("step1") is True
        # Step3 should not have been executed
        assert steps[2]._executed is False  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_execute_step_raises_exception(self) -> None:
        """Test that pipeline stops when a step raises an exception."""
        steps = [
            _MockStep("Step1", data_to_set={"step1": True}),
            _MockStep("Step2", raise_error=True),
            _MockStep("Step3", data_to_set={"step3": True}),
        ]
        pipeline = ProcessingPipeline("exception", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)

        assert result.status == "error"
        assert result.error is not None
        assert "Step2 failed" in result.error
        assert result.get("step1") is True
        # Step3 should not have been executed
        assert steps[2]._executed is False  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_execute_preserves_context_uuid(self) -> None:
        """Test that context UUID is preserved through pipeline."""
        steps = [_MockStep("Step1"), _MockStep("Step2")]
        pipeline = ProcessingPipeline("preserve", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="my-uuid-123", binary_path="/test/binary")
        result = await pipeline.execute(ctx)
        assert result.uuid == "my-uuid-123"

    @pytest.mark.asyncio
    async def test_execute_data_flows_between_steps(self) -> None:
        """Test that data set by one step is available to the next."""
        steps = [
            _MockStep("Step1", data_to_set={"shared": "value"}),
            _MockStep("Step2"),
        ]
        pipeline = ProcessingPipeline("flow", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)
        assert result.get("shared") == "value"

    @pytest.mark.asyncio
    async def test_execute_sets_exc_info_on_exception(self) -> None:
        """Test that exc_info is set when a step raises."""
        steps = [_MockStep("Step1", raise_error=True)]
        pipeline = ProcessingPipeline("exc_info", steps)  # pyright: ignore[reportArgumentType]
        ctx = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = await pipeline.execute(ctx)
        assert result.exc_info is not False
        assert result.status == "error"
