import sys
import os

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.request_handler import (
    DataHandler,
    TrainingRequest,
    PredictionRequest,
    GhidraRequest,
    Prediction,
)


class TestDataHandler:
    def test_data_handler_init(self):
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
        # Test with duplicate functions
        duplicate_data = {
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},  # Duplicate
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            }
        }

        handler = DataHandler("test-uuid", duplicate_data, "test-model")
        # Should have deduplicated functions
        assert len(handler.json_dict["functionsMap"]["functions"]) == 2

    def test_get_functions(self):
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
    def test_training_request_init(self):
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
        duplicate_data = {
            "binaryName": "test_binary",
            "functionsMap": {
                "functions": [
                    {"name": "func1", "tokenList": ["token1", "token2"]},
                    {"name": "func1", "tokenList": ["token1", "token2"]},  # Duplicate
                    {"name": "func2", "tokenList": ["token3", "token4"]},
                ]
            },
        }

        request = TrainingRequest("test-uuid", "test-model", duplicate_data)
        # Should have deduplicated functions
        assert len(request.data) == 2
        # Check that tokens were added
        assert "tokens" in request.data.columns


class TestPredictionRequest:
    def test_prediction_request_init(self):
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
        labels = ["label1", "label2"]
        request.set_prediction_values(labels)
        functions = request.get_functions()
        assert functions[0]["functionName"] == "label1"
        assert functions[1]["functionName"] == "label2"


class TestGhidraRequest:
    def test_ghidra_request_init(self):
        request = GhidraRequest(
            filename="test_file.txt",
            is_training=True,
            model_name="test-model",
            task_name="test_task",
            ml_class_type="test_class",
        )
        assert request.file_name == "/workspaces/Glyph/test_file.txt"
        assert request.is_training is True
        assert request.model_name == "test-model"
        assert request.task_name == "test_task"
        assert request.ml_class_type == "test_class"
        assert request.uuid is not None
        assert isinstance(request.uuid, str)
        assert len(request.uuid) > 0


class TestPrediction:
    def test_prediction_init(self):
        pred_data = {"result": "success"}
        prediction = Prediction("test_task", "test-model", pred_data)
        assert prediction.task_name == "test_task"
        assert prediction.model_name == "test-model"
        assert prediction.predictions == pred_data


def test_exception_handling():
    """Test that exceptions are properly handled and chained"""
    pass
