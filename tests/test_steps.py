"""Tests for pipeline step implementations.

This module contains tests for the individual pipeline steps.
"""

from typing import Any

from unittest.mock import MagicMock, patch

from app.processing.pipeline import PipelineContext
from app.processing.steps import (
    ValidationStep,
    DecompileStep,
    TokenizeStep,
    FilterStep,
    FeatureExtractStep,
    TrainStep,
    PredictStep,
    SaveRawFunctionsStep,
    LoadBinaryFunctionsStep,
    _filter_tokens,  # pyright: ignore[reportPrivateUsage]
    _remove_comments,  # pyright: ignore[reportPrivateUsage]
    _check_if_variable,  # pyright: ignore[reportPrivateUsage]
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

    def test_single_line_comments_not_removed(self):
        """Test that single-line // comments are preserved (not removed).
        
        _remove_comments only handles multi-line /* */ comments, not // comments.
        """
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

    async def test_execute_valid_file(self, tmp_path: Any) -> None:
        """Test validation with a valid file."""
        temp_file = tmp_path / "test_binary"
        temp_file.write_bytes(b"test content")

        step = ValidationStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path=str(temp_file),
        )
        result = await step.execute(context)
        assert result.error is None

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

    async def test_execute_empty_file(self, tmp_path: Any) -> None:
        """Test validation with an empty file."""
        temp_file = tmp_path / "empty_binary"
        temp_file.write_bytes(b"")

        step = ValidationStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path=str(temp_file),
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "empty" in result.error

    async def test_execute_max_size(self, tmp_path: Any) -> None:
        """Test validation with max size limit."""
        temp_file = tmp_path / "large_binary"
        temp_file.write_bytes(b"x" * 1024 * 1024)  # 1 MB file

        step = ValidationStep(max_size_mb=0.5)  # 0.5 MB limit
        context = PipelineContext(
            uuid="test-uuid",
            binary_path=str(temp_file),
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "exceeds" in result.error


class TestDecompileStep:
    """Tests for DecompileStep."""

    def test_get_name(self):
        """Test step name."""
        step = DecompileStep()
        assert step.get_name() == "DecompileStep"

    @patch("app.processing.ghidra_processor.analyze_binary_and_decompile")
    async def test_execute_success(self, mock_analyze: Any) -> None:
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
    async def test_execute_failure(self, mock_analyze: Any) -> None:
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

    async def test_execute_no_model_name(self):
        """Test training without model name."""
        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None

    @patch("app.processing.steps.ModelRepository")
    @patch("app.processing.steps.MLTask")
    async def test_execute_success(self, mock_ml_task: Any, mock_persistence: Any) -> None:
        """Test successful training."""
        from unittest.mock import AsyncMock

        mock_pipeline = MagicMock()
        mock_ml_task.get_multi_class_pipeline.return_value = mock_pipeline  # pyright: ignore[reportUnknownMemberType]
        mock_persistence.save_model = AsyncMock()

        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "functionName": "category1", "tokens": "int main function"},
                    {"name": "func2", "functionName": "category2", "tokens": "void helper function"},
                ],
                "tokens": ["int main function", "void helper function"],
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

    async def test_execute_no_model_name(self):
        """Test prediction without model name."""
        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)

        assert result.error is not None

    @patch("app.processing.steps.ModelRepository")
    async def test_execute_success(self, mock_persistence: Any) -> None:
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


class TestValidationStep_Errors:
    """Tests for ValidationStep error paths."""

    async def test_execute_file_not_readable(self, tmp_path: Any) -> None:
        """Test validation with a file that is not readable."""
        temp_file = tmp_path / "unreadable_binary"
        temp_file.write_bytes(b"test content")
        temp_file.chmod(0o000)

        step = ValidationStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path=str(temp_file),
        )
        result = await step.execute(context)
        temp_file.chmod(0o644)
        assert result.error is not None
        assert "not readable" in result.error


class TestFeatureExtractStep_Errors:
    """Tests for FeatureExtractStep error paths."""

    async def test_execute_no_tokens_in_filtered_functions(self):
        """Test feature extraction with filtered functions that have no tokens."""
        step = FeatureExtractStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": ""},
                    {"name": "func2", "tokens": ""},
                ]
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "No tokens found" in result.error


class TestTrainStep_Errors:
    """Tests for TrainStep error paths."""

    async def test_execute_no_tokens_in_context(self):
        """Test training with no tokens in context."""
        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "filtered_functions": [
                    {"name": "func1", "functionName": "cat", "tokens": "int x"},
                ],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "No tokens found" in result.error

    async def test_execute_no_model_name(self):
        """Test training without model name in metadata."""
        step = TrainStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "filtered_functions": [
                    {"name": "func1", "functionName": "cat", "tokens": "int x"},
                ],
                "tokens": ["int x"],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "model_name" in result.error

    @patch("app.processing.steps.ModelRepository")
    @patch("app.config.pipeline_configs.MLTask")
    async def test_execute_training_fails(self, mock_ml_task: Any, mock_persistence: Any) -> None:
        """Test training when model.fit raises an exception."""
        from unittest.mock import AsyncMock

        mock_pipeline = MagicMock()
        mock_pipeline.fit.side_effect = Exception("Training error")
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
                ],
                "tokens": ["int x"],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "Training failed" in result.error


class TestPredictStep_Errors:
    """Tests for PredictStep error paths."""

    async def test_execute_no_tokens(self):
        """Test prediction with no tokens in context."""
        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x"},
                ],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "No tokens found" in result.error

    async def test_execute_no_model_name(self):
        """Test prediction without model name in metadata."""
        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x"},
                ],
                "tokens": ["int x"],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "model_name" in result.error

    @patch("app.processing.steps.ModelRepository")
    async def test_execute_prediction_fails(self, mock_persistence: Any) -> None:
        """Test prediction when model loading fails."""
        from unittest.mock import AsyncMock

        mock_persistence.load_model = AsyncMock(side_effect=Exception("Model not found"))

        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "missing_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x"},
                ],
                "tokens": ["int x"],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "Prediction failed" in result.error

    @patch("app.processing.steps.ModelRepository")
    @patch("app.processing.steps.get_settings")
    async def test_execute_low_probability_becomes_unknown(
        self, mock_get_settings: Any, mock_persistence: Any
    ) -> None:
        """Test that predictions below threshold become Unknown."""
        import numpy as np
        from unittest.mock import AsyncMock

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0])
        # predict_proba returns values before *100 multiplication in the code
        mock_model.predict_proba.return_value = np.array([[0.30, 0.70]])

        mock_encoder = MagicMock()
        mock_encoder.inverse_transform.return_value = np.array(["category1"])

        mock_persistence.load_model = AsyncMock(return_value=(mock_model, mock_encoder))

        mock_settings = MagicMock()
        mock_settings.prediction_probability_threshold = 80.0
        mock_get_settings.return_value = mock_settings

        step = PredictStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            metadata={"model_name": "test_model"},
            data={
                "filtered_functions": [
                    {"name": "func1", "tokens": "int x"},
                ],
                "tokens": ["int x"],
            },
        )
        result = await step.execute(context)
        assert result.error is None
        predictions = result.get("predictions")
        assert predictions == ["Unknown"]


class TestSaveRawFunctionsStep:
    """Tests for SaveRawFunctionsStep."""

    def test_get_name(self):
        """Test step name."""
        step = SaveRawFunctionsStep()
        assert step.get_name() == "SaveRawFunctionsStep"

    async def test_execute_missing_binary_id(self):
        """Test save with missing binary_id."""
        step = SaveRawFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "functions": [{"functionName": "main", "raw_code": "int main() {}"}],
            },
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "binary_id" in result.error

    async def test_execute_no_functions(self):
        """Test save with no functions."""
        step = SaveRawFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={"binary_id": 1},
        )
        result = await step.execute(context)
        assert result.error is None
        assert result.get("functions_saved") == 0

    @patch("app.database.sql_service.SQLUtil")
    async def test_execute_success(self, mock_sql: Any) -> None:
        """Test successful save of raw functions."""
        from unittest.mock import AsyncMock

        mock_sql.save_binary_functions = AsyncMock()

        step = SaveRawFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={
                "binary_id": 1,
                "functions": [
                    {"functionName": "main", "lowAddress": "0x401000", "raw_code": "int main() {}"},
                    {"functionName": "helper", "lowAddress": "0x401100", "raw_code": "void helper() {}"},
                ],
            },
        )
        result = await step.execute(context)
        assert result.error is None
        assert result.get("functions_saved") == 2
        mock_sql.save_binary_functions.assert_called_once()

    async def test_execute_skips_functions_without_raw_code(self):
        """Test that functions without raw_code are skipped."""
        with patch("app.database.sql_service.SQLUtil") as mock_sql:
            from unittest.mock import AsyncMock

            mock_sql.save_binary_functions = AsyncMock()

            step = SaveRawFunctionsStep()
            context = PipelineContext(
                uuid="test-uuid",
                binary_path="/test/binary",
                data={
                    "binary_id": 1,
                    "functions": [
                        {"functionName": "main", "raw_code": "int main() {}"},
                        {"functionName": "empty", "raw_code": ""},
                        {"functionName": "no_code"},
                    ],
                },
            )
            result = await step.execute(context)
            assert result.error is None
            assert result.get("functions_saved") == 1


class TestLoadBinaryFunctionsStep:
    """Tests for LoadBinaryFunctionsStep."""

    def test_get_name(self):
        """Test step name."""
        step = LoadBinaryFunctionsStep()
        assert step.get_name() == "LoadBinaryFunctionsStep"

    async def test_execute_missing_binary_id(self):
        """Test load with missing binary_id."""
        step = LoadBinaryFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "binary_id" in result.error

    @patch("app.database.sql_service.SQLUtil")
    async def test_execute_success(self, mock_sql: Any) -> None:
        """Test successful load of binary functions."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock ORM objects with attribute access (not dicts)
        mock_bf = MagicMock()
        mock_bf.function_name = "main"
        mock_bf.entrypoint = "0x401000"
        mock_bf.raw_code = "int main() {}"

        mock_sql.get_binary_functions = AsyncMock(return_value=[mock_bf])

        step = LoadBinaryFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={"binary_id": 1},
        )
        result = await step.execute(context)
        assert result.error is None
        functions = result.get("functions")
        assert len(functions) == 1
        assert functions[0]["functionName"] == "main"

    @patch("app.database.sql_service.SQLUtil")
    async def test_execute_no_functions_found(self, mock_sql: Any) -> None:
        """Test load when no functions exist for binary."""
        from unittest.mock import AsyncMock

        mock_sql.get_binary_functions = AsyncMock(return_value=[])

        step = LoadBinaryFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={"binary_id": 1},
        )
        result = await step.execute(context)
        assert result.error is not None
        assert "No functions found" in result.error

    @patch("app.database.sql_service.SQLUtil")
    async def test_execute_load_fails(self, mock_sql: Any) -> None:
        """Test load when database query fails."""
        from unittest.mock import AsyncMock

        mock_sql.get_binary_functions = AsyncMock(side_effect=Exception("DB error"))

        step = LoadBinaryFunctionsStep()
        context = PipelineContext(
            uuid="test-uuid",
            binary_path="/test/binary",
            data={"binary_id": 1},
        )
        result = await step.execute(context)
        assert result.error is not None
