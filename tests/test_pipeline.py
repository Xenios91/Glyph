"""Tests for the pipeline framework.

This module contains tests for the ProcessingPipeline class and PipelineContext.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.processing.pipeline import (
    PipelineContext,
    PipelineStep,
    ProcessingPipeline,
)


class MockStep(PipelineStep):
    """Mock step for testing."""

    def __init__(
        self,
        name: str,
        set_key: str | None = None,
        set_value: str | None = None,
        fail: bool = False,
    ) -> None:
        self._name = name
        self._set_key = set_key
        self._set_value = set_value
        self._fail = fail

    def get_name(self) -> str:
        return self._name

    def execute(self, context: PipelineContext) -> PipelineContext:
        if self._fail:
            context.error = f"Step {self._name} failed"
            return context
        if self._set_key is not None:
            context.set(self._set_key, self._set_value)
        return context


class TestPipelineContext:
    """Tests for PipelineContext."""

    def test_create_context(self):
        """Test creating a basic context."""
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        assert context.uuid == "test-uuid"
        assert context.binary_path == "/test/binary"
        assert context.pipeline_type == "generic"
        assert context.status == "starting"
        assert context.error is None

    def test_context_set_and_get(self):
        """Test setting and getting values in context."""
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        context.set("key1", "value1")
        context.set("key2", 123)
        assert context.get("key1") == "value1"
        assert context.get("key2") == 123

    def test_context_get_default(self):
        """Test getting a value with default."""
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        assert context.get("nonexistent", "default") == "default"
        assert context.get("nonexistent") is None

    def test_context_metadata(self):
        """Test metadata dictionary."""
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"}
        )
        assert context.metadata["model_name"] == "test_model"


class TestPipelineStep:
    """Tests for PipelineStep abstract base class."""

    def test_step_must_implement_execute(self):
        """Test that PipelineStep requires execute method."""
        # PipelineStep is abstract and cannot be instantiated directly
        # This is verified by the ABC mechanism
        assert hasattr(PipelineStep, '__abstractmethods__')
        assert 'execute' in PipelineStep.__abstractmethods__

    def test_step_must_implement_get_name(self):
        """Test that PipelineStep requires get_name method."""
        # PipelineStep is abstract and cannot be instantiated directly
        assert hasattr(PipelineStep, '__abstractmethods__')
        assert 'get_name' in PipelineStep.__abstractmethods__


class TestProcessingPipeline:
    """Tests for ProcessingPipeline class."""

    def test_create_pipeline(self):
        """Test creating a pipeline with steps."""
        steps = [MockStep("Step1"), MockStep("Step2")]
        pipeline = ProcessingPipeline("Test Pipeline", steps)
        assert pipeline.name == "Test Pipeline"
        assert len(pipeline.steps) == 2

    def test_execute_pipeline(self):
        """Test executing a pipeline."""
        steps = [
            MockStep("Step1", set_key="key1", set_value="value1"),
            MockStep("Step2", set_key="key2", set_value="value2"),
        ]
        pipeline = ProcessingPipeline("Test Pipeline", steps)
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = pipeline.execute(context)

        assert result.status == "complete"
        assert result.get("key1") == "value1"
        assert result.get("key2") == "value2"

    def test_execute_pipeline_with_error(self):
        """Test pipeline execution with a failing step."""
        steps = [
            MockStep("Step1", set_key="key1", set_value="value1"),
            MockStep("Step2", fail=True),
            MockStep("Step3", set_key="key3", set_value="value3"),
        ]
        pipeline = ProcessingPipeline("Test Pipeline", steps)
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = pipeline.execute(context)

        assert result.status == "error"
        assert result.error is not None
        assert result.get("key1") == "value1"
        assert result.get("key3") is None  # Step3 should not have run


class TestPipelineIntegration:
    """Integration tests for the pipeline framework."""

    def test_empty_pipeline(self):
        """Test executing an empty pipeline."""
        pipeline = ProcessingPipeline("Empty Pipeline", [])
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = pipeline.execute(context)
        assert result.status == "complete"

    def test_single_step_pipeline(self):
        """Test executing a single-step pipeline."""
        pipeline = ProcessingPipeline("Single Step", [
            MockStep("Step1", set_key="result", set_value="done")
        ])
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = pipeline.execute(context)
        assert result.status == "complete"
        assert result.get("result") == "done"

    def test_pipeline_with_exception(self):
        """Test pipeline handling of exceptions."""

        class FailingStep(PipelineStep):
            def get_name(self) -> str:
                return "FailingStep"

            def execute(self, context: PipelineContext) -> PipelineContext:
                raise ValueError("Test exception")

        pipeline = ProcessingPipeline("Failing Pipeline", [FailingStep()])
        context = PipelineContext(uuid="test-uuid", binary_path="/test/binary")
        result = pipeline.execute(context)

        assert result.status == "error"
        assert result.error is not None
        assert "Test exception" in str(result.error)
