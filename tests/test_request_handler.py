"""Unit tests for request handler classes and data processing."""

from typing import Any

from app.services.request_handler import (
    DataHandler,
    Prediction,
    PredictionRequest,
    TrainingRequest,
)


class TestDataHandler:
    """Tests for DataHandler initialization and data processing."""

    def test_data_handler_init(self) -> None:
        """Test DataHandler initializes with correct attributes."""
        test_data: dict[str, Any] = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        handler = DataHandler("test-uuid", test_data, "test-model")
        assert handler.uuid == "test-uuid"
        assert handler.model_name == "test-model"

    def test_clean_dict_removes_duplicates(self) -> None:
        """Test duplicate functions are removed during initialization."""
        duplicate_data: dict[str, Any] = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        handler = DataHandler("test-uuid", duplicate_data, "test-model")
        assert len(handler.json_dict["functionsMap"]["functions"]) == 2

    def test_get_functions(self) -> None:
        """Test get_functions returns correct function count."""
        test_data: dict[str, Any] = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        handler = DataHandler("test-uuid", test_data, "test-model")
        functions = handler.get_functions()
        assert len(functions) == 2


class TestTrainingRequest:
    """Tests for TrainingRequest initialization and data loading."""

    def test_training_request_init(self) -> None:
        """Test TrainingRequest initializes with correct attributes."""
        test_data: dict[str, Any] = {
            "binaryName": "test_binary",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        request = TrainingRequest("test-uuid", "test-model", test_data)
        assert request.bin_name == "test_binary"
        assert len(request.get_functions()) == 2

    def test_training_request_load_data_with_duplicates(self) -> None:
        """Test duplicate functions are removed during data loading."""
        duplicate_data: dict[str, Any] = {
            "binaryName": "test_binary",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        request = TrainingRequest("test-uuid", "test-model", duplicate_data)
        functions = request.get_functions()
        assert len(functions) == 2
        assert "tokens" in functions[0]


class TestPredictionRequest:
    """Tests for PredictionRequest initialization and prediction handling."""

    def test_prediction_request_init(self) -> None:
        """Test PredictionRequest initializes with correct attributes."""
        test_data: dict[str, Any] = {
            "taskName": "test_task",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        request = PredictionRequest("test-uuid", "test-model", test_data)
        assert request.task_name == "test_task"
        assert len(request.get_functions()) == 2

    def test_prediction_request_load_data_with_duplicates(self) -> None:
        """Test duplicate functions are removed during data loading."""
        duplicate_data: dict[str, Any] = {
            "taskName": "test_task",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ],
            },
        }

        request = PredictionRequest("test-uuid", "test-model", duplicate_data)
        functions = request.get_functions()
        assert len(functions) == 2
        assert "tokens" in functions[0]


class TestPrediction:
    """Tests for Prediction class initialization."""

    def test_prediction_init(self) -> None:
        """Test Prediction initializes with correct attributes."""
        pred_data: list[dict[str, Any]] = [{"result": "success"}]
        prediction = Prediction("test_task", "test-model", pred_data)
        assert prediction.task_name == "test_task"
        assert prediction.model_name == "test-model"
        assert prediction.predictions == pred_data
