"""Tests for pipeline step implementations.

This module contains tests for the individual pipeline steps.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.processing.pipeline import PipelineContext
from app.processing.steps import (
    ValidationStep,
    DecompileStep,
    TokenizeStep,
    FilterStep,
    FeatureExtractStep,
    TrainStep,
    PredictStep,
    _filter_tokens,
    _remove_comments,
    _check_if_variable,
)


class TestTokenFilteringUtilities:
    """Tests for token filtering utility functions."""

    def test_check_if_variable_var_pattern(self):
        """Test variable detection for var patterns."""
        assert _check_if_variable("var1") is True
        assert _check_if_variable("var123") is True

    def test_check_if_variable_local_pattern(self):
        """Test variable detection for local patterns."""
        assert _check_if_variable("local_10") is True
        assert _check_if_variable("local_ABC") is True

    def test_check_if_variable_param_pattern(self):
        """Test variable detection for param patterns."""
        assert _check_if_variable("param_0") is True
        assert _check_if_variable("param_1") is True

    def test_check_if_variable_not_variable(self):
        """Test that non-variables are not detected."""
        assert _check_if_variable("main") is False
        assert _check_if_variable("printf") is False
        assert _check_if_variable("myFunction") is False

    def test_remove_comments_single_line(self):
        """Test removing single-line comments.
        
        Note: _remove_comments only handles multi-line /* */ comments, not // comments.
        """
        # The _remove_comments function only handles /* */ style comments
        # Single-line // comments are not removed
        tokens = ["int", "x", "//", "this", "is", "a", "comment"]
        result = _remove_comments(tokens)
        # Single-line comments are preserved as-is
        assert result == ["int", "x", "//", "this", "is", "a", "comment"]

    def test_remove_comments_multi_line(self):
        """Test removing multi-line comments."""
        tokens = ["int", "x", "/*", "multi", "line", "comment", "*/", ";"]
        result = _remove_comments(tokens)
        assert "/*" not in result
        assert "*/" not in result
        assert "multi" not in result

    def test_filter_tokens_hex_address(self):
        """Test filtering hex addresses."""
        tokens = ["0x401000", "0x8048000"]
        result = _filter_tokens(tokens)
        assert result == ["HEX", "HEX"]

    def test_filter_tokens_function_name(self):
        """Test filtering function names."""
        tokens = ["FUN_00401000", "FUN_00402000"]
        result = _filter_tokens(tokens)
        assert result == ["FUNCTION", "FUNCTION"]

    def test_filter_tokens_variable(self):
        """Test filtering variables."""
        tokens = ["var1", "local_10", "param_0"]
        result = _filter_tokens(tokens)
        assert result == ["VARIABLE", "VARIABLE", "VARIABLE"]

    def test_filter_tokens_undefined(self):
        """Test filtering undefined types."""
        tokens = ["undefined4", "undefined8"]
        result = _filter_tokens(tokens)
        assert result == ["undefined", "undefined"]

    def test_filter_tokens_preserves_keywords(self):
        """Test that keywords are preserved."""
        tokens = ["int", "return", "if", "while"]
        result = _filter_tokens(tokens)
        assert result == ["int", "return", "if", "while"]


class TestValidationStep:
    """Tests for ValidationStep."""

    def test_get_name(self):
        """Test step name."""
        step = ValidationStep()
        assert step.get_name() == "ValidationStep"

    @pytest.mark.asyncio
    async def test_execute_valid_file(self):
        """Test validation with a valid file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            step = ValidationStep()
            context = PipelineContext(
                uuid="test-uuid",
                binary_path=temp_path,
            )
            result = await step.execute(context)
            assert result.error is None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_nonexistent_file(self):
        """Test validation with a nonexistent file."""
        step = ValidationStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/nonexistent/file",
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_empty_file(self):
        """Test validation with an empty file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            step = ValidationStep()
            context = PipelineContext(
                uuid="test-uuid",
                binary_path=temp_path,
            )
            result = await step.execute(context)
            assert result.error is not None
            assert "empty" in result.error
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_max_size(self):
        """Test validation with max size limit."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 1024 * 1024)  # 1 MB file
            temp_path = f.name

        try:
            step = ValidationStep(max_size_mb=0.5)  # 0.5 MB limit
            context = PipelineContext(
                uuid="test-uuid",
                binary_path=temp_path,
            )
            result = await step.execute(context)
            assert result.error is not None
            assert "exceeds" in result.error
        finally:
            os.unlink(temp_path)


class TestDecompileStep:
    """Tests for DecompileStep."""

    def test_get_name(self):
        """Test step name."""
        step = DecompileStep()
        assert step.get_name() == "DecompileStep"

    @patch("app.processing.ghidra_processor.analyze_binary_and_decompile")
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_analyze):
        """Test successful decompilation."""
        mock_analyze.return_value = {
            "functions": [{"name": "test"}],
            "erroredFunctions": [],
        }

        step = DecompileStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is None
        assert result.get("functions") == [{"name": "test"}]

    @patch("app.processing.ghidra_processor.analyze_binary_and_decompile")
    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_analyze):
        """Test failed decompilation."""
        mock_analyze.side_effect = Exception("Ghidra error")

        step = DecompileStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None
        assert "Decompilation failed" in result.error


class TestTokenizeStep:
    """Tests for TokenizeStep."""

    def test_get_name(self):
        """Test step name."""
        step = TokenizeStep()
        assert step.get_name() == "TokenizeStep"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful tokenization."""
        step = TokenizeStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "functions": [
                    {"name": "func1", "tokenList": ["int", "x", ";"]},
                    {"name": "func2", "tokenList": ["return", "0", ";"]},
                ]
            },
        )
        result = await step.execute(context)

        assert result.error is None
        tokenized = result.get("tokenized_functions")
        assert len(tokenized) == 2
        assert tokenized[0]["tokens"] == "int x ;"
        assert tokenized[1]["tokens"] == "return 0 ;"

    @pytest.mark.asyncio
    async def test_execute_no_functions(self):
        """Test tokenization with no functions."""
        step = TokenizeStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None
        assert "decompilation" in result.error


class TestFilterStep:
    """Tests for FilterStep."""

    def test_get_name(self):
        """Test step name."""
        step = FilterStep()
        assert step.get_name() == "FilterStep"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful filtering."""
        step = FilterStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "tokenized_functions": [
                    {
                        "name": "func1",
                        "tokenList": ["0x401000", "FUN_00401000", "var1", "int"],
                    },
                ]
            },
        )
        result = await step.execute(context)

        assert result.error is None
        filtered = result.get("filtered_functions")
        assert len(filtered) == 1
        assert filtered[0]["tokenList"] == ["HEX", "FUNCTION", "VARIABLE", "int"]

    @pytest.mark.asyncio
    async def test_execute_no_tokenized_functions(self):
        """Test filtering with no tokenized functions."""
        step = FilterStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None


class TestFeatureExtractStep:
    """Tests for FeatureExtractStep."""

    def test_get_name(self):
        """Test step name."""
        step = FeatureExtractStep()
        assert step.get_name() == "FeatureExtractStep"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful feature extraction."""
        step = FeatureExtractStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x return 0"},
                    {"name": "func2", "tokens": "void y return 1"},
                ]
            },
        )
        result = await step.execute(context)

        assert result.error is None
        tokens = result.get("tokens")
        assert tokens is not None
        assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_execute_no_filtered_functions(self):
        """Test feature extraction with no filtered functions."""
        step = FeatureExtractStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None


class TestTrainStep:
    """Tests for TrainStep."""

    def test_get_name(self):
        """Test step name."""
        step = TrainStep()
        assert step.get_name() == "TrainStep"

    @pytest.mark.asyncio
    async def test_execute_no_model_name(self):
        """Test training without model name."""
        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None

    @patch("app.processing.steps.MLPersistanceUtil")
    @patch("app.processing.steps.MLTask")
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_ml_task, mock_persistence):
        """Test successful training."""
        from unittest.mock import AsyncMock

        mock_pipeline = MagicMock()
        mock_ml_task.get_multi_class_pipeline.return_value = mock_pipeline
        mock_persistence.save_model = AsyncMock()

        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "functionName": "category1", "tokens": "int x"},
                    {"name": "func2", "functionName": "category2", "tokens": "void y"},
                ],
                "tokens": ["int x", "void y"],
            },
        )
        result = await step.execute(context)

        assert result.error is None
        mock_persistence.save_model.assert_called_once()


class TestPredictStep:
    """Tests for PredictStep."""

    def test_get_name(self):
        """Test step name."""
        step = PredictStep()
        assert step.get_name() == "PredictStep"

    @pytest.mark.asyncio
    async def test_execute_no_model_name(self):
        """Test prediction without model name."""
        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None

    @patch("app.processing.steps.MLPersistanceUtil")
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_persistence):
        """Test successful prediction."""
        import numpy as np
        from unittest.mock import AsyncMock

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0, 1])
        mock_model.predict_proba.return_value = np.array([[0.9, 0.1], [0.2, 0.8]])

        mock_encoder = MagicMock()
        mock_encoder.inverse_transform.return_value = np.array(["category1", "category2"])

        mock_persistence.load_model = AsyncMock(return_value=(mock_model, mock_encoder))

        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x"},
                    {"name": "func2", "tokens": "void y"},
                ],
                "tokens": ["int x", "void y"],
            },
        )
        result = await step.execute(context)

        assert result.error is None
        predictions = result.get("predictions")
        assert predictions == ["category1", "category2"]
