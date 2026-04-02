"""Tests for the processing pipeline module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.processing.pipeline import (
    PipelineStepStatus,
    PipelineContext,
    PipelineStep,
    PipelineStepError,
    ProcessingPipeline,
)


class TestPipelineStepStatus:
    """Tests for PipelineStepStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert PipelineStepStatus.PENDING.value == "pending"
        assert PipelineStepStatus.RUNNING.value == "running"
        assert PipelineStepStatus.COMPLETED.value == "completed"
        assert PipelineStepStatus.FAILED.value == "failed"
        assert PipelineStepStatus.SKIPPED.value == "skipped"


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_context_creation_minimal(self):
        """Test creating context with minimal required fields."""
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )
        assert context.binary_path == "/test/binary"
        assert context.model_name == "test_model"
        assert context.task_name == "test_task"
        assert context.is_training is True
        assert context.data == {}
        assert context.status == "pending"
        assert context.error is None
        assert context.started_at is None
        assert context.completed_at is None

    def test_context_creation_with_data(self):
        """Test creating context with additional data."""
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=False,
            data={"key": "value"},
            status="running",
            error="test error",
        )
        assert context.data == {"key": "value"}
        assert context.status == "running"
        assert context.error == "test error"


class TestPipelineStep:
    """Tests for PipelineStep abstract base class."""

    def test_abstract_base_class(self):
        """Test that PipelineStep is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            PipelineStep()

    def test_default_validate_returns_true(self):
        """Test that default validate method returns True."""
        # Create a concrete implementation
        class TestStep(PipelineStep):
            name = "TestStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        step = TestStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )
        assert step.validate(context) is True


class TestPipelineStepError:
    """Tests for PipelineStepError exception."""

    def test_error_creation(self):
        """Test creating PipelineStepError."""
        error = PipelineStepError("TestStep", "Test error message")
        assert error.step_name == "TestStep"
        assert error.message == "Test error message"
        assert "TestStep: Test error message" in str(error)

    def test_error_inheritance(self):
        """Test that PipelineStepError inherits from Exception."""
        assert issubclass(PipelineStepError, Exception)


class TestProcessingPipeline:
    """Tests for ProcessingPipeline class."""

    def test_pipeline_creation_empty(self):
        """Test creating pipeline with no steps."""
        pipeline = ProcessingPipeline()
        assert pipeline.steps == []

    def test_pipeline_creation_with_steps(self):
        """Test creating pipeline with steps."""

        class TestStep(PipelineStep):
            name = "TestStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        step = TestStep()
        pipeline = ProcessingPipeline(steps=[step])
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0] is step

    def test_add_step(self):
        """Test adding a step to pipeline."""

        class TestStep(PipelineStep):
            name = "TestStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        pipeline = ProcessingPipeline()
        step = TestStep()
        result = pipeline.add_step(step)

        assert len(pipeline.steps) == 1
        assert pipeline.steps[0] is step
        assert result is pipeline  # Returns self for chaining

    def test_add_step_chaining(self):
        """Test that add_step supports method chaining."""

        class TestStep(PipelineStep):
            def __init__(self, name):
                self.name = name

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        pipeline = (
            ProcessingPipeline()
            .add_step(TestStep("Step1"))
            .add_step(TestStep("Step2"))
            .add_step(TestStep("Step3"))
        )

        assert len(pipeline.steps) == 3
        assert pipeline.steps[0].name == "Step1"
        assert pipeline.steps[1].name == "Step2"
        assert pipeline.steps[2].name == "Step3"

    def test_process_empty_pipeline(self):
        """Test processing with empty pipeline."""
        pipeline = ProcessingPipeline()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = pipeline.process(context)

        assert result.status == "completed"
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.error is None

    def test_process_successful_steps(self):
        """Test processing with successful steps."""

        class CounterStep(PipelineStep):
            def __init__(self, name, increment):
                self.name = name
                self.increment = increment

            def process(self, context: PipelineContext) -> PipelineContext:
                context.data["count"] = context.data.get("count", 0) + self.increment
                return context

        pipeline = ProcessingPipeline()
        pipeline.add_step(CounterStep("Step1", 1))
        pipeline.add_step(CounterStep("Step2", 2))
        pipeline.add_step(CounterStep("Step3", 3))

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = pipeline.process(context)

        assert result.status == "completed"
        assert result.data["count"] == 6  # 1 + 2 + 3

    def test_process_step_failure(self):
        """Test processing when a step fails."""

        class FailingStep(PipelineStep):
            name = "FailingStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                raise PipelineStepError(self.name, "Step failed")

        class SuccessStep(PipelineStep):
            name = "SuccessStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                context.data["success"] = True
                return context

        pipeline = ProcessingPipeline()
        pipeline.add_step(SuccessStep())
        pipeline.add_step(FailingStep())
        pipeline.add_step(SuccessStep())  # Should not be executed

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = pipeline.process(context)

        assert result.status == "failed"
        assert "FailingStep: Step failed" in result.error
        assert result.data.get("success") is True  # First step executed
        assert result.completed_at is not None

    def test_process_step_skip_on_validation_failure(self):
        """Test that steps are skipped when validation fails."""

        class ConditionalStep(PipelineStep):
            def __init__(self, name, should_skip):
                self.name = name
                self.should_skip = should_skip

            def validate(self, context: PipelineContext) -> bool:
                return not self.should_skip

            def process(self, context: PipelineContext) -> PipelineContext:
                context.data["executed"] = True
                return context

        pipeline = ProcessingPipeline()
        pipeline.add_step(ConditionalStep("Step1", False))  # Should execute
        pipeline.add_step(ConditionalStep("Step2", True))  # Should skip
        pipeline.add_step(ConditionalStep("Step3", False))  # Should execute

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
            data={"executed": False},
        )

        result = pipeline.process(context)

        assert result.status == "completed"
        assert result.data["executed"] is True  # Steps 1 and 3 executed

    def test_process_sets_timestamps(self):
        """Test that processing sets started_at and completed_at timestamps."""
        pipeline = ProcessingPipeline()

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = pipeline.process(context)

        assert isinstance(result.started_at, datetime)
        assert isinstance(result.completed_at, datetime)
        assert result.started_at <= result.completed_at

    def test_process_status_transitions(self):
        """Test that status transitions correctly during processing."""

        class TrackingStep(PipelineStep):
            name = "TrackingStep"

            def process(self, context: PipelineContext) -> PipelineContext:
                context.data["status_during_process"] = context.status
                return context

        pipeline = ProcessingPipeline()
        pipeline.add_step(TrackingStep())

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = pipeline.process(context)

        # Status should be "running" during step execution
        assert result.data["status_during_process"] == "running"
        # Final status should be "completed"
        assert result.status == "completed"
