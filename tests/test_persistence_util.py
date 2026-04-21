"""Unit tests for persistence utilities including ML, prediction, and function storage."""
import pytest
from unittest.mock import MagicMock, patch, call
from io import BytesIO

from app.utils.persistence_util import (
    MLTask,
    PredictionPersistanceUtil,
    MLPersistanceUtil,
    FunctionPersistanceUtil,
)
from app.services.request_handler import Prediction, PredictionRequest, TrainingRequest


class TestMLTask:
    """Tests for MLTask pipeline creation."""

    def test_get_multi_class_pipeline(self):
        """Test multi-class pipeline has correct components."""
        pipeline = MLTask.get_multi_class_pipeline()
        assert pipeline is not None
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0][0] == "preprocessor"
        assert pipeline.steps[1][0] == "clf"

    def test_get_single_class_pipeline(self):
        """Test single-class pipeline has correct components."""
        # Note: MLTask only has get_multi_class_pipeline, not get_single_class_pipeline
        # This test is skipped as the method doesn't exist
        pytest.skip("get_single_class_pipeline method does not exist in MLTask")


class TestPredictionPersistanceUtil:
    """Tests for PredictionPersistanceUtil operations."""

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_predictions_list(self, mock_sql_util):
        """Test retrieving list of predictions."""
        mock_prediction = MagicMock(spec=Prediction)
        mock_sql_util.get_predictions_list.return_value = [mock_prediction]

        result = PredictionPersistanceUtil.get_predictions_list()

        assert len(result) == 1
        assert result[0] == mock_prediction
        mock_sql_util.get_predictions_list.assert_called_once()

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_predictions_success(self, mock_sql_util):
        """Test retrieving a specific prediction by task and model."""
        mock_prediction = MagicMock(spec=Prediction)
        mock_sql_util.get_predictions.return_value = mock_prediction

        result = PredictionPersistanceUtil.get_predictions("test_task", "test_model")

        assert result == mock_prediction
        mock_sql_util.get_predictions.assert_called_once_with("test_task", "test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_predictions_not_found(self, mock_sql_util):
        """Test retrieving non-existent prediction raises ValueError."""
        mock_sql_util.get_predictions.return_value = None

        with pytest.raises(ValueError, match="not found"):
            PredictionPersistanceUtil.get_predictions("test_task", "test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_predictions_empty_task_name(self, mock_sql_util):
        """Test empty task name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty strings"):
            PredictionPersistanceUtil.get_predictions("", "test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_predictions_empty_model_name(self, mock_sql_util):
        """Test empty model name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty strings"):
            PredictionPersistanceUtil.get_predictions("test_task", "")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_prediction(self, mock_sql_util):
        """Test deleting a prediction by task name."""
        PredictionPersistanceUtil.delete_prediction("test_task")
        mock_sql_util.delete_prediction.assert_called_once_with("test_task")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_prediction_empty_task_name(self, mock_sql_util):
        """Test empty task name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            PredictionPersistanceUtil.delete_prediction("")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_model_predictions(self, mock_sql_util):
        """Test deleting all predictions for a model."""
        PredictionPersistanceUtil.delete_model_predictions("test_model")
        mock_sql_util.delete_model_predictions.assert_called_once_with("test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_model_predictions_empty_model_name(self, mock_sql_util):
        """Test empty model name raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            PredictionPersistanceUtil.delete_model_predictions("")


class TestMLPersistanceUtil:
    """Tests for MLPersistanceUtil operations."""

    @patch("app.utils.persistence_util.SQLUtil")
    @patch("app.utils.persistence_util.joblib")
    def test_save_model_success(self, mock_joblib, mock_sql_util):
        """Test saving a model successfully."""
        mock_pipeline = MagicMock()
        mock_label_encoder = MagicMock()
        mock_joblib.dump = MagicMock()

        MLPersistanceUtil.save_model("test_model", mock_label_encoder, mock_pipeline)

        mock_sql_util.save_model.assert_called_once()

    @patch("app.utils.persistence_util.SQLUtil")
    def test_save_model_empty_model_name(self, mock_sql_util):
        """Test empty model name raises ValueError."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.save_model("", MagicMock(), MagicMock())

    @patch("app.utils.persistence_util.SQLUtil")
    def test_save_model_none_pipeline(self, mock_sql_util):
        """Test None pipeline raises ValueError."""
        with pytest.raises(ValueError, match="pipeline must not be None"):
            MLPersistanceUtil.save_model("test_model", MagicMock(), None)

    @patch("app.utils.persistence_util.SQLUtil")
    def test_save_model_none_label_encoder(self, mock_sql_util):
        """Test None label encoder raises ValueError."""
        with pytest.raises(ValueError, match="label_encoder must not be None"):
            MLPersistanceUtil.save_model("test_model", None, MagicMock())

    @patch("app.utils.persistence_util.SQLUtil")
    @patch("app.utils.persistence_util.secure_load")
    def test_load_model_success(self, mock_secure_load, mock_sql_util):
        """Test loading a model successfully."""
        # Model data has 3 fields: model_name, label_encoder, model
        mock_sql_util.get_model.return_value = ("test_model", b"encoder_data", b"model_data")
        mock_secure_load.side_effect = [MagicMock(), MagicMock()]

        label_encoder, pipeline = MLPersistanceUtil.load_model("test_model")

        assert label_encoder is not None
        assert pipeline is not None
        mock_sql_util.get_model.assert_called_once_with("test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_load_model_not_found(self, mock_sql_util):
        """Test loading non-existent model raises ValueError."""
        mock_sql_util.get_model.return_value = None

        with pytest.raises(ValueError, match="not found"):
            MLPersistanceUtil.load_model("nonexistent")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_load_model_empty_model_name(self, mock_sql_util):
        """Test empty model name raises ValueError."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.load_model("")

    @patch("app.utils.persistence_util.SQLUtil")
    @patch("app.utils.persistence_util.secure_load")
    def test_load_model_invalid_schema(self, mock_secure_load, mock_sql_util):
        """Test loading model with invalid schema raises RuntimeError."""
        # Model data has 3 fields: model_name, label_encoder, model
        mock_sql_util.get_model.return_value = ("test_model", b"encoder_data", b"model_data")
        mock_secure_load.side_effect = Exception("Invalid schema")

        with pytest.raises(RuntimeError, match="Could not deserialize model data"):
            MLPersistanceUtil.load_model("test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_models_list(self, mock_sql_util):
        """Test retrieving list of model names."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.get_models_list()

        assert result == {"model1", "model2"}
        mock_sql_util.get_models_list.assert_called_once()

    @patch("app.utils.persistence_util.SQLUtil")
    def test_check_name_exists(self, mock_sql_util):
        """Test checking if model name exists."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.check_name("model1")

        assert result is True

    @patch("app.utils.persistence_util.SQLUtil")
    def test_check_name_not_exists(self, mock_sql_util):
        """Test checking if model name does not exist."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.check_name("model3")

        assert result is False

    @patch("app.utils.persistence_util.SQLUtil")
    def test_check_name_empty(self, mock_sql_util):
        """Test checking empty model name returns False."""
        result = MLPersistanceUtil.check_name("")

        assert result is False

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_model(self, mock_sql_util):
        """Test deleting a model."""
        MLPersistanceUtil.delete_model("test_model")
        mock_sql_util.delete_model.assert_called_once_with("test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_delete_model_empty_name(self, mock_sql_util):
        """Test deleting model with empty name raises ValueError."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.delete_model("")


class TestFunctionPersistanceUtil:
    """Tests for FunctionPersistanceUtil operations."""

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_functions(self, mock_sql_util):
        """Test retrieving functions for a model."""
        mock_functions = [{"name": "func1"}, {"name": "func2"}]
        mock_sql_util.get_functions.return_value = mock_functions

        result = FunctionPersistanceUtil.get_functions("test_model")

        assert result == mock_functions
        mock_sql_util.get_functions.assert_called_once_with("test_model")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_functions_empty_result(self, mock_sql_util):
        """Test retrieving functions when none exist returns empty list."""
        mock_sql_util.get_functions.return_value = None

        result = FunctionPersistanceUtil.get_functions("test_model")

        assert result == []

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_functions_empty_model_name(self, mock_sql_util):
        """Test empty model name raises ValueError."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            FunctionPersistanceUtil.get_functions("")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_function(self, mock_sql_util):
        """Test retrieving a specific function."""
        mock_function = [{"name": "func1", "tokens": "token1 token2"}]
        mock_sql_util.get_function.return_value = mock_function

        result = FunctionPersistanceUtil.get_function("test_model", "func1")

        assert result == mock_function
        mock_sql_util.get_function.assert_called_once_with("test_model", "func1")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_function_not_found(self, mock_sql_util):
        """Test non-existent function returns empty list."""
        mock_sql_util.get_function.return_value = None

        result = FunctionPersistanceUtil.get_function("test_model", "nonexistent")

        assert result == []

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_function_empty_args(self, mock_sql_util):
        """Test empty arguments raise ValueError."""
        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_function("", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_function("test_model", "")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_model_functions(self, mock_sql_util):
        """Test adding functions for a model."""
        mock_training_request = MagicMock(spec=TrainingRequest)
        mock_functions = [{"name": "func1", "tokenList": ["token1"]}]
        mock_training_request.get_functions.return_value = mock_functions
        mock_training_request.model_name = "test_model"

        FunctionPersistanceUtil.add_model_functions(mock_training_request)

        mock_sql_util.save_functions.assert_called_once_with("test_model", mock_functions)

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_model_functions_none_request(self, mock_sql_util):
        """Test None request raises ValueError."""
        with pytest.raises(ValueError, match="training_request must not be None"):
            FunctionPersistanceUtil.add_model_functions(None)

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_prediction_functions(self, mock_sql_util):
        """Test adding prediction functions."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)
        mock_functions = [{"name": "func1"}]
        mock_prediction_request.get_functions.return_value = mock_functions
        mock_prediction_request.task_name = "test_task"
        mock_prediction_request.model_name = "test_model"
        predictions = ["label1"]

        FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, predictions)

        mock_sql_util.save_predictions.assert_called_once()

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_prediction_functions_none_request(self, mock_sql_util):
        """Test None request raises ValueError."""
        with pytest.raises(ValueError, match="prediction_request must not be None"):
            FunctionPersistanceUtil.add_prediction_functions(None, ["label1"])

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_prediction_functions_none_predictions(self, mock_sql_util):
        """Test None predictions raises ValueError."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)
        mock_prediction_request.get_functions.return_value = [{"name": "func1"}]

        with pytest.raises(ValueError, match="predictions must not be None"):
            FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, None)

    @patch("app.utils.persistence_util.SQLUtil")
    def test_add_prediction_functions_invalid_type(self, mock_sql_util):
        """Test invalid prediction type raises TypeError."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)
        mock_prediction_request.get_functions.return_value = [{"name": "func1"}]

        with pytest.raises(TypeError, match="predictions must be a list"):
            FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, "invalid")

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_prediction_function(self, mock_sql_util):
        """Test retrieving a prediction function."""
        mock_function = {"name": "func1", "tokens": "pred tokens"}
        mock_sql_util.get_prediction_function.return_value = mock_function

        result = FunctionPersistanceUtil.get_prediction_function(
            "test_task", "test_model", "func1"
        )

        assert result == mock_function
        mock_sql_util.get_prediction_function.assert_called_once_with(
            "test_task", "test_model", "func1"
        )

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_prediction_function_not_found(self, mock_sql_util):
        """Test non-existent prediction function raises ValueError."""
        mock_sql_util.get_prediction_function.return_value = None

        with pytest.raises(ValueError, match="not found"):
            FunctionPersistanceUtil.get_prediction_function(
                "test_task", "test_model", "nonexistent"
            )

    @patch("app.utils.persistence_util.SQLUtil")
    def test_get_prediction_function_empty_args(self, mock_sql_util):
        """Test empty arguments raise ValueError."""
        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("", "test_model", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("test_task", "", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("test_task", "test_model", "")
