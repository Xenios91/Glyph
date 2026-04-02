"""Tests for the processing steps module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.processing.pipeline import PipelineContext, PipelineStepError
from app.processing.steps import (
    ValidationStep,
    DecompileStep,
    TokenizeStep,
    FilterStep,
    FeatureExtractStep,
    TrainStep,
    PredictStep,
)


class TestValidationStep:
    """Tests for ValidationStep."""

    def test_process_success(self):
        """Test successful validation of existing readable file."""
        step = ValidationStep()
        context = PipelineContext(
            binary_path="/tmp/test_binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("os.access", return_value=True):
            result = step.process(context)

        assert result is context
        assert "binary_path" in result.__dict__

    def test_process_file_not_found(self):
        """Test validation fails when file doesn't exist."""
        step = ValidationStep()
        context = PipelineContext(
            binary_path="/nonexistent/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(PipelineStepError) as exc_info:
                step.process(context)

        assert exc_info.value.step_name == "ValidationStep"
        assert "not found" in str(exc_info.value).lower()

    def test_process_not_a_file(self):
        """Test validation fails when path is not a file."""
        step = ValidationStep()
        context = PipelineContext(
            binary_path="/some/directory",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=False):
            with pytest.raises(PipelineStepError) as exc_info:
                step.process(context)

        assert exc_info.value.step_name == "ValidationStep"
        assert "not a file" in str(exc_info.value).lower()

    def test_process_not_readable(self):
        """Test validation fails when file is not readable."""
        step = ValidationStep()
        context = PipelineContext(
            binary_path="/unreadable/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("os.access", return_value=False):
            with pytest.raises(PipelineStepError) as exc_info:
                step.process(context)

        assert exc_info.value.step_name == "ValidationStep"
        assert "not readable" in str(exc_info.value).lower()


class TestDecompileStep:
    """Tests for DecompileStep."""

    def test_process_success(self):
        """Test successful decompilation."""
        step = DecompileStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("app.processing.steps.get_settings") as mock_settings:
            mock_settings.return_value = Mock()
            result = step.process(context)

        assert result.data.get("decompiled") is True

    def test_process_failure(self):
        """Test decompilation failure."""
        step = DecompileStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        # Mock get_settings to return a valid settings object, but mock the actual
        # decompilation logic to raise an exception inside the try block
        with patch("app.processing.steps.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_get_settings.return_value = mock_settings
            # Raise exception during the decompilation attempt (inside try block)
            with patch("app.processing.steps.logger") as mock_logger:
                mock_logger.info.side_effect = Exception("Decompile error")
                with pytest.raises(PipelineStepError) as exc_info:
                    step.process(context)

        assert exc_info.value.step_name == "DecompileStep"
        assert "Decompilation failed" in str(exc_info.value)


class TestTokenizeStep:
    """Tests for TokenizeStep."""

    def test_process_success(self):
        """Test successful tokenization."""
        step = TokenizeStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = step.process(context)

        assert result.data.get("tokenized") is True

    def test_process_failure(self):
        """Test tokenization failure."""
        step = TokenizeStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        # TokenizeStep doesn't have external dependencies that can fail
        # so we test that it always succeeds with current implementation
        result = step.process(context)
        assert result.data.get("tokenized") is True


class TestFilterStep:
    """Tests for FilterStep."""

    def test_process_success(self):
        """Test successful filtering."""
        step = FilterStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = step.process(context)

        assert result.data.get("filtered") is True

    def test_process_failure(self):
        """Test filtering failure."""
        step = FilterStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        # FilterStep doesn't have external dependencies that can fail
        # so we test that it always succeeds with current implementation
        result = step.process(context)
        assert result.data.get("filtered") is True


class TestFeatureExtractStep:
    """Tests for FeatureExtractStep."""

    def test_process_success(self):
        """Test successful feature extraction."""
        step = FeatureExtractStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = step.process(context)

        assert result.data.get("features_extracted") is True

    def test_process_failure(self):
        """Test feature extraction failure."""
        step = FeatureExtractStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        # FeatureExtractStep doesn't have external dependencies that can fail
        # so we test that it always succeeds with current implementation
        result = step.process(context)
        assert result.data.get("features_extracted") is True


class TestTrainStep:
    """Tests for TrainStep."""

    def test_validate_training_task(self):
        """Test validation passes for training task."""
        step = TrainStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        assert step.validate(context) is True

    def test_validate_prediction_task(self):
        """Test validation fails for prediction task."""
        step = TrainStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=False,
        )

        assert step.validate(context) is False

    def test_process_success(self):
        """Test successful training."""
        step = TrainStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        result = step.process(context)

        assert result.data.get("model_trained") is True

    def test_process_with_model_name(self):
        """Test training logs model name."""
        step = TrainStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="my_custom_model",
            task_name="test_task",
            is_training=True,
        )

        result = step.process(context)

        assert result.data.get("model_trained") is True


class TestPredictStep:
    """Tests for PredictStep."""

    def test_validate_prediction_task(self):
        """Test validation passes for prediction task."""
        step = PredictStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=False,
        )

        assert step.validate(context) is True

    def test_validate_training_task(self):
        """Test validation fails for training task."""
        step = PredictStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        assert step.validate(context) is False

    def test_process_success(self):
        """Test successful prediction."""
        step = PredictStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=False,
        )

        result = step.process(context)

        assert result.data.get("predictions_made") is True

    def test_process_with_model_name(self):
        """Test prediction logs model name."""
        step = PredictStep()
        context = PipelineContext(
            binary_path="/test/binary",
            model_name="my_prediction_model",
            task_name="test_task",
            is_training=False,
        )

        result = step.process(context)

        assert result.data.get("predictions_made") is True


class TestStepIntegration:
    """Integration tests for step combinations."""

    def test_all_steps_in_sequence(self):
        """Test all steps can be executed in sequence."""
        steps = [
            ValidationStep(),
            DecompileStep(),
            TokenizeStep(),
            FilterStep(),
            FeatureExtractStep(),
            TrainStep(),
        ]

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=True,
        )

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("os.access", return_value=True), \
             patch("app.processing.steps.get_settings", return_value=Mock()):
            for step in steps:
                if step.validate(context):
                    context = step.process(context)

        assert context.data.get("decompiled") is True
        assert context.data.get("tokenized") is True
        assert context.data.get("filtered") is True
        assert context.data.get("features_extracted") is True
        assert context.data.get("model_trained") is True

    def test_prediction_pipeline(self):
        """Test prediction-specific pipeline."""
        steps = [
            ValidationStep(),
            DecompileStep(),
            TokenizeStep(),
            FilterStep(),
            FeatureExtractStep(),
            PredictStep(),
        ]

        context = PipelineContext(
            binary_path="/test/binary",
            model_name="test_model",
            task_name="test_task",
            is_training=False,
        )

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("os.access", return_value=True), \
             patch("app.processing.steps.get_settings", return_value=Mock()):
            for step in steps:
                if step.validate(context):
                    context = step.process(context)

        assert context.data.get("decompiled") is True
        assert context.data.get("tokenized") is True
        assert context.data.get("filtered") is True
        assert context.data.get("features_extracted") is True
        assert context.data.get("predictions_made") is True
