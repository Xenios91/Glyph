import pytest
from unittest.mock import MagicMock, patch, call
from io import BytesIO

from app.persistence_util import (
    MLTask,
    PredictionPersistanceUtil,
    MLPersistanceUtil,
    FunctionPersistanceUtil,
)
from app.request_handler import Prediction, PredictionRequest, TrainingRequest


class TestMLTask:
    """Tests for MLTask pipeline creation."""

    def test_get_multi_class_pipeline(self):
        """Test that multi-class pipeline is created with correct components."""
        pipeline = MLTask.get_multi_class_pipeline()
        assert pipeline is not None
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0][0] == "preprocessor"
        assert pipeline.steps[1][0] == "clf"

    def test_get_single_class_pipeline(self):
        """Test that single-class pipeline is created with correct components."""
        pipeline = MLTask.get_single_class_pipeline()
        assert pipeline is not None
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0][0] == "preprocessor"
        assert pipeline.steps[1][0] == "clf"


class TestPredictionPersistanceUtil:
    """Tests for PredictionPersistanceUtil."""

    @patch("app.persistence_util.SQLUtil")
    def test_get_predictions_list(self, mock_sql_util):
        """Test retrieving predictions list."""
        mock_prediction = MagicMock(spec=Prediction)
        mock_sql_util.get_predictions_list.return_value = [mock_prediction]

        result = PredictionPersistanceUtil.get_predictions_list()

        assert len(result) == 1
        assert result[0] == mock_prediction
        mock_sql_util.get_predictions_list.assert_called_once()

    @patch("app.persistence_util.SQLUtil")
    def test_get_predictions_success(self, mock_sql_util):
        """Test retrieving a specific prediction."""
        mock_prediction = MagicMock(spec=Prediction)
        mock_sql_util.get_predictions.return_value = mock_prediction

        result = PredictionPersistanceUtil.get_predictions("test_task", "test_model")

        assert result == mock_prediction
        mock_sql_util.get_predictions.assert_called_once_with("test_task", "test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_get_predictions_not_found(self, mock_sql_util):
        """Test retrieving a prediction that doesn't exist."""
        mock_sql_util.get_predictions.return_value = None

        with pytest.raises(ValueError, match="not found"):
            PredictionPersistanceUtil.get_predictions("test_task", "test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_get_predictions_empty_task_name(self, mock_sql_util):
        """Test retrieving prediction with empty task name raises error."""
        with pytest.raises(ValueError, match="non-empty strings"):
            PredictionPersistanceUtil.get_predictions("", "test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_get_predictions_empty_model_name(self, mock_sql_util):
        """Test retrieving prediction with empty model name raises error."""
        with pytest.raises(ValueError, match="non-empty strings"):
            PredictionPersistanceUtil.get_predictions("test_task", "")

    @patch("app.persistence_util.SQLUtil")
    def test_delete_prediction(self, mock_sql_util):
        """Test deleting a prediction."""
        PredictionPersistanceUtil.delete_prediction("test_task")
        mock_sql_util.delete_prediction.assert_called_once_with("test_task")

    @patch("app.persistence_util.SQLUtil")
    def test_delete_prediction_empty_task_name(self, mock_sql_util):
        """Test deleting prediction with empty task name raises error."""
        with pytest.raises(ValueError, match="non-empty string"):
            PredictionPersistanceUtil.delete_prediction("")

    @patch("app.persistence_util.SQLUtil")
    def test_delete_model_predictions(self, mock_sql_util):
        """Test deleting all predictions for a model."""
        PredictionPersistanceUtil.delete_model_predictions("test_model")
        mock_sql_util.delete_model_predictions.assert_called_once_with("test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_delete_model_predictions_empty_model_name(self, mock_sql_util):
        """Test deleting model predictions with empty model name raises error."""
        with pytest.raises(ValueError, match="non-empty string"):
            PredictionPersistanceUtil.delete_model_predictions("")


class TestMLPersistanceUtil:
    """Tests for MLPersistanceUtil."""

    @patch("app.persistence_util.SQLUtil")
    @patch("app.persistence_util.joblib")
    def test_save_model_success(self, mock_joblib, mock_sql_util):
        """Test saving a model successfully."""
        mock_pipeline = MagicMock()
        mock_label_encoder = MagicMock()
        mock_joblib.dump = MagicMock()

        MLPersistanceUtil.save_model("test_model", mock_label_encoder, mock_pipeline)

        mock_sql_util.save_model.assert_called_once()

    @patch("app.persistence_util.SQLUtil")
    def test_save_model_empty_model_name(self, mock_sql_util):
        """Test saving model with empty name raises error."""
        mock_pipeline = MagicMock()
        mock_label_encoder = MagicMock()

        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.save_model("", mock_label_encoder, mock_pipeline)

    @patch("app.persistence_util.SQLUtil")
    def test_save_model_none_pipeline(self, mock_sql_util):
        """Test saving model with None pipeline raises error."""
        mock_label_encoder = MagicMock()

        with pytest.raises(ValueError, match="pipeline must not be None"):
            MLPersistanceUtil.save_model("test_model", mock_label_encoder, None)

    @patch("app.persistence_util.SQLUtil")
    def test_save_model_none_label_encoder(self, mock_sql_util):
        """Test saving model with None label encoder raises error."""
        mock_pipeline = MagicMock()

        with pytest.raises(ValueError, match="label_encoder must not be None"):
            MLPersistanceUtil.save_model("test_model", None, mock_pipeline)

    @patch("app.persistence_util.SQLUtil")
    def test_load_model_success(self, mock_sql_util):
        """Test loading a model successfully."""
        mock_model = MagicMock()
        mock_label_encoder = MagicMock()

        def mock_load(buffer):
            if "model" in str(buffer):
                return mock_model
            return mock_label_encoder

        with patch("app.persistence_util.joblib.load", side_effect=mock_load):
            mock_sql_util.get_model.return_value = ("test_model", b"model_data", b"encoder_data")

            result = MLPersistanceUtil.load_model("test_model")

            assert len(result) == 2
            mock_sql_util.get_model.assert_called_once_with("test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_load_model_not_found(self, mock_sql_util):
        """Test loading a model that doesn't exist."""
        mock_sql_util.get_model.return_value = None

        with pytest.raises(ValueError, match="not found"):
            MLPersistanceUtil.load_model("nonexistent_model")

    @patch("app.persistence_util.SQLUtil")
    def test_load_model_empty_model_name(self, mock_sql_util):
        """Test loading model with empty name raises error."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.load_model("")

    @patch("app.persistence_util.SQLUtil")
    def test_load_model_invalid_schema(self, mock_sql_util):
        """Test loading model with invalid schema raises error."""
        mock_sql_util.get_model.return_value = ("test_model",)  # Only 1 field instead of 3

        with pytest.raises(ValueError, match="incorrect structure"):
            MLPersistanceUtil.load_model("test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_get_models_list(self, mock_sql_util):
        """Test getting list of models."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.get_models_list()

        assert result == {"model1", "model2"}
        mock_sql_util.get_models_list.assert_called_once()

    @patch("app.persistence_util.SQLUtil")
    def test_check_name_exists(self, mock_sql_util):
        """Test checking if model name exists."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.check_name("model1")

        assert result is True

    @patch("app.persistence_util.SQLUtil")
    def test_check_name_not_exists(self, mock_sql_util):
        """Test checking if non-existent model name exists."""
        mock_sql_util.get_models_list.return_value = {"model1", "model2"}

        result = MLPersistanceUtil.check_name("model3")

        assert result is False

    @patch("app.persistence_util.SQLUtil")
    def test_check_name_empty(self, mock_sql_util):
        """Test checking empty model name returns False."""
        result = MLPersistanceUtil.check_name("")

        assert result is False

    @patch("app.persistence_util.SQLUtil")
    def test_delete_model(self, mock_sql_util):
        """Test deleting a model."""
        MLPersistanceUtil.delete_model("test_model")
        mock_sql_util.delete_model.assert_called_once_with("test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_delete_model_empty_name(self, mock_sql_util):
        """Test deleting model with empty name raises error."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            MLPersistanceUtil.delete_model("")


class TestFunctionPersistanceUtil:
    """Tests for FunctionPersistanceUtil."""

    @patch("app.persistence_util.SQLUtil")
    def test_get_functions(self, mock_sql_util):
        """Test getting functions for a model."""
        mock_functions = [{"name": "func1"}, {"name": "func2"}]
        mock_sql_util.get_functions.return_value = mock_functions

        result = FunctionPersistanceUtil.get_functions("test_model")

        assert result == mock_functions
        mock_sql_util.get_functions.assert_called_once_with("test_model")

    @patch("app.persistence_util.SQLUtil")
    def test_get_functions_empty_result(self, mock_sql_util):
        """Test getting functions returns empty list when no functions found."""
        mock_sql_util.get_functions.return_value = []

        result = FunctionPersistanceUtil.get_functions("test_model")

        assert result == []

    @patch("app.persistence_util.SQLUtil")
    def test_get_functions_empty_model_name(self, mock_sql_util):
        """Test getting functions with empty model name raises error."""
        with pytest.raises(ValueError, match="model_name must be a non-empty string"):
            FunctionPersistanceUtil.get_functions("")

    @patch("app.persistence_util.SQLUtil")
    def test_get_function(self, mock_sql_util):
        """Test getting a specific function."""
        mock_function = {"name": "func1", "tokens": "token1 token2"}
        mock_sql_util.get_function.return_value = [mock_function]

        result = FunctionPersistanceUtil.get_function("test_model", "func1")

        assert result == mock_function
        mock_sql_util.get_function.assert_called_once_with("test_model", "func1")

    @patch("app.persistence_util.SQLUtil")
    def test_get_function_not_found(self, mock_sql_util):
        """Test getting a function that doesn't exist returns empty dict."""
        mock_sql_util.get_function.return_value = None

        result = FunctionPersistanceUtil.get_function("test_model", "nonexistent")

        assert result == {}

    @patch("app.persistence_util.SQLUtil")
    def test_get_function_empty_args(self, mock_sql_util):
        """Test getting function with empty args raises error."""
        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_function("", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_function("test_model", "")

    @patch("app.persistence_util.SQLUtil")
    def test_add_model_functions(self, mock_sql_util):
        """Test adding functions for a model."""
        mock_training_request = MagicMock(spec=TrainingRequest)
        mock_functions = [{"name": "func1", "tokenList": ["token1"]}]
        mock_training_request.get_functions.return_value = mock_functions
        mock_training_request.model_name = "test_model"

        FunctionPersistanceUtil.add_model_functions(mock_training_request)

        mock_sql_util.save_functions.assert_called_once_with("test_model", mock_functions)

    @patch("app.persistence_util.SQLUtil")
    def test_add_model_functions_none_request(self, mock_sql_util):
        """Test adding functions with None request raises error."""
        with pytest.raises(ValueError, match="training_request must not be None"):
            FunctionPersistanceUtil.add_model_functions(None)

    @patch("app.persistence_util.SQLUtil")
    def test_add_prediction_functions(self, mock_sql_util):
        """Test adding prediction functions."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)
        mock_functions = [{"name": "func1"}, {"name": "func2"}]
        mock_prediction_request.get_functions.return_value = mock_functions
        mock_prediction_request.task_name = "test_task"
        mock_prediction_request.model_name = "test_model"

        predictions = ["label1", "label2"]

        FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, predictions)

        mock_sql_util.save_predictions.assert_called_once()

    @patch("app.persistence_util.SQLUtil")
    def test_add_prediction_functions_none_request(self, mock_sql_util):
        """Test adding prediction functions with None request raises error."""
        with pytest.raises(ValueError, match="prediction_request must not be None"):
            FunctionPersistanceUtil.add_prediction_functions(None, ["label1"])

    @patch("app.persistence_util.SQLUtil")
    def test_add_prediction_functions_none_predictions(self, mock_sql_util):
        """Test adding prediction functions with None predictions raises error."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)

        with pytest.raises(ValueError, match="predictions must not be None"):
            FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, None)

    @patch("app.persistence_util.SQLUtil")
    def test_add_prediction_functions_invalid_type(self, mock_sql_util):
        """Test adding prediction functions with invalid predictions type raises error."""
        mock_prediction_request = MagicMock(spec=PredictionRequest)

        with pytest.raises(TypeError, match="predictions must be a list"):
            FunctionPersistanceUtil.add_prediction_functions(mock_prediction_request, "not_a_list")

    @patch("app.persistence_util.SQLUtil")
    def test_get_prediction_function(self, mock_sql_util):
        """Test getting a prediction function."""
        mock_function = {"functionName": "func1", "prediction": "label1"}
        mock_sql_util.get_prediction_function.return_value = mock_function

        result = FunctionPersistanceUtil.get_prediction_function(
            "test_task", "test_model", "func1"
        )

        assert result == mock_function
        mock_sql_util.get_prediction_function.assert_called_once_with(
            "test_task", "test_model", "func1"
        )

    @patch("app.persistence_util.SQLUtil")
    def test_get_prediction_function_not_found(self, mock_sql_util):
        """Test getting a prediction function that doesn't exist raises error."""
        mock_sql_util.get_prediction_function.return_value = None

        with pytest.raises(ValueError, match="not found"):
            FunctionPersistanceUtil.get_prediction_function(
                "test_task", "test_model", "func1"
            )

    @patch("app.persistence_util.SQLUtil")
    def test_get_prediction_function_empty_args(self, mock_sql_util):
        """Test getting prediction function with empty args raises error."""
        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("", "test_model", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("test_task", "", "func1")

        with pytest.raises(ValueError, match="non-empty strings"):
            FunctionPersistanceUtil.get_prediction_function("test_task", "test_model", "")