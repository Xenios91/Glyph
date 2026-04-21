"""Unit tests for request handler classes and data processing."""
from app.services.request_handler import (
    DataHandler,
    TrainingRequest,
    PredictionRequest,
    GhidraRequest,
    Prediction,
)


class TestDataHandler:
    """Tests for DataHandler initialization and data processing."""

    def test_data_handler_init(self):
        """Test DataHandler initializes with correct attributes."""
        test_data = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            }
        }

        handler = DataHandler("test-uuid", test_data, "test-model")
        assert handler.uuid == "test-uuid"
        assert handler.model_name == "test-model"
        assert handler.status == "starting"

    def test_clean_dict_removes_duplicates(self):
        """Test duplicate functions are removed during initialization."""
        duplicate_data = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            }
        }

        handler = DataHandler("test-uuid", duplicate_data, "test-model")
        assert len(handler.json_dict["functionsMap"]["functions"]) == 2

    def test_get_functions(self):
        """Test get_functions returns correct function count."""
        test_data = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            }
        }

        handler = DataHandler("test-uuid", test_data, "test-model")
        functions = handler.get_functions()
        assert len(functions) == 2


class TestTrainingRequest:
    """Tests for TrainingRequest initialization and data loading."""

    def test_training_request_init(self):
        """Test TrainingRequest initializes with correct attributes."""
        test_data = {
            "binaryName": "test_binary",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            },
        }

        request = TrainingRequest("test-uuid", "test-model", test_data)
        assert request.bin_name == "test_binary"
        assert request.data is not None
        assert len(request.data) == 2

    def test_training_request_load_data_with_duplicates(self):
        """Test duplicate functions are removed during data loading."""
        duplicate_data = {
            "binaryName": "test_binary",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            },
        }

        request = TrainingRequest("test-uuid", "test-model", duplicate_data)
        assert len(request.data) == 2
        assert "tokens" in request.data.columns


class TestPredictionRequest:
    """Tests for PredictionRequest initialization and prediction handling."""

    def test_prediction_request_init(self):
        """Test PredictionRequest initializes with correct attributes."""
        test_data = {
            "taskName": "test_task",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            },
        }

        request = PredictionRequest("test-uuid", "test-model", test_data)
        assert request.task_name == "test_task"
        assert request.data is not None
        assert len(request.data) == 2

    def test_prediction_request_load_data_with_duplicates(self):
        """Test duplicate functions are removed during data loading."""
        duplicate_data = {
            "taskName": "test_task",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            },
        }

        request = PredictionRequest("test-uuid", "test-model", duplicate_data)
        assert len(request.data) == 2
        assert "tokens" in request.data.columns

    def test_set_prediction_values(self):
        """Test prediction values are correctly assigned to functions.
        
        Skip: set_prediction_values method does not exist in current implementation.
        """
        import pytest
        pytest.skip("set_prediction_values method does not exist in current implementation")


class TestGhidraRequest:
    """Tests for GhidraRequest initialization."""

    def test_ghidra_request_init(self):
        """Test GhidraRequest initializes with correct attributes and generates UUID."""
        request = GhidraRequest(
            filename="test_file.txt",
            is_training=True,
            model_name="test-model",
            task_name="test_task",
            ml_class_type="test_class",
        )
        # Path.as_posix() returns the path as-is without adding workspace directory
        assert request.file_name == "test_file.txt"
        assert request.is_training is True
        assert request.model_name == "test-model"
        assert request.task_name == "test_task"
        assert request.ml_class_type == "test_class"
        assert request.uuid is not None
        assert isinstance(request.uuid, str)
        assert len(request.uuid) > 0


class TestPrediction:
    """Tests for Prediction class initialization."""

    def test_prediction_init(self):
        """Test Prediction initializes with correct attributes."""
        pred_data = {"result": "success"}
        prediction = Prediction("test_task", "test-model", pred_data)
        assert prediction.task_name == "test_task"
        assert prediction.model_name == "test-model"
        assert prediction.predictions == pred_data