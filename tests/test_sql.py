"""Unit tests for SQL database operations and utilities."""
import os
import sqlite3
import pickle
from unittest.mock import MagicMock, patch, mock_open, create_autospec
import pytest

from app.database.sql_service import SQLUtil
from app.services.request_handler import Prediction


def make_cursor_mock(return_data=None, fetchall_data=None, fetchone_data=None):
    """Create a cursor mock with configurable execute behavior."""
    mock_cur = MagicMock()
    mock_execute_result = MagicMock()

    if fetchall_data is not None:
        mock_execute_result.fetchall.return_value = fetchall_data
    elif return_data is not None:
        mock_execute_result.fetchall.return_value = return_data

    if fetchone_data is not None or fetchone_data is None:
        mock_execute_result.fetchone.return_value = fetchone_data
    elif return_data is not None and return_data:
        mock_execute_result.fetchone.return_value = return_data[0] if isinstance(return_data, list) else return_data

    mock_cur.execute.return_value = mock_execute_result
    return mock_cur


class TestSQLUtilInitDB:
    """Tests for SQLUtil.init_db() method."""

    def test_init_db_creates_tables(self, monkeypatch):
        """Test that init_db creates both database tables."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: False)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.init_db()

        assert mock_connect.call_count == 2
        mock_connect.assert_any_call("models.db")
        mock_connect.assert_any_call("predictions.db")

        executed_queries = [call.args[0] for call in mock_cur.execute.call_args_list]
        assert any("CREATE TABLE IF NOT EXISTS models" in q for q in executed_queries)
        assert any("CREATE TABLE IF NOT EXISTS PREDICTIONS" in q for q in executed_queries)

    def test_init_db_skips_existing_databases(self, monkeypatch):
        """Test that init_db skips creation if databases already exist."""
        mock_connect = MagicMock()
        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.init_db()

        mock_connect.assert_not_called()

    def test_init_db_handles_exception(self, monkeypatch, caplog):
        """Test that init_db handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("DB Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: False)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.init_db()

        assert "DB Error" in caplog.text


class TestSQLUtilSaveModel:
    """Tests for SQLUtil.save_model() method."""

    def test_save_model_success(self, monkeypatch):
        """Test saving a model successfully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.save_model("test_model", b"encoder_data", b"model_data")

        calls = mock_cur.execute.call_args_list
        insert_calls = [c for c in calls if "INSERT" in c[0][0]]
        assert len(insert_calls) == 1

    def test_save_model_handles_exception(self, monkeypatch, caplog):
        """Test that save_model handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Save Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.save_model("test_model", b"encoder", b"model")

        assert "Save Error" in caplog.text


class TestSQLUtilGetModelsList:
    """Tests for SQLUtil.get_models_list() method."""

    def test_get_models_list_success(self, monkeypatch):
        """Test getting list of models."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchall_data=[("model1",), ("model2",)])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_models_list()

        assert result == {"model1", "model2"}

    def test_get_models_list_empty(self, monkeypatch):
        """Test getting empty list when no models exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchall_data=[])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_models_list()

        assert result == set()

    def test_get_models_list_database_not_exists(self, monkeypatch):
        """Test getting empty set when database doesn't exist."""
        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: False)

        result = SQLUtil.get_models_list()

        assert result == set()

    def test_get_models_list_handles_exception(self, monkeypatch, caplog):
        """Test that get_models_list handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Query Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_models_list()

        assert result == set()
        assert "Query Error" in caplog.text


class TestSQLUtilGetModel:
    """Tests for SQLUtil.get_model() method."""

    def test_get_model_success(self, monkeypatch):
        """Test getting a specific model."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=("test_model", b"model_data", b"encoder_data"))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_model("test_model")

        assert result is not None
        assert result[0] == "test_model"

    def test_get_model_not_found(self, monkeypatch, caplog):
        """Test getting a model that doesn't exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=None)

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_model("nonexistent")

        assert result is None
        assert "not found" in caplog.text.lower()

    def test_get_model_database_error(self, monkeypatch, caplog):
        """Test that get_model handles database errors."""
        mock_connect = MagicMock()
        mock_connect.side_effect = sqlite3.Error("Connection failed")

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_model("test_model")

        assert result is None
        assert "Database error" in caplog.text


class TestSQLUtilDeleteModel:
    """Tests for SQLUtil.delete_model() method."""

    def test_delete_model_success(self, monkeypatch):
        """Test deleting a model."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_model("test_model")

        calls = mock_cur.execute.call_args_list
        call_strs = [str(c) for c in calls]
        assert any("DELETE FROM MODELS" in s for s in call_strs)
        assert any("DELETE FROM FUNCTIONS" in s for s in call_strs)

    def test_delete_model_handles_exception(self, monkeypatch, caplog):
        """Test that delete_model handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Delete Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_model("test_model")

        assert "Delete Error" in caplog.text


class TestSQLUtilGetPredictionsList:
    """Tests for SQLUtil.get_predictions_list() method."""

    def test_get_predictions_list_success(self, monkeypatch):
        """Test getting list of predictions."""
        mock_connect = MagicMock()
        mock_con = MagicMock()

        test_pred = [{"functionName": "func1", "prediction": "label1"}]
        serialized = pickle.dumps(test_pred)

        mock_cur = make_cursor_mock(fetchall_data=[("task1", "model1", sqlite3.Binary(serialized))])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_predictions_list()

        assert len(result) == 1
        assert result[0].task_name == "task1"
        assert result[0].model_name == "model1"

    def test_get_predictions_list_empty(self, monkeypatch):
        """Test getting empty list when no predictions exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchall_data=[])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)
        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_predictions_list()

        assert result == []

    def test_get_predictions_list_database_not_exists(self, monkeypatch):
        """Test getting empty list when database doesn't exist."""
        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: False)

        result = SQLUtil.get_predictions_list()

        assert result == []


class TestSQLUtilGetPredictions:
    """Tests for SQLUtil.get_predictions() method."""

    def test_get_predictions_success(self, monkeypatch):
        """Test getting a specific prediction."""
        mock_connect = MagicMock()
        mock_con = MagicMock()

        test_pred = [{"functionName": "func1", "prediction": "label1"}]
        serialized = pickle.dumps(test_pred)

        mock_cur = make_cursor_mock(fetchone_data=("task1", "model1", sqlite3.Binary(serialized)))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)
        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: True)

        result = SQLUtil.get_predictions("task1", "model1")

        assert result is not None
        assert result.task_name == "task1"
        assert result.model_name == "model1"

    def test_get_predictions_not_found(self, monkeypatch):
        """Test getting a prediction that doesn't exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=None)

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_predictions("task1", "model1")

        assert result is None

    def test_get_predictions_database_not_exists(self, monkeypatch, caplog):
        """Test getting prediction when database doesn't exist."""
        monkeypatch.setattr("app.database.sql_service.os.path.exists", lambda path: False)

        result = SQLUtil.get_predictions("task1", "model1")

        assert result is None
        assert "does not exist" in caplog.text.lower()

    def test_get_predictions_pickle_error(self, monkeypatch, caplog):
        """Test handling corrupted pickle data."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=("task1", "model1", sqlite3.Binary(b"corrupted")))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_predictions("task1", "model1")

        assert result is None


class TestSQLUtilSavePredictions:
    """Tests for SQLUtil.save_predictions() method."""

    def test_save_predictions_success(self, monkeypatch):
        """Test saving predictions successfully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        functions = [{"functionName": "func1", "prediction": "label1"}]

        SQLUtil.save_predictions("task1", "model1", functions)

        assert mock_cur.execute.call_count >= 1

    def test_save_predictions_handles_exception(self, monkeypatch, caplog):
        """Test that save_predictions handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Save Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.save_predictions("task1", "model1", [{"func": "f1"}])

        assert "Save Error" in caplog.text


class TestSQLUtilGetPredictionFunction:
    """Tests for SQLUtil.get_prediction_function() method."""

    def test_get_prediction_function_success(self, monkeypatch):
        """Test getting a specific prediction function."""
        mock_connect = MagicMock()
        mock_con = MagicMock()

        test_pred = [{"functionName": "func1", "prediction": "label1", "confidence": 0.95}]
        serialized = pickle.dumps(test_pred)

        mock_cur = make_cursor_mock(fetchone_data=("task1", "model1", sqlite3.Binary(serialized)))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_prediction_function("task1", "model1", "func1")

        assert result == {"functionName": "func1", "prediction": "label1", "confidence": 0.95}

    def test_get_prediction_function_not_found(self, monkeypatch):
        """Test getting a prediction function that doesn't exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()

        test_pred = [{"functionName": "func2", "prediction": "label2"}]
        serialized = pickle.dumps(test_pred)

        mock_cur = make_cursor_mock(fetchone_data=("task1", "model1", sqlite3.Binary(serialized)))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_prediction_function("task1", "model1", "func1")

        assert result == {}


class TestSQLUtilSaveFunctions:
    """Tests for SQLUtil.save_functions() method."""

    def test_save_functions_success(self, monkeypatch):
        """Test saving functions successfully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        functions = [
            {"functionName": "func1", "lowAddress": "0x1000", "tokens": "token1 token2"},
            {"functionName": "func2", "lowAddress": "0x2000", "tokens": "token3 token4"}
        ]

        SQLUtil.save_functions("model1", functions)

        assert mock_cur.execute.call_count >= 2

    def test_save_functions_handles_exception(self, monkeypatch, caplog):
        """Test that save_functions handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Save Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.save_functions("model1", [{"functionName": "f1", "lowAddress": "0x0", "tokens": "t"}])

        assert "Save Error" in caplog.text


class TestSQLUtilGetFunctions:
    """Tests for SQLUtil.get_functions() method."""

    def test_get_functions_success(self, monkeypatch):
        """Test getting functions for a model."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchall_data=[
            ("model1", "func1", "0x1000", "tokens1"),
            ("model1", "func2", "0x2000", "tokens2")
        ])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_functions("model1")

        assert len(result) == 2

    def test_get_functions_empty(self, monkeypatch):
        """Test getting empty list when no functions exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchall_data=[])

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_functions("model1")

        assert result == []


class TestSQLUtilGetFunction:
    """Tests for SQLUtil.get_function() method."""

    def test_get_function_success(self, monkeypatch):
        """Test getting a specific function."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=("model1", "func1", "0x1000", "tokens"))

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_function("model1", "func1")

        assert result is not None
        assert result[0] == "model1"
        assert result[1] == "func1"

    def test_get_function_not_found(self, monkeypatch):
        """Test getting a function that doesn't exist."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock(fetchone_data=None)

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        result = SQLUtil.get_function("model1", "func1")

        assert result is None


class TestSQLUtilDeleteFunctions:
    """Tests for SQLUtil.delete_functions() method."""

    def test_delete_functions_success(self, monkeypatch):
        """Test deleting functions for a model."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_functions("model1")

        calls = mock_cur.execute.call_args_list
        assert any("DELETE FROM FUNCTIONS" in str(c) for c in calls)

    def test_delete_functions_handles_exception(self, monkeypatch, caplog):
        """Test that delete_functions handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Delete Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_functions("model1")

        assert "Delete Error" in caplog.text


class TestSQLUtilDeletePrediction:
    """Tests for SQLUtil.delete_prediction() method."""

    def test_delete_prediction_success(self, monkeypatch):
        """Test deleting a prediction."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_prediction("task1")

        calls = mock_cur.execute.call_args_list
        assert any("DELETE FROM PREDICTIONS" in str(c) for c in calls)

    def test_delete_prediction_handles_exception(self, monkeypatch, caplog):
        """Test that delete_prediction handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Delete Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_prediction("task1")

        assert "Delete Error" in caplog.text


class TestSQLUtilDeleteModelPredictions:
    """Tests for SQLUtil.delete_model_predictions() method."""

    def test_delete_model_predictions_success(self, monkeypatch):
        """Test deleting all predictions for a model."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = make_cursor_mock()

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_model_predictions("model1")

        calls = mock_cur.execute.call_args_list
        assert any("DELETE FROM PREDICTIONS" in str(c) for c in calls)

    def test_delete_model_predictions_handles_exception(self, monkeypatch, caplog):
        """Test that delete_model_predictions handles exceptions gracefully."""
        mock_connect = MagicMock()
        mock_con = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = sqlite3.Error("Delete Error")

        mock_connect.return_value.__enter__.return_value = mock_con
        mock_con.cursor.return_value = mock_cur

        monkeypatch.setattr("app.database.sql_service.sqlite3.connect", mock_connect)

        SQLUtil.delete_model_predictions("model1")

        assert "Delete Error" in caplog.text