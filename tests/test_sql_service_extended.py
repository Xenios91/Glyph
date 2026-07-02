"""Extended tests for SQLUtil to improve coverage above 80%."""

import pickle
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import exc as sa_exc
from app.database.models import Base
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    init_async_databases,
)
from app.database.sql_service import SQLUtil


@pytest.fixture(scope="module", autouse=True)
async def sql_db_lifecycle():
    """Initialize and cleanup in-memory databases for this test module."""
    await init_async_databases()
    for db_name, engine in async_engines.items():
        target_tables = DB_TABLE_MAP.get(db_name)
        if target_tables:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
                await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield
    await dispose_async_engines()


# -----------------------------------------------------------------------
# Error-path tests for existing methods (using mocked session errors)
# -----------------------------------------------------------------------


class TestSQLUtilErrorPaths:
    """Tests for error handling paths in SQLUtil methods."""

    async def test_save_model_rollback_on_error(self):
        """Test that save_model rolls back and raises on session error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB write failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.model_repository.get_async_session", return_value=mock_error):
            with patch("app.database.model_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB write failed"):
                    await SQLUtil.save_model("err_model", b"enc", b"mod")
                mock_error.rollback.assert_awaited_once()

    async def test_get_models_list_catches_error(self):
        """Test that get_models_list catches exceptions and returns empty set."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB read failed"))

        with patch("app.database.model_repository.get_async_session", return_value=mock_error):
            with patch("app.database.model_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.get_models_list()
                assert result == set()

    async def test_get_model_raises_on_error(self):
        """Test that get_model re-raises exceptions after logging."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.model_repository.get_async_session", return_value=mock_error):
            with patch("app.database.model_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_model("err_model")

    async def test_delete_model_rollback_on_error(self):
        """Test that delete_model rolls back and raises on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB delete failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.model_repository.get_async_session", return_value=mock_error):
            with patch("app.database.model_repository.close_async_session", new=AsyncMock()):
                with patch.object(SQLUtil, "delete_model_predictions", new=AsyncMock()):
                    with patch.object(SQLUtil, "delete_functions", new=AsyncMock()):
                        with pytest.raises(Exception, match="DB delete failed"):
                            await SQLUtil.delete_model("err_model")
                        mock_error.rollback.assert_awaited_once()

    async def test_save_predictions_rollback_on_error(self):
        """Test that save_predictions rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB save failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB save failed"):
                    await SQLUtil.save_predictions("task", "model", [{"functionName": "f1"}])
                mock_error.rollback.assert_awaited_once()

    async def test_get_predictions_error(self):
        """Test that get_predictions returns None on deserialization error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB read failed"))

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.get_predictions("task", "model")
                assert result is None

    async def test_delete_functions_rollback_on_error(self):
        """Test that delete_functions rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB del func failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.function_repository.get_async_session", return_value=mock_error):
            with patch("app.database.function_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB del func failed"):
                    await SQLUtil.delete_functions("err_model")
                mock_error.rollback.assert_awaited_once()

    async def test_delete_prediction_rollback_on_error(self):
        """Test that delete_prediction rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB del pred failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB del pred failed"):
                    await SQLUtil.delete_prediction("err_task")
                mock_error.rollback.assert_awaited_once()

    async def test_delete_model_predictions_rollback_on_error(self):
        """Test that delete_model_predictions rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB del model preds failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB del model preds failed"):
                    await SQLUtil.delete_model_predictions("err_model")
                mock_error.rollback.assert_awaited_once()

    async def test_model_name_exists_returns_false_on_error(self):
        """Test that model_name_exists returns False on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB check failed"))

        with patch("app.database.model_repository.get_async_session", return_value=mock_error):
            with patch("app.database.model_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.model_name_exists("err_model")
                assert result is False

    async def test_task_name_exists_returns_false_on_error(self):
        """Test that task_name_exists returns False on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB check failed"))

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.task_name_exists("err_task")
                assert result is False


# -----------------------------------------------------------------------
# Binary operations
# -----------------------------------------------------------------------


class TestSQLUtilBinaryOperations:
    """Tests for Binary-related SQLUtil methods."""

    async def test_save_binary_success(self):
        """Test saving binary metadata successfully."""
        binary_id = await SQLUtil.save_binary(
            name="test_binary",
            file_path="/tmp/test.bin",
            file_size=1024,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        assert isinstance(binary_id, int)
        assert binary_id > 0

    async def test_get_binary_success(self):
        """Test retrieving a binary by id."""
        binary_id = await SQLUtil.save_binary(
            name="get_test_binary",
            file_path="/tmp/get_test.bin",
            file_size=512,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        binary = await SQLUtil.get_binary(binary_id)
        assert binary is not None
        assert binary.name == "get_test_binary"
        assert binary.file_size == 512

    async def test_get_binary_not_found(self):
        """Test retrieving a non-existent binary returns None."""
        binary = await SQLUtil.get_binary(99999)
        assert binary is None

    async def test_get_binary_raises_on_error(self):
        """Test that get_binary raises on DB error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_binary(1)

    async def test_get_binaries_by_user(self):
        """Test listing binaries by user."""
        await SQLUtil.save_binary(
            name="user_binary_1",
            file_path="/tmp/u1.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=42,
        )
        await SQLUtil.save_binary(
            name="user_binary_2",
            file_path="/tmp/u2.bin",
            file_size=200,
            mime_type="application/octet-stream",
            uploaded_by=42,
        )
        binaries = await SQLUtil.get_binaries_by_user(42)
        assert len(binaries) >= 2
        names = [b.name for b in binaries]
        assert "user_binary_1" in names
        assert "user_binary_2" in names

    async def test_get_binaries_by_user_empty(self):
        """Test listing binaries for user with no binaries."""
        binaries = await SQLUtil.get_binaries_by_user(99999)
        assert binaries == []

    async def test_get_binaries_by_user_raises_on_error(self):
        """Test that get_binaries_by_user raises on DB error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_binaries_by_user(1)

    async def test_delete_binary_success(self):
        """Test deleting a binary."""
        binary_id = await SQLUtil.save_binary(
            name="delete_binary",
            file_path="/tmp/del.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        await SQLUtil.delete_binary(binary_id)
        binary = await SQLUtil.get_binary(binary_id)
        assert binary is None

    async def test_delete_binary_rollback_on_error(self):
        """Test that delete_binary rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB del binary failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB del binary failed"):
                    await SQLUtil.delete_binary(1)
                mock_error.rollback.assert_awaited_once()

    async def test_save_binary_functions_success(self):
        """Test saving binary functions."""
        binary_id = await SQLUtil.save_binary(
            name="func_binary",
            file_path="/tmp/func.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        functions = [
            {"function_name": "main", "entrypoint": True, "raw_code": "int main() {}"},
            {"function_name": "helper", "entrypoint": False, "raw_code": "void helper() {}"},
        ]
        await SQLUtil.save_binary_functions(binary_id, functions)

        result = await SQLUtil.get_binary_functions(binary_id)
        assert len(result) == 2
        names = {f.function_name for f in result}
        assert "main" in names
        assert "helper" in names

    async def test_save_binary_functions_upsert(self):
        """Test that save_binary_functions updates existing entries."""
        binary_id = await SQLUtil.save_binary(
            name="upsert_func_binary",
            file_path="/tmp/upsert.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        functions = [
            {"function_name": "main", "entrypoint": True, "raw_code": "v1"},
        ]
        await SQLUtil.save_binary_functions(binary_id, functions)

        functions_v2 = [
            {"function_name": "main", "entrypoint": False, "raw_code": "v2"},
        ]
        await SQLUtil.save_binary_functions(binary_id, functions_v2)

        result = await SQLUtil.get_binary_functions(binary_id)
        assert len(result) == 1
        assert result[0].raw_code == "v2"
        assert result[0].entrypoint == "0"

    async def test_save_binary_functions_rollback_on_error(self):
        """Test that save_binary_functions rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB save funcs failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB save funcs failed"):
                    await SQLUtil.save_binary_functions(
                        1, [{"function_name": "f", "entrypoint": False, "raw_code": "c"}]
                    )
                mock_error.rollback.assert_awaited_once()

    async def test_get_binary_functions_empty(self):
        """Test getting functions for binary with none."""
        binary_id = await SQLUtil.save_binary(
            name="empty_func_binary",
            file_path="/tmp/empty.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        result = await SQLUtil.get_binary_functions(binary_id)
        assert result == []

    async def test_get_binary_functions_raises_on_error(self):
        """Test that get_binary_functions raises on DB error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_binary_functions(1)

    async def test_get_all_binary_ids(self):
        """Test getting all binary ids."""
        await SQLUtil.save_binary(
            name="id_binary_1",
            file_path="/tmp/id1.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        ids = await SQLUtil.get_all_binary_ids()
        assert len(ids) >= 1

    async def test_get_all_binary_ids_raises_on_error(self):
        """Test that get_all_binary_ids raises on DB error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_all_binary_ids()

    async def test_get_binary_name(self):
        """Test getting binary name by id."""
        binary_id = await SQLUtil.save_binary(
            name="named_binary",
            file_path="/tmp/named.bin",
            file_size=100,
            mime_type="application/octet-stream",
            uploaded_by=1,
        )
        name = await SQLUtil.get_binary_name(binary_id)
        assert name == "named_binary"

    async def test_get_binary_name_not_found(self):
        """Test getting name for non-existent binary returns None."""
        name = await SQLUtil.get_binary_name(99999)
        assert name is None

    async def test_get_binary_name_raises_on_error(self):
        """Test that get_binary_name raises on DB error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB query failed"))

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB query failed"):
                    await SQLUtil.get_binary_name(1)

    async def test_save_binary_rollback_on_error(self):
        """Test that save_binary rolls back on error."""
        mock_error = AsyncMock()
        mock_error.add = MagicMock(side_effect=sa_exc.SQLAlchemyError("DB add failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.binary_repository.get_async_session", return_value=mock_error):
            with patch("app.database.binary_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB add failed"):
                    await SQLUtil.save_binary("err", "/tmp/e", 1, "m", 1)
                mock_error.rollback.assert_awaited_once()


# -----------------------------------------------------------------------
# delete_prediction with model_name
# -----------------------------------------------------------------------


class TestSQLUtilDeletePredictionWithModel:
    """Tests for delete_prediction with model_name parameter."""

    async def test_delete_prediction_with_model_name(self):
        """Test deleting prediction with both task_name and model_name."""
        await SQLUtil.save_predictions("del_with_model_task", "del_with_model", [{"functionName": "f1"}])
        await SQLUtil.delete_prediction("del_with_model_task", model_name="del_with_model")
        result = await SQLUtil.get_predictions("del_with_model_task", "del_with_model")
        assert result is None

    async def test_delete_prediction_without_model_name(self):
        """Test deleting prediction with only task_name (legacy behavior)."""
        await SQLUtil.save_predictions("del_without_model_task", "model_a", [{"functionName": "f1"}])
        await SQLUtil.save_predictions("del_without_model_task", "model_b", [{"functionName": "f2"}])
        await SQLUtil.delete_prediction("del_without_model_task")
        result_a = await SQLUtil.get_predictions("del_without_model_task", "model_a")
        result_b = await SQLUtil.get_predictions("del_without_model_task", "model_b")
        assert result_a is None
        assert result_b is None


class TestSQLUtilSimilarityComputation:
    """Tests for similarity computation SQL operations."""

    async def test_create_similarity_computation_success(self):
        """Test creating a new similarity computation record."""
        comp = await SQLUtil.create_similarity_computation("sim_task", 1, 3, "pending")
        assert comp.id is not None
        assert comp.task_name == "sim_task"
        assert comp.computed_by == 1
        assert comp.binary_count == 3
        assert comp.status == "pending"
        assert comp.total_comparisons == 0

    async def test_create_similarity_computation_rollback_on_error(self):
        """Test that create rolls back on error."""
        mock_error = AsyncMock()
        mock_error.add = MagicMock(side_effect=sa_exc.SQLAlchemyError("DB create failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB create failed"):
                    await SQLUtil.create_similarity_computation("fail_task", 1, 2)
                mock_error.rollback.assert_awaited_once()

    async def test_update_similarity_computation_status_success(self):
        """Test updating computation status."""
        comp = await SQLUtil.create_similarity_computation("update_task", 1, 2)
        await SQLUtil.update_similarity_computation_status(comp.id, "running", 100)

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert fetched.status == "running"
        assert fetched.total_comparisons == 100

    async def test_update_similarity_computation_status_not_found(self):
        """Test updating non-existent computation returns silently."""
        await SQLUtil.update_similarity_computation_status(99999, "running")

    async def test_update_similarity_computation_status_rollback_on_error(self):
        """Test that update rolls back on error."""
        mock_error = AsyncMock()
        mock_error.get = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB update failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB update failed"):
                    await SQLUtil.update_similarity_computation_status(1, "running")
                mock_error.rollback.assert_awaited_once()

    async def test_save_similarity_pairs_success(self):
        """Test saving similarity pairs."""
        from app.database.models import SimilarityPair

        comp = await SQLUtil.create_similarity_computation("pairs_task", 1, 2)
        pairs = [
            SimilarityPair(
                binary_a_id=1,
                binary_b_id=2,
                overall_similarity=0.85,
                matched_function_count=5,
                total_function_comparisons=10,
            ),
        ]
        await SQLUtil.save_similarity_pairs(comp.id, pairs)

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert len(fetched.pairs) == 1
        assert fetched.pairs[0].overall_similarity == 0.85

    async def test_save_similarity_pairs_rollback_on_error(self):
        """Test that save pairs rolls back on error."""
        from app.database.models import SimilarityPair

        mock_error = AsyncMock()
        mock_error.add = MagicMock(side_effect=sa_exc.SQLAlchemyError("DB save pairs failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                pairs = [
                    SimilarityPair(
                        binary_a_id=1,
                        binary_b_id=2,
                        overall_similarity=0.5,
                        matched_function_count=3,
                        total_function_comparisons=5,
                    )
                ]
                with pytest.raises(Exception, match="DB save pairs failed"):
                    await SQLUtil.save_similarity_pairs(1, pairs)
                mock_error.rollback.assert_awaited_once()

    async def test_get_similarity_computation_success(self):
        """Test retrieving a similarity computation."""
        comp = await SQLUtil.create_similarity_computation("get_task", 1, 2)
        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert fetched.task_name == "get_task"

    async def test_get_similarity_computation_not_found(self):
        """Test retrieving non-existent computation returns None."""
        result = await SQLUtil.get_similarity_computation(99999)
        assert result is None

    async def test_get_similarity_computation_returns_none_on_error(self):
        """Test that get returns None on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB read failed"))

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.get_similarity_computation(1)
                assert result is None

    async def test_list_similarity_computations_all(self):
        """Test listing all similarity computations."""
        await SQLUtil.create_similarity_computation("list_task_a", 1, 2)
        await SQLUtil.create_similarity_computation("list_task_b", 2, 3)

        comps = await SQLUtil.list_similarity_computations()
        assert len(comps) >= 2

    async def test_list_similarity_computations_filtered(self):
        """Test listing computations filtered by user."""
        comp = await SQLUtil.create_similarity_computation("filter_task", 42, 2)
        comps = await SQLUtil.list_similarity_computations(computed_by=42)
        found = [c for c in comps if c.id == comp.id]
        assert len(found) == 1

    async def test_list_similarity_computations_returns_empty_on_error(self):
        """Test that list returns empty list on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB list failed"))

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                comps = await SQLUtil.list_similarity_computations()
                assert comps == []

    async def test_delete_similarity_computation_success(self):
        """Test deleting a similarity computation."""
        comp = await SQLUtil.create_similarity_computation("del_sim_task", 1, 2)
        await SQLUtil.delete_similarity_computation(comp.id)

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is None

    async def test_delete_similarity_computation_rollback_on_error(self):
        """Test that delete rolls back on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB delete failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.similarity_repository.get_async_session", return_value=mock_error):
            with patch("app.database.similarity_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB delete failed"):
                    await SQLUtil.delete_similarity_computation(1)
                mock_error.rollback.assert_awaited_once()


class TestSQLUtilFunctionErrorPaths:
    """Tests for error paths in get_functions and get_function."""

    async def test_get_functions_returns_empty_on_error(self):
        """Test that get_functions returns empty list on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB read failed"))

        with patch("app.database.function_repository.get_async_session", return_value=mock_error):
            with patch("app.database.function_repository.close_async_session", new=AsyncMock()):
                funcs = await SQLUtil.get_functions("err_model")
                assert funcs == []

    async def test_get_function_returns_none_on_error(self):
        """Test that get_function returns None on error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB read failed"))

        with patch("app.database.function_repository.get_async_session", return_value=mock_error):
            with patch("app.database.function_repository.close_async_session", new=AsyncMock()):
                func = await SQLUtil.get_function("err_model", "main")
                assert func is None


class TestSQLUtilPredictionDeserializationErrors:
    """Tests for prediction deserialization error paths."""

    async def test_get_predictions_list_non_list_data(self):
        """Test get_predictions_list skips predictions with non-list data."""
        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        db_session = await get_async_session("predictions")
        try:
            bad_data = BytesIO()
            pickle.dump({"not": "a list"}, bad_data)
            pred = Prediction(
                task_name="non_list_task",
                model_name="model_a",
                functions_data=bad_data.getvalue(),
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        results = await SQLUtil.get_predictions_list()
        # The non-list prediction should be skipped
        found = [r for r in results if r.task_name == "non_list_task"]
        assert len(found) == 0

    async def test_get_predictions_list_secure_deserialization_error(self):
        """Test get_predictions_list handles SecureDeserializationError."""
        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        # Insert data that will fail secure deserialization (raw bytes)
        db_session = await get_async_session("predictions")
        try:
            pred = Prediction(
                task_name="secure_err_task",
                model_name="model_a",
                functions_data=b"not valid pickle data at all \x80\x80\x00",
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        results = await SQLUtil.get_predictions_list()
        # The bad prediction should be skipped
        found = [r for r in results if r.task_name == "secure_err_task"]
        assert len(found) == 0

    async def test_get_predictions_list_session_error(self):
        """Test get_predictions_list handles session-level errors."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB session failed"))

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                results = await SQLUtil.get_predictions_list()
                assert results == []

    async def test_get_predictions_not_list_data(self):
        """Test get_predictions returns None when data is not a list."""
        import pickle
        from io import BytesIO

        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        db_session = await get_async_session("predictions")
        try:
            bad_data = BytesIO()
            pickle.dump({"not": "a list"}, bad_data)
            pred = Prediction(
                task_name="not_list_pred",
                model_name="model_a",
                functions_data=bad_data.getvalue(),
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        result = await SQLUtil.get_predictions("not_list_pred", "model_a")
        assert result is None

    async def test_get_predictions_general_deserialization_error(self):
        """Test get_predictions returns None on general deserialization error."""
        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        db_session = await get_async_session("predictions")
        try:
            pred = Prediction(
                task_name="gen_err_pred",
                model_name="model_a",
                functions_data=b"\x80\x80\x00\x00 invalid pickle",
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        result = await SQLUtil.get_predictions("gen_err_pred", "model_a")
        assert result is None

    async def test_get_prediction_function_not_list_data(self):
        """Test get_prediction_function returns {} when data is not a list."""
        import pickle
        from io import BytesIO

        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        db_session = await get_async_session("predictions")
        try:
            bad_data = BytesIO()
            pickle.dump({"not": "a list"}, bad_data)
            pred = Prediction(
                task_name="func_not_list",
                model_name="model_a",
                functions_data=bad_data.getvalue(),
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        result = await SQLUtil.get_prediction_function("func_not_list", "model_a", "any_func")
        assert result == {}

    async def test_get_prediction_function_deserialization_error(self):
        """Test get_prediction_function returns {} on deserialization error."""
        from app.database.models import Prediction
        from app.database.session_handler import close_async_session, get_async_session

        db_session = await get_async_session("predictions")
        try:
            pred = Prediction(
                task_name="func_deser_err",
                model_name="model_a",
                functions_data=b"\x80\x80\x00\x00 invalid",
            )
            db_session.add(pred)
            await db_session.commit()
        finally:
            await close_async_session(db_session)

        result = await SQLUtil.get_prediction_function("func_deser_err", "model_a", "any_func")
        assert result == {}

    async def test_get_prediction_function_session_error(self):
        """Test get_prediction_function returns {} on session error."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB session failed"))

        with patch("app.database.prediction_repository.get_async_session", return_value=mock_error):
            with patch("app.database.prediction_repository.close_async_session", new=AsyncMock()):
                result = await SQLUtil.get_prediction_function("task", "model", "func")
                assert result == {}

    async def test_save_functions_error_path(self):
        """Test save_functions error handling."""
        mock_error = AsyncMock()
        mock_error.execute = AsyncMock(side_effect=sa_exc.SQLAlchemyError("DB save failed"))
        mock_error.commit = AsyncMock()
        mock_error.rollback = AsyncMock()

        with patch("app.database.function_repository.get_async_session", return_value=mock_error):
            with patch("app.database.function_repository.close_async_session", new=AsyncMock()):
                with pytest.raises(Exception, match="DB save failed"):
                    await SQLUtil.save_functions(
                        "err_model", [{"functionName": "f", "lowAddress": "0", "tokenList": []}]
                    )
                mock_error.rollback.assert_awaited_once()
