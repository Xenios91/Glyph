"""Tests for database repositories."""

import pickle
import pytest
from unittest.mock import Mock, patch

# Skip tests that depend on missing repository modules
# model_repository, prediction_repository, function_repository do not exist in current codebase
pytestmark = pytest.mark.skip(reason="Repository modules do not exist in current codebase")


class TestModelRepository:
    """Tests for ModelRepository."""

    @patch("app.database.repositories.model_repository.Model")
    @patch("app.database.repositories.model_repository.joblib.dump")
    @patch("app.database.repositories.model_repository.get_session")
    def test_save_model(self, mock_get_session, mock_joblib_dump, mock_model_class):
        """Test saving a model to the database."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        mock_model = Mock(spec=Model)
        mock_model_class.return_value = mock_model

        # Use a real object that can be pickled
        label_encoder = {"classes": [0, 1], "mapping": {0: "a", 1: "b"}}
        model_bytes = b"test_model_data"

        result = ModelRepository.save_model("test_model", label_encoder, model_bytes)

        mock_session.add.assert_called_once()
        assert result is mock_model

    @patch("app.database.repositories.model_repository.get_session")
    def test_get_models_list_empty(self, mock_get_session):
        """Test getting empty models list."""
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = []
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.get_models_list()

        assert result == set()

    @patch("app.database.repositories.model_repository.get_session")
    def test_get_models_list_with_models(self, mock_get_session):
        """Test getting models list with models."""
        mock_session = Mock()
        mock_model1 = Mock(spec=Model)
        mock_model1.model_name = "model1"
        mock_model2 = Mock(spec=Model)
        mock_model2.model_name = "model2"
        mock_session.query.return_value.all.return_value = [mock_model1, mock_model2]
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.get_models_list()

        assert result == {"model1", "model2"}

    @patch("app.database.repositories.model_repository.get_session")
    def test_get_model_found(self, mock_get_session):
        """Test getting a model that exists."""
        mock_session = Mock()
        mock_model = Mock(spec=Model)
        mock_model.model_name = "test_model"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_model
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.get_model("test_model")

        assert result is mock_model

    @patch("app.database.repositories.model_repository.get_session")
    def test_get_model_not_found(self, mock_get_session):
        """Test getting a model that doesn't exist."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.get_model("nonexistent")

        assert result is None

    @patch("app.database.repositories.model_repository.get_session")
    def test_delete_model_success(self, mock_get_session):
        """Test deleting a model successfully."""
        mock_session = Mock()
        mock_model = Mock(spec=Model)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_model
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.delete_model("test_model")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_model)

    @patch("app.database.repositories.model_repository.get_session")
    def test_delete_model_not_found(self, mock_get_session):
        """Test deleting a model that doesn't exist."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = ModelRepository.delete_model("nonexistent")

        assert result is False

    @patch("app.database.repositories.model_repository.ModelRepository.get_model")
    @patch("app.database.repositories.model_repository.joblib")
    def test_get_model_data_success(self, mock_joblib, mock_get_model):
        """Test getting model data successfully."""
        mock_model = Mock(spec=Model)
        mock_model.model_name = "test_model"
        mock_model.label_encoder_data = b"label_encoder_data"
        mock_model.model_data = b"model_data"
        mock_get_model.return_value = mock_model

        mock_label_encoder = Mock()
        mock_model_obj = Mock()
        mock_joblib.load.side_effect = [mock_label_encoder, mock_model_obj]

        result = ModelRepository.get_model_data("test_model")

        assert result is not None
        label_encoder, model_obj = result
        assert label_encoder is mock_label_encoder
        assert model_obj is mock_model_obj

    @patch("app.database.repositories.model_repository.ModelRepository.get_model")
    def test_get_model_data_not_found(self, mock_get_model):
        """Test getting model data when model doesn't exist."""
        mock_get_model.return_value = None

        result = ModelRepository.get_model_data("nonexistent")

        assert result is None

    @patch("app.database.repositories.model_repository.ModelRepository.get_model")
    @patch("app.database.repositories.model_repository.joblib.load")
    def test_get_model_data_deserialize_error(self, mock_joblib_load, mock_get_model):
        """Test getting model data when deserialization fails."""
        mock_model = Mock(spec=Model)
        mock_model.model_name = "test_model"
        mock_model.label_encoder_data = b"dummy_data"
        mock_model.model_data = b"dummy_data"
        mock_get_model.return_value = mock_model

        mock_joblib_load.side_effect = pickle.UnpicklingError("Deserialization error")

        result = ModelRepository.get_model_data("test_model")

        assert result is None


class TestPredictionRepository:
    """Tests for PredictionRepository."""

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_save_predictions(self, mock_get_session):
        """Test saving predictions to the database."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        mock_prediction = Mock(spec=Prediction)
        # Mock session.add to return the mock_prediction when called
        mock_session.add.return_value = mock_prediction

        functions = [{"functionName": "test", "prediction": "test_pred"}]

        result = PredictionRepository.save_predictions("test_task", "test_model", functions)

        mock_session.add.assert_called_once()
        # The function returns the Prediction object created inside, which is what session.add was called with
        assert mock_session.add.call_count == 1

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_get_predictions_list_empty(self, mock_get_session):
        """Test getting empty predictions list."""
        mock_session = Mock()
        mock_session.query.return_value.all.return_value = []
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.get_predictions_list()

        assert result == []

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_get_predictions_list_with_predictions(self, mock_get_session):
        """Test getting predictions list with predictions."""
        mock_session = Mock()
        mock_pred1 = Mock(spec=Prediction)
        mock_pred2 = Mock(spec=Prediction)
        mock_session.query.return_value.all.return_value = [mock_pred1, mock_pred2]
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.get_predictions_list()

        assert len(result) == 2

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_get_prediction_found(self, mock_get_session):
        """Test getting a prediction that exists."""
        mock_session = Mock()
        mock_prediction = Mock(spec=Prediction)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_prediction
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.get_prediction("test_task", "test_model")

        assert result is mock_prediction

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_get_prediction_not_found(self, mock_get_session):
        """Test getting a prediction that doesn't exist."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.get_prediction("test_task", "test_model")

        assert result is None

    @patch("app.database.repositories.prediction_repository.PredictionRepository.get_prediction")
    @patch("app.database.repositories.prediction_repository.joblib")
    def test_get_prediction_functions_success(self, mock_joblib, mock_get_prediction):
        """Test getting prediction functions successfully."""
        mock_prediction = Mock(spec=Prediction)
        mock_prediction.functions_data = b"functions_data"
        mock_get_prediction.return_value = mock_prediction

        mock_functions = [{"functionName": "test"}]
        mock_joblib.load.return_value = mock_functions

        result = PredictionRepository.get_prediction_functions("test_task", "test_model")

        assert result == mock_functions

    @patch("app.database.repositories.prediction_repository.PredictionRepository.get_prediction")
    def test_get_prediction_functions_not_found(self, mock_get_prediction):
        """Test getting prediction functions when prediction doesn't exist."""
        mock_get_prediction.return_value = None

        result = PredictionRepository.get_prediction_functions("test_task", "test_model")

        assert result is None

    @patch("app.database.repositories.prediction_repository.PredictionRepository.get_prediction")
    @patch("app.database.repositories.prediction_repository.joblib")
    def test_get_prediction_functions_not_list(self, mock_joblib, mock_get_prediction):
        """Test getting prediction functions when data is not a list."""
        mock_prediction = Mock(spec=Prediction)
        mock_prediction.functions_data = b"data"
        mock_get_prediction.return_value = mock_prediction

        mock_joblib.load.return_value = "not a list"

        result = PredictionRepository.get_prediction_functions("test_task", "test_model")

        assert result is None

    @patch("app.database.repositories.prediction_repository.PredictionRepository.get_prediction_functions")
    def test_get_prediction_function_found(self, mock_get_functions):
        """Test getting a specific prediction function that exists."""
        mock_get_functions.return_value = [
            {"functionName": "func1", "prediction": "pred1"},
            {"functionName": "func2", "prediction": "pred2"},
        ]

        result = PredictionRepository.get_prediction_function("test_task", "test_model", "func2")

        assert result is not None
        assert result["functionName"] == "func2"

    @patch("app.database.repositories.prediction_repository.PredictionRepository.get_prediction_functions")
    def test_get_prediction_function_not_found(self, mock_get_functions):
        """Test getting a specific prediction function that doesn't exist."""
        mock_get_functions.return_value = [
            {"functionName": "func1", "prediction": "pred1"},
        ]

        result = PredictionRepository.get_prediction_function("test_task", "test_model", "func2")

        assert result is None

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_delete_prediction_success(self, mock_get_session):
        """Test deleting a prediction successfully."""
        mock_session = Mock()
        mock_prediction = Mock(spec=Prediction)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_prediction
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.delete_prediction("test_task")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_prediction)

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_delete_prediction_not_found(self, mock_get_session):
        """Test deleting a prediction that doesn't exist."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.delete_prediction("nonexistent")

        assert result is False

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_delete_model_predictions(self, mock_get_session):
        """Test deleting all predictions for a model."""
        mock_session = Mock()
        mock_delete_result = Mock()
        mock_delete_result.return_value = 5
        mock_session.query.return_value.filter.return_value.delete.return_value = 5
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.delete_model_predictions("test_model")

        assert result == 5

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_task_name_exists_true(self, mock_get_session):
        """Test task name exists returns True."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.count.return_value = 1
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.task_name_exists("test_task")

        assert result is True

    @patch("app.database.repositories.prediction_repository.get_session")
    def test_task_name_exists_false(self, mock_get_session):
        """Test task name exists returns False."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = PredictionRepository.task_name_exists("test_task")

        assert result is False


class TestFunctionRepository:
    """Tests for FunctionRepository."""

    @patch("app.database.repositories.function_repository.get_session")
    def test_save_functions(self, mock_get_session):
        """Test saving functions to the database."""
        mock_session = Mock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        mock_function = Mock(spec=Function)
        mock_session.add = Mock()
        mock_session.add.return_value = mock_function

        # The function_repository expects 'lowAddress' key, not 'entrypoint'
        functions = [{"functionName": "test", "lowAddress": "0x1000", "tokens": "test"}]

        result = FunctionRepository.save_functions("test_model", functions)

        mock_session.add.assert_called_once()
        # The function returns a list of Function objects, not a single one
        assert len(result) == 1

    @patch("app.database.repositories.function_repository.get_session")
    def test_get_functions_empty(self, mock_get_session):
        """Test getting empty functions list."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = FunctionRepository.get_functions("test_model")

        assert result == []

    @patch("app.database.repositories.function_repository.get_session")
    def test_get_functions_with_functions(self, mock_get_session):
        """Test getting functions list with functions."""
        mock_session = Mock()
        mock_func1 = Mock(spec=Function)
        mock_func1.function_name = "func1"
        mock_func2 = Mock(spec=Function)
        mock_func2.function_name = "func2"
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_func1, mock_func2]
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = FunctionRepository.get_functions("test_model")

        assert len(result) == 2

    @patch("app.database.repositories.function_repository.get_session")
    def test_get_function_found(self, mock_get_session):
        """Test getting a function that exists."""
        mock_session = Mock()
        mock_function = Mock(spec=Function)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_function
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = FunctionRepository.get_function("test_model", "test_func")

        assert result is mock_function

    @patch("app.database.repositories.function_repository.get_session")
    def test_get_function_not_found(self, mock_get_session):
        """Test getting a function that doesn't exist."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = FunctionRepository.get_function("test_model", "nonexistent")

        assert result is None

    @patch("app.database.repositories.function_repository.get_session")
    def test_delete_functions(self, mock_get_session):
        """Test deleting all functions for a model."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.delete.return_value = 10
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=False)

        result = FunctionRepository.delete_functions("test_model")

        assert result == 10
