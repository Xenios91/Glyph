"""Tests for dangerous functions API v1 endpoints."""

from typing import Any

from unittest.mock import Mock, patch, AsyncMock

import pytest

from app.auth.dependencies import get_current_active_user
from tests.conftest import set_dependency_override
from tests.factories import make_mock_user


# ---------------------------------------------------------------------------
# GET /catalog tests
# ---------------------------------------------------------------------------

class TestGetCatalog:
    """Tests for GET /catalog endpoint."""

    def test_get_full_catalog(self, dangerous_functions_client: Any) -> None:
        """Test retrieving full catalog without category filter."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "entries" in data["data"]
        assert "categories" in data["data"]
        assert len(data["data"]["entries"]) > 0
        assert len(data["data"]["categories"]) > 0

    def test_catalog_entry_structure(self, dangerous_functions_client: Any) -> None:
        """Test that catalog entries have correct structure."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog")
        data = response.json()
        entries = data["data"]["entries"]
        assert len(entries) > 0
        entry = entries[0]
        assert "name" in entry
        assert "category" in entry
        assert "severity" in entry
        assert "cwe" in entry
        assert "description" in entry
        assert "safe_alternative" in entry

    def test_catalog_categories(self, dangerous_functions_client: Any) -> None:
        """Test that categories list includes expected values."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog")
        data = response.json()
        categories = data["data"]["categories"]
        assert "Buffer Overflow" in categories
        assert "Format String" in categories

    def test_get_catalog_by_category(self, dangerous_functions_client: Any) -> None:
        """Test filtering catalog by category."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog?category=Buffer Overflow")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        entries = data["data"]["entries"]
        assert len(entries) > 0
        for entry in entries:
            assert entry["category"] == "Buffer Overflow"

    def test_get_catalog_by_unknown_category(self, dangerous_functions_client: Any) -> None:
        """Test filtering by unknown category returns empty list."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog?category=Nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["entries"] == []


# ---------------------------------------------------------------------------
# GET /catalog/{function_name} tests
# ---------------------------------------------------------------------------

class TestGetCatalogEntry:
    """Tests for GET /catalog/{function_name} endpoint."""

    def test_get_existing_entry(self, dangerous_functions_client: Any) -> None:
        """Test retrieving existing catalog entry."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog/strcpy")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "strcpy"
        assert data["data"]["category"] == "Buffer Overflow"

    def test_get_nonexistent_entry(self, dangerous_functions_client: Any) -> None:
        """Test retrieving nonexistent entry returns error response."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog/safe_function_xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]["message"].lower()

    def test_get_entry_case_insensitive(self, dangerous_functions_client: Any) -> None:
        """Test catalog lookup is case-insensitive."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog/STRCPY")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "strcpy"

    def test_entry_response_structure(self, dangerous_functions_client: Any) -> None:
        """Test entry response has all required fields."""
        response = dangerous_functions_client.get("/dangerous-functions/catalog/gets")
        data = response.json()
        entry = data["data"]
        assert entry["name"] == "gets"
        assert entry["severity"] == "Critical"
        assert "CWE" in entry["cwe"]
        assert len(entry["description"]) > 0
        assert len(entry["safe_alternative"]) > 0


# ---------------------------------------------------------------------------
# GET /available-models tests
# ---------------------------------------------------------------------------

class TestGetAvailableModels:
    """Tests for GET /available-models endpoint."""

    def test_get_available_models(self, dangerous_functions_client: Any) -> None:
        """Test retrieving available models and prediction tasks."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred:
            mock_ml.get_models_list = AsyncMock(return_value=["model_a", "model_b"])
            mock_prediction = Mock()
            mock_prediction.task_name = "task_1"
            mock_pred.get_predictions_list = AsyncMock(return_value=[mock_prediction])

            response = dangerous_functions_client.get("/dangerous-functions/available-models")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "model_a" in data["data"]["models"]
            assert "model_b" in data["data"]["models"]
            assert "task_1" in data["data"]["prediction_tasks"]

    def test_get_available_models_empty(self, dangerous_functions_client: Any) -> None:
        """Test empty models and predictions list."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred:
            mock_ml.get_models_list = AsyncMock(return_value=[])
            mock_pred.get_predictions_list = AsyncMock(return_value=[])

            response = dangerous_functions_client.get("/dangerous-functions/available-models")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["models"] == []
            assert data["data"]["prediction_tasks"] == []

    def test_get_available_models_no_auth(self, dangerous_functions_client: Any) -> None:
        """Test that endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException
        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.get("/dangerous-functions/available-models")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /scan tests
# ---------------------------------------------------------------------------

class TestScanEndpoint:
    """Tests for POST /scan endpoint."""

    def _make_mock_function(self, name: str, entrypoint: str = "0x401000", tokens: str = "") -> Mock:
        """Create a mock Function ORM object."""
        func = Mock()
        func.function_name = name
        func.entrypoint = entrypoint
        func.tokens = tokens
        return func

    def test_scan_missing_target(self, dangerous_functions_client: Any) -> None:
        """Test scan with neither modelName nor taskName returns 400."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        response = dangerous_functions_client.post(
            "/dangerous-functions/scan",
            json={},
        )
        assert response.status_code == 400
        assert "modelName" in response.json()["detail"] or "taskName" in response.json()["detail"]

    def test_scan_model_not_found(self, dangerous_functions_client: Any) -> None:
        """Test scan with nonexistent model returns 404."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml:
            mock_ml.exists = AsyncMock(return_value=False)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "nonexistent_model"},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_scan_task_not_found(self, dangerous_functions_client: Any) -> None:
        """Test scan with nonexistent task returns 404."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred:
            mock_pred.get_predictions_list = AsyncMock(return_value=[])

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"taskName": "nonexistent_task"},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_scan_model_no_functions(self, dangerous_functions_client: Any) -> None:
        """Test scan of model with no functions returns empty report."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=[])

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "empty_model"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_functions_scanned"] == 0
            assert data["data"]["total_found"] == 0

    def test_scan_model_with_dangerous_functions(self, dangerous_functions_client: Any) -> None:
        """Test scan detects dangerous functions in model."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("vuln_func1", "0x401000", "char buf[100]; strcpy(buf, src);"),
            self._make_mock_function("vuln_func2", "0x402000", "char buf[64]; gets(buf);"),
            self._make_mock_function("safe_func", "0x403000", "int x = 5; return x;"),
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            report = data["data"]
            assert report["model_name"] == "test_model"
            assert report["total_functions_scanned"] == 3
            assert report["total_found"] >= 2  # strcpy and gets
            assert report["critical_count"] >= 1  # gets is Critical
            assert report["high_count"] >= 1  # strcpy is High

    def test_scan_report_structure(self, dangerous_functions_client: Any) -> None:
        """Test scan report has correct structure."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("sprintf", "0x401000", "sprintf(buf, fmt, arg);"),
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            report = data["data"]
            # Check report fields
            assert "model_name" in report
            assert "total_functions_scanned" in report
            assert "total_found" in report
            assert "critical_count" in report
            assert "high_count" in report
            assert "medium_count" in report
            assert "low_count" in report
            assert "results" in report

    def test_scan_result_structure(self, dangerous_functions_client: Any) -> None:
        """Test individual scan results have correct structure."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("my_func", "0xDEADBEEF", "strcpy(dst, src); return 0;"),
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            assert len(results) >= 1
            result = results[0]
            assert "function_name" in result
            assert "containing_function" in result
            assert "entrypoint" in result
            assert "category" in result
            assert "severity" in result
            assert "cwe" in result
            assert "description" in result
            assert "safe_alternative" in result
            assert "usage_context" in result

    def test_scan_preserves_entrypoint(self, dangerous_functions_client: Any) -> None:
        """Test that memory address is preserved in results."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("my_wrapper", "0xCAFE0000", "gets(buf);"),
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            assert len(results) >= 1
            assert results[0]["entrypoint"] == "0xCAFE0000"

    def test_scan_results_sorted_by_severity(self, dangerous_functions_client: Any) -> None:
        """Test that results are sorted by severity (Critical first)."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("f1", "0x401000", "sprintf(buf, fmt);"),  # High
            self._make_mock_function("f2", "0x402000", "gets(buf);"),  # Critical
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            severities = [r["severity"] for r in results]
            if "Critical" in severities and "High" in severities:
                assert severities.index("Critical") < severities.index("High")

    def test_scan_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that scan endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException
        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.post(
            "/dangerous-functions/scan",
            json={"modelName": "test_model"},
        )
        assert response.status_code == 401

    def test_scan_by_task_name(self, dangerous_functions_client: Any) -> None:
        """Test scanning by prediction task name."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        # Create mock prediction with pickled function data
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"

        # Create pickled function data
        import pickle
        func_data: list[dict[str, str | list[str]]] = [
            {"functionName": "my_func", "lowAddress": "0x401000", "tokenList": ["strcpy(buf, src);"]},
        ]
        mock_prediction.functions_data = pickle.dumps(func_data)

        with patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred:
            mock_pred.get_predictions_list = AsyncMock(return_value=[mock_prediction])

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"taskName": "test_task"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_found"] >= 1

    def test_scan_model_and_task_preference(self, dangerous_functions_client: Any) -> None:
        """Test that modelName takes precedence when both provided."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("strcpy", "0x401000", "strcpy(buf, src);"),
        ]

        with patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml, \
             patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func:
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model", "taskName": "test_task"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["model_name"] == "test_model"
