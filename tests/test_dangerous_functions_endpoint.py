"""Tests for dangerous functions API v1 endpoints."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from app.auth.dependencies import get_current_active_user
from app.config.settings import LLMConfig
from app.database.models import LLMAnalysisResult
from app.services.llm_analysis_service import FindingAnalysis
from sqlalchemy.exc import SQLAlchemyError
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.PredictionRepository") as mock_pred,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
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

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func,
        ):
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)

            response = dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model", "taskName": "test_task"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["model_name"] == "test_model"


# ---------------------------------------------------------------------------
# POST /llm-analysis tests
# ---------------------------------------------------------------------------


class TestLLMAnalysisEndpoint:
    """Tests for POST /llm-analysis endpoint."""

    @staticmethod
    def _make_finding(function_name: str, entrypoint: str = "0x401000") -> dict[str, Any]:
        return {
            "function_name": function_name,
            "containing_function": "main",
            "entrypoint": entrypoint,
            "category": "Buffer Overflow",
            "severity": "High",
            "cwe": "CWE-120",
            "description": "Unbounded copy",
            "safe_alternative": "strlcpy",
            "usage_context": ["strcpy(buf, src);"],
            "containing_function_code": "void main() { strcpy(buf, src); }",
        }

    @staticmethod
    def _make_llm(enabled: bool = True) -> Any:
        return LLMConfig(
            enabled=enabled,
            base_url="https://llm.example.com",
            model="test-model",
            api_key="test-key",
        )

    def test_llm_analysis_success(self, dangerous_functions_client: Any) -> None:
        """Test successful analysis with results persisted by default."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        analyses = [
            FindingAnalysis(status="success", analysis="Low risk.", model="test-model", elapsed_ms=12),
            FindingAnalysis(status="error", error="Request timed out", model="", elapsed_ms=1200),
        ]
        findings = [self._make_finding("strcpy"), self._make_finding("system", "0x402000")]

        with (
            patch(
                "app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
                new=AsyncMock(return_value=self._make_llm()),
            ),
            patch(
                "app.api.v1.endpoints.dangerous_functions.analyze_findings",
                new=AsyncMock(return_value=analyses),
            ) as mock_analyze,
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_repo,
        ):
            mock_repo.upsert_many = AsyncMock()

            response = dangerous_functions_client.post(
                "/dangerous-functions/llm-analysis",
                json={"target_name": "test_model", "findings": findings},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["target_name"] == "test_model"
        assert payload["model"] == "test-model"
        assert payload["total"] == 2
        assert payload["succeeded"] == 1
        assert payload["failed"] == 1
        assert payload["saved"] is True
        assert set(payload["results"].keys()) == {"0", "1"}
        assert payload["results"]["0"] == {
            "status": "success",
            "analysis": "Low risk.",
            "error": "",
            "model": "test-model",
            "elapsed_ms": 12,
        }
        assert payload["results"]["1"]["status"] == "error"
        assert payload["results"]["1"]["error"] == "Request timed out"
        assert data["message"] == "LLM analysis complete: 1/2 succeeded"

        # The service received the findings as dumped dicts, in order.
        passed_findings = mock_analyze.await_args_list[0].args[1]
        assert passed_findings[0]["function_name"] == "strcpy"
        assert passed_findings[1]["entrypoint"] == "0x402000"

        # One upserted row per finding, error row included.
        assert mock_repo.upsert_many.await_count == 1
        target_name, rows = mock_repo.upsert_many.await_args_list[0].args
        assert target_name == "test_model"
        assert len(rows) == 2
        assert all(isinstance(row, LLMAnalysisResult) for row in rows)
        assert rows[0].function_name == "strcpy"
        assert rows[0].containing_function == "main"
        assert rows[0].entrypoint == "0x401000"
        assert rows[0].status == "success"
        assert rows[0].analysis == "Low risk."
        assert rows[0].model_name == "test-model"
        assert rows[1].function_name == "system"
        assert rows[1].status == "error"
        assert rows[1].analysis == ""
        assert rows[1].error == "Request timed out"

    def test_llm_analysis_save_false(self, dangerous_functions_client: Any) -> None:
        """Test that save=false skips persistence."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        analyses = [FindingAnalysis(status="success", analysis="ok", model="test-model", elapsed_ms=5)]

        with (
            patch(
                "app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
                new=AsyncMock(return_value=self._make_llm()),
            ),
            patch(
                "app.api.v1.endpoints.dangerous_functions.analyze_findings",
                new=AsyncMock(return_value=analyses),
            ),
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_repo,
        ):
            mock_repo.upsert_many = AsyncMock()

            response = dangerous_functions_client.post(
                "/dangerous-functions/llm-analysis",
                json={"target_name": "test_model", "save": False, "findings": [self._make_finding("strcpy")]},
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["saved"] is False
        mock_repo.upsert_many.assert_not_awaited()

    def test_llm_analysis_upsert_failure(self, dangerous_functions_client: Any) -> None:
        """Test that a persistence failure reports saved=false but the request still succeeds."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        analyses = [FindingAnalysis(status="success", analysis="ok", model="test-model", elapsed_ms=5)]

        with (
            patch(
                "app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
                new=AsyncMock(return_value=self._make_llm()),
            ),
            patch(
                "app.api.v1.endpoints.dangerous_functions.analyze_findings",
                new=AsyncMock(return_value=analyses),
            ),
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_repo,
        ):
            mock_repo.upsert_many = AsyncMock(side_effect=SQLAlchemyError("boom"))

            response = dangerous_functions_client.post(
                "/dangerous-functions/llm-analysis",
                json={"target_name": "test_model", "findings": [self._make_finding("strcpy")]},
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["saved"] is False
        assert payload["succeeded"] == 1

    def test_llm_analysis_not_configured(self, dangerous_functions_client: Any) -> None:
        """Test 503 when the LLM endpoint is disabled (real service fail-fast path)."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch(
            "app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
            new=AsyncMock(return_value=self._make_llm(enabled=False)),
        ):
            response = dangerous_functions_client.post(
                "/dangerous-functions/llm-analysis",
                json={"target_name": "test_model", "findings": [self._make_finding("strcpy")]},
            )

        assert response.status_code == 503
        data = response.json()
        detail = data.get("detail", data)
        assert detail.get("error", {}).get("code", "") == "LLM_NOT_CONFIGURED"

    def test_llm_analysis_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.post(
            "/dangerous-functions/llm-analysis",
            json={"target_name": "test_model", "findings": [self._make_finding("strcpy")]},
        )
        assert response.status_code == 401

    def test_llm_analysis_empty_findings(self, dangerous_functions_client: Any) -> None:
        """Test 422 when no findings are supplied."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.post(
            "/dangerous-functions/llm-analysis",
            json={"target_name": "test_model", "findings": []},
        )
        assert response.status_code == 422

    def test_llm_analysis_missing_target_name(self, dangerous_functions_client: Any) -> None:
        """Test 422 when target_name is missing."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.post(
            "/dangerous-functions/llm-analysis",
            json={"findings": [self._make_finding("strcpy")]},
        )
        assert response.status_code == 422

    def test_llm_analysis_too_many_findings(self, dangerous_functions_client: Any) -> None:
        """Test 422 when more than 100 findings are supplied."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        findings = [self._make_finding(f"fn{i}", entrypoint=f"0x{i:06x}") for i in range(101)]
        response = dangerous_functions_client.post(
            "/dangerous-functions/llm-analysis",
            json={"target_name": "test_model", "findings": findings},
        )
        assert response.status_code == 422

    def test_llm_analysis_rate_limited(self, dangerous_functions_client: Any) -> None:
        """Test that more than 10 requests per minute are rejected with 429."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        analyses = [FindingAnalysis(status="success", analysis="ok", model="test-model", elapsed_ms=1)]
        body = {"target_name": "test_model", "save": False, "findings": [self._make_finding("strcpy")]}

        with (
            patch(
                "app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
                new=AsyncMock(return_value=self._make_llm()),
            ),
            patch(
                "app.api.v1.endpoints.dangerous_functions.analyze_findings",
                new=AsyncMock(return_value=analyses),
            ),
        ):
            for _ in range(10):
                response = dangerous_functions_client.post(
                    "/dangerous-functions/llm-analysis", json=body,
                )
                assert response.status_code == 200
            response = dangerous_functions_client.post(
                "/dangerous-functions/llm-analysis", json=body,
            )
            assert response.status_code == 429


# ---------------------------------------------------------------------------
# GET /llm-results tests
# ---------------------------------------------------------------------------


class TestLLMResultsEndpoint:
    """Tests for GET /llm-results endpoint."""

    @staticmethod
    def _make_result(function_name: str = "strcpy", entrypoint: str = "0x401000") -> LLMAnalysisResult:
        from datetime import UTC, datetime

        return LLMAnalysisResult(
            target_name="test_model",
            function_name=function_name,
            containing_function="main",
            entrypoint=entrypoint,
            status="success",
            analysis="Analysis text",
            error="",
            model_name="test-model",
            elapsed_ms=42,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            modified_at=datetime(2026, 1, 2, tzinfo=UTC),
        )

    def test_get_llm_results(self, dangerous_functions_client: Any) -> None:
        """Test retrieving stored results for a target."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_repo:
            mock_repo.get_for_target = AsyncMock(return_value=[self._make_result()])

            response = dangerous_functions_client.get("/dangerous-functions/llm-results?target_name=test_model")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["target_name"] == "test_model"
        assert payload["count"] == 1
        assert payload["results"][0] == {
            "function_name": "strcpy",
            "containing_function": "main",
            "entrypoint": "0x401000",
            "status": "success",
            "analysis": "Analysis text",
            "error": "",
            "model_name": "test-model",
            "elapsed_ms": 42,
            "modified_at": "2026-01-02T00:00:00+00:00",
        }

    def test_get_llm_results_empty(self, dangerous_functions_client: Any) -> None:
        """Test that an empty result set is a valid success."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_repo:
            mock_repo.get_for_target = AsyncMock(return_value=[])

            response = dangerous_functions_client.get("/dangerous-functions/llm-results?target_name=test_model")

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["count"] == 0
        assert payload["results"] == []

    def test_get_llm_results_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.get("/dangerous-functions/llm-results?target_name=test_model")
        assert response.status_code == 401

    def test_get_llm_results_missing_target_name(self, dangerous_functions_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.get("/dangerous-functions/llm-results")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Scan report persistence tests
# ---------------------------------------------------------------------------


class TestScanReportPersistence:
    """The scan endpoint must persist its report for later retrieval."""

    def _scan_with_functions(self, dangerous_functions_client: Any) -> Any:
        from unittest.mock import Mock

        mock_func = Mock()
        mock_func.function_name = "my_func"
        mock_func.entrypoint = "0x401000"
        mock_func.tokens = "strcpy(dst, src); return 0;"

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.dangerous_functions.FunctionRepository") as mock_func_repo,
        ):
            mock_ml.exists = AsyncMock(return_value=True)
            mock_func_repo.get_functions = AsyncMock(return_value=[mock_func])
            return dangerous_functions_client.post(
                "/dangerous-functions/scan",
                json={"modelName": "test_model"},
            )

    def test_scan_persists_report(self, dangerous_functions_client: Any) -> None:
        """A successful scan saves its report via ScanReportRepository."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo:
            mock_repo.save_report = AsyncMock()
            response = self._scan_with_functions(dangerous_functions_client)

        assert response.status_code == 200
        assert mock_repo.save_report.await_count == 1
        saved = mock_repo.save_report.await_args_list[0].args[0]
        assert saved["model_name"] == "test_model"
        assert saved["total_found"] >= 1

    def test_scan_succeeds_when_persistence_fails(self, dangerous_functions_client: Any) -> None:
        """A persistence failure must not fail the scan request."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo:
            mock_repo.save_report = AsyncMock(side_effect=Exception("db down"))
            response = self._scan_with_functions(dangerous_functions_client)

        assert response.status_code == 200
        assert response.json()["data"]["total_found"] >= 1


# ---------------------------------------------------------------------------
# GET /scan-results tests
# ---------------------------------------------------------------------------


class TestGetScanResultsEndpoint:
    """Tests for GET /scan-results endpoint."""

    @staticmethod
    def _make_row(target_name: str = "test_model") -> Mock:
        from datetime import UTC, datetime

        row = Mock()
        row.target_name = target_name
        row.total_functions_scanned = 12
        row.total_found = 2
        row.critical_count = 1
        row.high_count = 1
        row.medium_count = 0
        row.low_count = 0
        row.results_json = (
            '[{"function_name": "strcpy", "containing_function": "main", '
            '"entrypoint": "0x401000", "category": "Buffer Overflow", '
            '"severity": "High", "cwe": "CWE-120", "description": "d", '
            '"safe_alternative": "strlcpy", "usage_context": ["strcpy(a, b);"], '
            '"containing_function_code": "void main() {}"}]'
        )
        row.modified_at = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
        return row

    def test_get_scan_results(self, dangerous_functions_client: Any) -> None:
        """Test retrieving a stored scan report."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo:
            mock_repo.get_report = AsyncMock(return_value=self._make_row())
            response = dangerous_functions_client.get(
                "/dangerous-functions/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["model_name"] == "test_model"
        assert payload["total_functions_scanned"] == 12
        assert payload["total_found"] == 2
        assert payload["critical_count"] == 1
        assert payload["high_count"] == 1
        assert len(payload["results"]) == 1
        assert payload["results"][0]["function_name"] == "strcpy"
        assert payload["modified_at"] == "2026-01-02T12:00:00+00:00"

    def test_get_scan_results_empty(self, dangerous_functions_client: Any) -> None:
        """Test that a target with no stored report returns a null data payload."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo:
            mock_repo.get_report = AsyncMock(return_value=None)
            response = dangerous_functions_client.get(
                "/dangerous-functions/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is None

    def test_get_scan_results_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.get(
            "/dangerous-functions/scan-results?target_name=test_model"
        )
        assert response.status_code == 401

    def test_get_scan_results_missing_target_name(self, dangerous_functions_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.get("/dangerous-functions/scan-results")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /scan-results tests
# ---------------------------------------------------------------------------


class TestDeleteScanResultsEndpoint:
    """Tests for DELETE /scan-results endpoint."""

    def test_delete_scan_results(self, dangerous_functions_client: Any) -> None:
        """Test deleting a stored scan report also deletes the LLM results."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo,
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_llm_repo,
        ):
            mock_repo.delete_for_target = AsyncMock(return_value=True)
            mock_llm_repo.delete_for_target = AsyncMock(return_value=True)
            response = dangerous_functions_client.request(
                "DELETE", "/dangerous-functions/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == "deleted"
        mock_repo.delete_for_target.assert_awaited_once_with("test_model")
        mock_llm_repo.delete_for_target.assert_awaited_once_with("test_model")

    def test_delete_scan_results_no_report_but_llm(self, dangerous_functions_client: Any) -> None:
        """Test deleting a target with only LLM results still reports deleted."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo,
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_llm_repo,
        ):
            mock_repo.delete_for_target = AsyncMock(return_value=False)
            mock_llm_repo.delete_for_target = AsyncMock(return_value=True)
            response = dangerous_functions_client.request(
                "DELETE", "/dangerous-functions/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        assert response.json()["data"] == "deleted"
        mock_repo.delete_for_target.assert_awaited_once_with("test_model")
        mock_llm_repo.delete_for_target.assert_awaited_once_with("test_model")

    def test_delete_scan_results_not_found(self, dangerous_functions_client: Any) -> None:
        """Test deleting a target with no stored report or LLM results is still a success."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo,
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_llm_repo,
        ):
            mock_repo.delete_for_target = AsyncMock(return_value=False)
            mock_llm_repo.delete_for_target = AsyncMock(return_value=False)
            response = dangerous_functions_client.request(
                "DELETE", "/dangerous-functions/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        assert response.json()["data"] == "not_found"

    def test_delete_scan_results_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.request(
            "DELETE", "/dangerous-functions/scan-results?target_name=test_model"
        )
        assert response.status_code == 401

    def test_delete_scan_results_missing_target_name(self, dangerous_functions_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.request("DELETE", "/dangerous-functions/scan-results")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /llm-results tests
# ---------------------------------------------------------------------------


class TestDeleteLlmResultsEndpoint:
    """Tests for DELETE /llm-results endpoint."""

    def test_delete_llm_results(self, dangerous_functions_client: Any) -> None:
        """Test deleting stored LLM results does not touch the scan report."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository") as mock_repo,
            patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_llm_repo,
        ):
            mock_repo.delete_for_target = AsyncMock(return_value=True)
            mock_llm_repo.delete_for_target = AsyncMock(return_value=True)
            response = dangerous_functions_client.request(
                "DELETE", "/dangerous-functions/llm-results?target_name=test_model"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == "deleted"
        mock_llm_repo.delete_for_target.assert_awaited_once_with("test_model")
        mock_repo.delete_for_target.assert_not_awaited()

    def test_delete_llm_results_not_found(self, dangerous_functions_client: Any) -> None:
        """Test deleting a target with no stored LLM results is still a success."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository") as mock_llm_repo:
            mock_llm_repo.delete_for_target = AsyncMock(return_value=False)
            response = dangerous_functions_client.request(
                "DELETE", "/dangerous-functions/llm-results?target_name=test_model"
            )

        assert response.status_code == 200
        assert response.json()["data"] == "not_found"

    def test_delete_llm_results_requires_auth(self, dangerous_functions_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(dangerous_functions_client, get_current_active_user, raise_unauthenticated)
        response = dangerous_functions_client.request(
            "DELETE", "/dangerous-functions/llm-results?target_name=test_model"
        )
        assert response.status_code == 401

    def test_delete_llm_results_missing_target_name(self, dangerous_functions_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(dangerous_functions_client, get_current_active_user, make_mock_user)
        response = dangerous_functions_client.request("DELETE", "/dangerous-functions/llm-results")
        assert response.status_code == 422
