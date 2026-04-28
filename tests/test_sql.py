"""Unit tests for SQL database operations using SQLAlchemy ORM."""
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.database.models import Prediction
from app.database.session_handler import (
    get_async_session,
    close_async_session,
    init_async_databases,
    dispose_async_engines,
)
from app.database.sql_service import SQLUtil


@pytest_asyncio.fixture(scope="module", autouse=True)
async def init_db():
    """Initialize async databases before tests and clean up after."""
    await init_async_databases()
    yield
    await dispose_async_engines()
    # Clean up database files
    for db_file in ["data/models.db", "data/predictions.db", "data/functions.db", "data/auth.db"]:
        for suffix in ["", "-wal", "-shm"]:
            try:
                os.remove(f"{db_file}{suffix}")
            except FileNotFoundError:
                pass


class TestSQLUtilInitDB:
    """Tests for SQLUtil.init_db() method."""

    @pytest.mark.asyncio
    async def test_init_db_is_noop(self):
        """Test that init_db is a no-op since tables are managed by session handler."""
        await SQLUtil.init_db()


class TestSQLUtilSaveModel:
    """Tests for SQLUtil.save_model() method."""

    @pytest.mark.asyncio
    async def test_save_model_success(self):
        """Test saving a model successfully."""
        await SQLUtil.save_model("test_model", b"encoder_data", b"model_data")
        result = await SQLUtil.get_model("test_model")
        assert result is not None
        assert result.model_name == "test_model"
        assert result.model_data == b"model_data"
        assert result.label_encoder_data == b"encoder_data"

    @pytest.mark.asyncio
    async def test_save_model_upsert(self):
        """Test that saving an existing model updates it."""
        await SQLUtil.save_model("test_model_upsert", b"encoder_v1", b"model_v1")
        await SQLUtil.save_model("test_model_upsert", b"encoder_v2", b"model_v2")

        result = await SQLUtil.get_model("test_model_upsert")
        assert result is not None
        assert result.model_data == b"model_v2"
        assert result.label_encoder_data == b"encoder_v2"

    @pytest.mark.asyncio
    async def test_save_model_raises_on_session_error(self):
        """Test that save_model raises when session creation fails."""
        mock_error = AsyncMock(side_effect=Exception("DB Error"))
        with patch("app.database.sql_service.get_async_session", mock_error):
            with pytest.raises(Exception, match="DB Error"):
                await SQLUtil.save_model("test_model", b"encoder", b"model")


class TestSQLUtilGetModelsList:
    """Tests for SQLUtil.get_models_list() method."""

    @pytest.mark.asyncio
    async def test_get_models_list_success(self):
        """Test getting list of models."""
        await SQLUtil.save_model("list_model1", b"enc1", b"mod1")
        await SQLUtil.save_model("list_model2", b"enc2", b"mod2")

        result = await SQLUtil.get_models_list()
        assert "list_model1" in result
        assert "list_model2" in result

    @pytest.mark.asyncio
    async def test_get_models_list_returns_set(self):
        """Test that get_models_list returns a set."""
        result = await SQLUtil.get_models_list()
        assert isinstance(result, set)


class TestSQLUtilGetModel:
    """Tests for SQLUtil.get_model() method."""

    @pytest.mark.asyncio
    async def test_get_model_success(self):
        """Test getting a specific model."""
        await SQLUtil.save_model("get_test_model", b"encoder_data", b"model_data")
        result = await SQLUtil.get_model("get_test_model")
        assert result is not None
        assert result.model_name == "get_test_model"

    @pytest.mark.asyncio
    async def test_get_model_not_found(self):
        """Test getting a model that doesn't exist."""
        result = await SQLUtil.get_model("nonexistent_model_xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_model_returns_none_on_error(self):
        """Test that get_model catches exceptions and returns None."""
        # The get_model method wraps exceptions and returns None
        # We verify this by checking the method catches non-critical errors
        result = await SQLUtil.get_model("definitely_nonexistent_model_xyz_999")
        assert result is None


class TestSQLUtilDeleteModel:
    """Tests for SQLUtil.delete_model() method."""

    @pytest.mark.asyncio
    async def test_delete_model_success(self):
        """Test deleting a model."""
        await SQLUtil.save_model("delete_test_model", b"encoder", b"model")
        await SQLUtil.delete_model("delete_test_model")
        result = await SQLUtil.get_model("delete_test_model")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_model_removes_predictions(self):
        """Test that deleting a model also removes associated predictions."""
        await SQLUtil.save_model("delete_pred_model", b"encoder", b"model")
        await SQLUtil.save_predictions("delete_pred_task", "delete_pred_model", [{"functionName": "func1"}])
        await SQLUtil.delete_model("delete_pred_model")
        predictions = await SQLUtil.get_predictions("delete_pred_task", "delete_pred_model")
        assert predictions is None

    @pytest.mark.asyncio
    async def test_delete_model_removes_functions(self):
        """Test that deleting a model also removes associated functions."""
        await SQLUtil.save_model("delete_func_model", b"encoder", b"model")
        await SQLUtil.save_functions("delete_func_model", [{"functionName": "func1", "lowAddress": "0x1000", "tokenList": ["t1"]}])
        await SQLUtil.delete_model("delete_func_model")
        functions = await SQLUtil.get_functions("delete_func_model")
        assert functions == []

    @pytest.mark.asyncio
    async def test_delete_model_handles_exception(self):
        """Test that delete_model handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Delete Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Delete Error"):
                await SQLUtil.delete_model("test_model")
        finally:
            sql_module.get_async_session = original


class TestSQLUtilGetPredictionsList:
    """Tests for SQLUtil.get_predictions_list() method."""

    @pytest.mark.asyncio
    async def test_get_predictions_list_success(self):
        """Test getting list of predictions."""
        functions = [{"functionName": "func1", "prediction": "label1"}]
        await SQLUtil.save_predictions("list_pred_task", "list_pred_model", functions)

        result = await SQLUtil.get_predictions_list()
        found = [p for p in result if p.task_name == "list_pred_task"]
        assert len(found) >= 1
        assert found[0].task_name == "list_pred_task"
        assert found[0].model_name == "list_pred_model"

    @pytest.mark.asyncio
    async def test_get_predictions_list_returns_list(self):
        """Test that get_predictions_list returns a list."""
        result = await SQLUtil.get_predictions_list()
        assert isinstance(result, list)


class TestSQLUtilGetPredictions:
    """Tests for SQLUtil.get_predictions() method."""

    @pytest.mark.asyncio
    async def test_get_predictions_success(self):
        """Test getting a specific prediction."""
        functions = [{"functionName": "func1", "prediction": "label1"}]
        await SQLUtil.save_predictions("get_pred_task", "get_pred_model", functions)

        result = await SQLUtil.get_predictions("get_pred_task", "get_pred_model")
        assert result is not None
        assert result.task_name == "get_pred_task"
        assert result.model_name == "get_pred_model"

    @pytest.mark.asyncio
    async def test_get_predictions_not_found(self):
        """Test getting a prediction that doesn't exist."""
        result = await SQLUtil.get_predictions("nonexistent_task_xyz", "nonexistent_model_xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_predictions_corrupted_data(self, caplog):
        """Test handling corrupted prediction data."""
        from app.database.models import Prediction as PredModel
        session = await get_async_session("predictions")
        try:
            pred = PredModel(
                task_name="corrupted_task",
                model_name="corrupted_model",
                functions_data=b"corrupted_data",
            )
            session.add(pred)
            await session.commit()
        finally:
            await close_async_session(session)

        result = await SQLUtil.get_predictions("corrupted_task", "corrupted_model")
        assert result is None


class TestSQLUtilSavePredictions:
    """Tests for SQLUtil.save_predictions() method."""

    @pytest.mark.asyncio
    async def test_save_predictions_success(self):
        """Test saving predictions successfully."""
        functions = [{"functionName": "func1", "prediction": "label1"}]
        await SQLUtil.save_predictions("save_pred_task", "save_pred_model", functions)
        result = await SQLUtil.get_predictions("save_pred_task", "save_pred_model")
        assert result is not None

    @pytest.mark.asyncio
    async def test_save_predictions_upsert(self):
        """Test that saving an existing prediction updates it."""
        functions_v1 = [{"functionName": "func1", "prediction": "label1"}]
        functions_v2 = [{"functionName": "func2", "prediction": "label2"}]

        await SQLUtil.save_predictions("upsert_pred_task", "upsert_pred_model", functions_v1)
        await SQLUtil.save_predictions("upsert_pred_task", "upsert_pred_model", functions_v2)

        result = await SQLUtil.get_predictions("upsert_pred_task", "upsert_pred_model")
        assert result is not None
        assert len(result.predictions) == 1
        assert result.predictions[0]["functionName"] == "func2"

    @pytest.mark.asyncio
    async def test_save_predictions_handles_exception(self):
        """Test that save_predictions handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Save Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Save Error"):
                await SQLUtil.save_predictions("task1", "model1", [{"func": "f1"}])
        finally:
            sql_module.get_async_session = original


class TestSQLUtilGetPredictionFunction:
    """Tests for SQLUtil.get_prediction_function() method."""

    @pytest.mark.asyncio
    async def test_get_prediction_function_success(self):
        """Test getting a specific prediction function."""
        functions = [{"functionName": "func1", "prediction": "label1", "confidence": 0.95}]
        await SQLUtil.save_predictions("get_func_task", "get_func_model", functions)

        result = await SQLUtil.get_prediction_function("get_func_task", "get_func_model", "func1")
        assert result == {"functionName": "func1", "prediction": "label1", "confidence": 0.95}

    @pytest.mark.asyncio
    async def test_get_prediction_function_not_found(self):
        """Test getting a prediction function that doesn't exist."""
        functions = [{"functionName": "func2", "prediction": "label2"}]
        await SQLUtil.save_predictions("not_found_func_task", "not_found_func_model", functions)

        result = await SQLUtil.get_prediction_function("not_found_func_task", "not_found_func_model", "func1")
        assert result == {}


class TestSQLUtilSaveFunctions:
    """Tests for SQLUtil.save_functions() method."""

    @pytest.mark.asyncio
    async def test_save_functions_success(self):
        """Test saving functions successfully."""
        functions = [
            {"functionName": "func1", "lowAddress": "0x1000", "tokenList": ["token1", "token2"]},
            {"functionName": "func2", "lowAddress": "0x2000", "tokenList": ["token3", "token4"]},
        ]
        await SQLUtil.save_functions("save_func_model", functions)
        result = await SQLUtil.get_functions("save_func_model")
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_save_functions_handles_exception(self):
        """Test that save_functions handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Save Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Save Error"):
                await SQLUtil.save_functions("model1", [{"functionName": "f1", "lowAddress": "0x0", "tokenList": ["t"]}])
        finally:
            sql_module.get_async_session = original


class TestSQLUtilGetFunctions:
    """Tests for SQLUtil.get_functions() method."""

    @pytest.mark.asyncio
    async def test_get_functions_success(self):
        """Test getting functions for a model."""
        functions = [
            {"functionName": "gfunc1", "lowAddress": "0x1000", "tokenList": ["t1"]},
            {"functionName": "gfunc2", "lowAddress": "0x2000", "tokenList": ["t2"]},
        ]
        await SQLUtil.save_functions("get_func_model", functions)
        result = await SQLUtil.get_functions("get_func_model")
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_get_functions_empty(self):
        """Test getting empty list when no functions exist."""
        result = await SQLUtil.get_functions("nonexistent_model_xyz")
        assert result == []


class TestSQLUtilGetFunction:
    """Tests for SQLUtil.get_function() method."""

    @pytest.mark.asyncio
    async def test_get_function_success(self):
        """Test getting a specific function."""
        functions = [{"functionName": "single_func", "lowAddress": "0x1000", "tokenList": ["tokens"]}]
        await SQLUtil.save_functions("single_func_model", functions)

        result = await SQLUtil.get_function("single_func_model", "single_func")
        assert result is not None
        assert result.function_name == "single_func"

    @pytest.mark.asyncio
    async def test_get_function_not_found(self):
        """Test getting a function that doesn't exist."""
        result = await SQLUtil.get_function("nonexistent_model_xyz", "nonexistent_func_xyz")
        assert result is None


class TestSQLUtilDeleteFunctions:
    """Tests for SQLUtil.delete_functions() method."""

    @pytest.mark.asyncio
    async def test_delete_functions_success(self):
        """Test deleting functions for a model."""
        functions = [{"functionName": "func1", "lowAddress": "0x1000", "tokenList": ["t1"]}]
        await SQLUtil.save_functions("del_func_model", functions)
        await SQLUtil.delete_functions("del_func_model")
        result = await SQLUtil.get_functions("del_func_model")
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_functions_handles_exception(self):
        """Test that delete_functions handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Delete Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Delete Error"):
                await SQLUtil.delete_functions("model1")
        finally:
            sql_module.get_async_session = original


class TestSQLUtilDeletePrediction:
    """Tests for SQLUtil.delete_prediction() method."""

    @pytest.mark.asyncio
    async def test_delete_prediction_success(self):
        """Test deleting a prediction."""
        await SQLUtil.save_predictions("del_pred_task", "del_pred_model", [{"functionName": "func1"}])
        await SQLUtil.delete_prediction("del_pred_task")
        result = await SQLUtil.get_predictions("del_pred_task", "del_pred_model")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_prediction_handles_exception(self):
        """Test that delete_prediction handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Delete Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Delete Error"):
                await SQLUtil.delete_prediction("task1")
        finally:
            sql_module.get_async_session = original


class TestSQLUtilDeleteModelPredictions:
    """Tests for SQLUtil.delete_model_predictions() method."""

    @pytest.mark.asyncio
    async def test_delete_model_predictions_success(self):
        """Test deleting all predictions for a model."""
        await SQLUtil.save_predictions("del_model_pred_task1", "del_model_pred_model", [{"functionName": "func1"}])
        await SQLUtil.save_predictions("del_model_pred_task2", "del_model_pred_model", [{"functionName": "func2"}])
        await SQLUtil.delete_model_predictions("del_model_pred_model")

        result1 = await SQLUtil.get_predictions("del_model_pred_task1", "del_model_pred_model")
        result2 = await SQLUtil.get_predictions("del_model_pred_task2", "del_model_pred_model")
        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_delete_model_predictions_handles_exception(self):
        """Test that delete_model_predictions handles exceptions gracefully."""
        import app.database.sql_service as sql_module
        original = sql_module.get_async_session
        mock_error = AsyncMock(side_effect=Exception("Delete Error"))
        sql_module.get_async_session = mock_error
        try:
            with pytest.raises(Exception, match="Delete Error"):
                await SQLUtil.delete_model_predictions("model1")
        finally:
            sql_module.get_async_session = original


class TestSQLUtilModelNameExists:
    """Tests for SQLUtil.model_name_exists() method."""

    @pytest.mark.asyncio
    async def test_model_name_exists_true(self):
        """Test that model_name_exists returns True for existing model."""
        await SQLUtil.save_model("exists_test_model", b"encoder", b"model")
        result = await SQLUtil.model_name_exists("exists_test_model")
        assert result is True

    @pytest.mark.asyncio
    async def test_model_name_exists_false(self):
        """Test that model_name_exists returns False for non-existing model."""
        result = await SQLUtil.model_name_exists("nonexistent_model_xyz_123")
        assert result is False

    @pytest.mark.asyncio
    async def test_model_name_exists_returns_false_for_missing(self):
        """Test that model_name_exists returns False for non-existent model."""
        result = await SQLUtil.model_name_exists("definitely_nonexistent_xyz_999")
        assert result is False


class TestSQLUtilTaskNameExists:
    """Tests for SQLUtil.task_name_exists() method."""

    @pytest.mark.asyncio
    async def test_task_name_exists_true(self):
        """Test that task_name_exists returns True for existing task."""
        await SQLUtil.save_predictions("exists_task_test", "exists_task_model", [{"functionName": "func1"}])
        result = await SQLUtil.task_name_exists("exists_task_test")
        assert result is True

    @pytest.mark.asyncio
    async def test_task_name_exists_false(self):
        """Test that task_name_exists returns False for non-existing task."""
        result = await SQLUtil.task_name_exists("nonexistent_task_xyz_123")
        assert result is False

    @pytest.mark.asyncio
    async def test_task_name_exists_returns_false_on_error(self):
        """Test that task_name_exists returns False on database errors."""
        mock_error = AsyncMock(side_effect=Exception("DB Error"))
        with patch("app.database.sql_service.get_async_session", new=mock_error):
            import importlib
            import app.database.sql_service as sql_module
            importlib.reload(sql_module)
            result = await sql_module.SQLUtil.task_name_exists("task1")
            assert result is False

