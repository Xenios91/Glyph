"""Tests for behavioral scans API v1 endpoints."""

import pickle
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest_asyncio
from app.auth.dependencies import get_current_active_user
from app.database.models import Base
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    init_async_databases,
)

from tests.conftest import set_dependency_override
from tests.factories import make_mock_user

# ---------------------------------------------------------------------------
# GET /catalog tests
# ---------------------------------------------------------------------------


class TestGetCatalog:
    """Tests for GET /catalog endpoint."""

    def test_get_full_catalog(self, behavioral_scans_client: Any) -> None:
        """Test retrieving the full catalog without a category filter."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "entries" in data["data"]
        assert "categories" in data["data"]
        assert len(data["data"]["entries"]) == 24
        assert len(data["data"]["categories"]) == 7

    def test_catalog_entry_structure(self, behavioral_scans_client: Any) -> None:
        """Test that catalog entries have the correct structure."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog")
        data = response.json()
        entries = data["data"]["entries"]
        assert len(entries) > 0
        entry = entries[0]
        for field in (
            "signature_id",
            "name",
            "category",
            "severity",
            "detection_method",
            "patterns",
            "description",
            "mitre_technique",
        ):
            assert field in entry

    def test_catalog_categories(self, behavioral_scans_client: Any) -> None:
        """Test that the categories list includes the expected values."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog")
        data = response.json()
        categories = data["data"]["categories"]
        assert "Anti-Debugging" in categories
        assert "Process Injection" in categories
        assert "Network C2" in categories

    def test_get_catalog_by_category(self, behavioral_scans_client: Any) -> None:
        """Test filtering the catalog by category."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog?category=Anti-Debugging")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        entries = data["data"]["entries"]
        assert len(entries) > 0
        for entry in entries:
            assert entry["category"] == "Anti-Debugging"

    def test_get_catalog_by_unknown_category(self, behavioral_scans_client: Any) -> None:
        """Test filtering by an unknown category returns an empty list."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog?category=Nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["entries"] == []


# ---------------------------------------------------------------------------
# GET /catalog/{signature_id} tests
# ---------------------------------------------------------------------------


class TestGetCatalogEntry:
    """Tests for GET /catalog/{signature_id} endpoint."""

    def test_get_existing_entry_by_id(self, behavioral_scans_client: Any) -> None:
        """Test retrieving an existing catalog entry by id."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog/BEHAV-001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["signature_id"] == "BEHAV-001"
        assert data["data"]["name"] == "Debugger presence check"
        assert data["data"]["category"] == "Anti-Debugging"
        assert data["data"]["severity"] == "Critical"

    def test_get_existing_entry_by_name(self, behavioral_scans_client: Any) -> None:
        """Test retrieving an existing catalog entry by behavior name."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog/Debugger%20presence%20check")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["signature_id"] == "BEHAV-001"

    def test_get_nonexistent_entry(self, behavioral_scans_client: Any) -> None:
        """Test retrieving a nonexistent entry returns an error envelope."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog/BEHAV-999")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["error"]["message"].lower()

    def test_get_entry_case_insensitive(self, behavioral_scans_client: Any) -> None:
        """Test catalog lookup is case-insensitive."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog/behav-001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["signature_id"] == "BEHAV-001"

    def test_entry_response_structure(self, behavioral_scans_client: Any) -> None:
        """Test the entry response has all required fields."""
        response = behavioral_scans_client.get("/behavioral-scans/catalog/BEHAV-009")
        data = response.json()
        entry = data["data"]
        assert entry["signature_id"] == "BEHAV-009"
        assert entry["severity"] == "Critical"
        assert entry["detection_method"] == "api_call"
        assert len(entry["patterns"]) > 0
        assert len(entry["description"]) > 0


# ---------------------------------------------------------------------------
# GET /available-models tests
# ---------------------------------------------------------------------------


class TestGetAvailableModels:
    """Tests for GET /available-models endpoint."""

    def test_get_available_models(self, behavioral_scans_client: Any) -> None:
        """Test retrieving available models and prediction tasks."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.PredictionRepository") as mock_pred,
        ):
            mock_ml.get_models_list_for_user = AsyncMock(return_value=["model_a", "model_b"])
            mock_pred.get_task_names_for_user = AsyncMock(return_value=["task_1"])

            response = behavioral_scans_client.get("/behavioral-scans/available-models")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "model_a" in data["data"]["models"]
            assert "model_b" in data["data"]["models"]
            assert "task_1" in data["data"]["prediction_tasks"]

    def test_get_available_models_empty(self, behavioral_scans_client: Any) -> None:
        """Test empty models and predictions lists."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.PredictionRepository") as mock_pred,
        ):
            mock_ml.get_models_list_for_user = AsyncMock(return_value=[])
            mock_pred.get_task_names_for_user = AsyncMock(return_value=[])

            response = behavioral_scans_client.get("/behavioral-scans/available-models")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["models"] == []
            assert data["data"]["prediction_tasks"] == []

    def test_get_available_models_no_auth(self, behavioral_scans_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(behavioral_scans_client, get_current_active_user, raise_unauthenticated)
        response = behavioral_scans_client.get("/behavioral-scans/available-models")
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
        # Unowned (legacy) row: accessible to any authenticated user.
        func.user_id = None
        return func

    def _make_mock_model(self, name: str) -> Mock:
        """Create a mock Model ORM object (unowned/legacy)."""
        model = Mock()
        model.model_name = name
        model.user_id = None
        return model

    def _make_mock_binary_function(self, name: str, entrypoint: str = "0x401000", raw_code: str = "") -> Mock:
        """Create a mock BinaryFunction ORM object."""
        bf = Mock()
        bf.function_name = name
        bf.entrypoint = entrypoint
        bf.raw_code = raw_code
        return bf

    def test_scan_missing_target(self, behavioral_scans_client: Any) -> None:
        """Test scan with no target returns 400."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        response = behavioral_scans_client.post("/behavioral-scans/scan", json={})
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "modelName" in detail or "taskName" in detail or "binaryId" in detail

    def test_scan_rejects_extra_fields(self, behavioral_scans_client: Any) -> None:
        """Test that an unexpected field returns 422 (extra=forbid)."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        response = behavioral_scans_client.post(
            "/behavioral-scans/scan",
            json={"modelName": "test_model", "unexpected": "x"},
        )
        assert response.status_code == 422

    def test_scan_model_not_found(self, behavioral_scans_client: Any) -> None:
        """Test scan with a nonexistent model returns 404."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml:
            mock_ml.get = AsyncMock(return_value=None)

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "nonexistent_model"},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_scan_task_not_found(self, behavioral_scans_client: Any) -> None:
        """Test scan with a nonexistent task returns 404."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.PredictionRepository") as mock_pred:
            mock_pred.get_for_user = AsyncMock(return_value=None)

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"taskName": "nonexistent_task"},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_scan_binary_not_found(self, behavioral_scans_client: Any) -> None:
        """Test scan with a nonexistent binary returns 404."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BinaryRepository") as mock_bin:
            mock_bin.get = AsyncMock(return_value=None)

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"binaryId": 999},
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_scan_binary_not_owner(self, behavioral_scans_client: Any) -> None:
        """Test scan on a binary owned by another user returns 403."""
        # make_mock_user() returns a user with id=1; the binary is owned by id=2.
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_binary = Mock()
        mock_binary.id = 1
        mock_binary.uploaded_by = 2  # owned by a different user
        mock_binary.name = "other.elf"

        with patch("app.api.v1.endpoints.behavioral_scans.BinaryRepository") as mock_bin:
            mock_bin.get = AsyncMock(return_value=mock_binary)

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"binaryId": 1},
            )
            assert response.status_code == 403

    def test_scan_model_no_functions(self, behavioral_scans_client: Any) -> None:
        """Test scan of a model with no functions returns an empty report."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("empty_model"))
            mock_func.get_functions = AsyncMock(return_value=[])
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "empty_model"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_functions_scanned"] == 0
            assert data["data"]["total_found"] == 0

    def test_scan_model_with_behaviors(self, behavioral_scans_client: Any) -> None:
        """Test scan detects malware behaviors in a model's functions."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("dbg_func", "0x401000", "if (IsDebuggerPresent()) { return; }"),  # BEHAV-001 Critical
            self._make_mock_function("inj_func", "0x402000", "WriteProcessMemory(h, a, b, c, d, e);"),  # BEHAV-009 Critical
            self._make_mock_function("safe_func", "0x403000", "int x = 5; return x;"),
        ]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            report = data["data"]
            assert report["model_name"] == "test_model"
            assert report["total_functions_scanned"] == 3
            assert report["total_found"] >= 2
            assert report["critical_count"] >= 2

    def test_scan_report_structure(self, behavioral_scans_client: Any) -> None:
        """Test the scan report has the correct structure."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [self._make_mock_function("my_func", "0x401000", "IsDebuggerPresent();")]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            report = data["data"]
            for field in (
                "model_name",
                "total_functions_scanned",
                "total_found",
                "critical_count",
                "high_count",
                "medium_count",
                "low_count",
                "results",
            ):
                assert field in report

    def test_scan_result_structure(self, behavioral_scans_client: Any) -> None:
        """Test individual scan results have the correct structure."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [self._make_mock_function("my_func", "0xDEADBEEF", "IsDebuggerPresent();")]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            assert len(results) >= 1
            result = results[0]
            for field in (
                "signature_id",
                "behavior_name",
                "category",
                "severity",
                "detection_method",
                "containing_function",
                "entrypoint",
                "mitre_technique",
                "description",
                "matched_evidence",
                "containing_function_code",
            ):
                assert field in result

    def test_scan_preserves_entrypoint(self, behavioral_scans_client: Any) -> None:
        """Test that the memory address is preserved in results."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [self._make_mock_function("my_wrapper", "0xCAFE0000", "IsDebuggerPresent();")]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            assert len(results) >= 1
            assert results[0]["entrypoint"] == "0xCAFE0000"

    def test_scan_results_sorted_by_severity(self, behavioral_scans_client: Any) -> None:
        """Test that results are sorted by severity (Critical first)."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [
            self._make_mock_function("f1", "0x401000", 'printf("Mozilla/5.0");'),  # BEHAV-018 Low
            self._make_mock_function("f2", "0x402000", "IsDebuggerPresent();"),  # BEHAV-001 Critical
        ]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )
            data = response.json()
            results = data["data"]["results"]
            severities = [r["severity"] for r in results]
            if "Critical" in severities and "Low" in severities:
                assert severities.index("Critical") < severities.index("Low")

    def test_scan_by_task_name(self, behavioral_scans_client: Any) -> None:
        """Test scanning by prediction task name."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.user_id = None

        func_data: list[dict[str, Any]] = [
            {"functionName": "my_func", "lowAddress": "0x401000", "tokenList": ["IsDebuggerPresent();"]},
        ]
        mock_prediction.functions_data = pickle.dumps(func_data)

        with (
            patch("app.api.v1.endpoints.behavioral_scans.PredictionRepository") as mock_pred,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_pred.get_for_user = AsyncMock(return_value=mock_prediction)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"taskName": "test_task"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["total_found"] >= 1

    def test_scan_by_binary_id(self, behavioral_scans_client: Any) -> None:
        """Test scanning by binary id."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_binary = Mock()
        mock_binary.id = 1
        mock_binary.uploaded_by = 1  # owned by the mock user (id=1)
        mock_binary.name = "test.elf"

        mock_bin_funcs = [
            self._make_mock_binary_function("dbg_func", "0x401000", "void dbg_func() { IsDebuggerPresent(); }"),
        ]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.BinaryRepository") as mock_bin,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_bin.get = AsyncMock(return_value=mock_binary)
            mock_bin.get_functions = AsyncMock(return_value=mock_bin_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"binaryId": 1},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["model_name"] == "test.elf"
            assert data["data"]["total_found"] >= 1

    def test_scan_model_and_task_preference(self, behavioral_scans_client: Any) -> None:
        """Test that modelName takes precedence when both are provided."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        mock_funcs = [self._make_mock_function("dbg", "0x401000", "IsDebuggerPresent();")]

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func,
            patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo,
        ):
            mock_ml.get = AsyncMock(return_value=self._make_mock_model("test_model"))
            mock_func.get_functions = AsyncMock(return_value=mock_funcs)
            mock_repo.save_report = AsyncMock()

            response = behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model", "taskName": "test_task"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["model_name"] == "test_model"

    def test_scan_requires_auth(self, behavioral_scans_client: Any) -> None:
        """Test that the scan endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(behavioral_scans_client, get_current_active_user, raise_unauthenticated)
        response = behavioral_scans_client.post(
            "/behavioral-scans/scan",
            json={"modelName": "test_model"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Scan report persistence tests
# ---------------------------------------------------------------------------


class TestScanReportPersistence:
    """The scan endpoint must persist its report for later retrieval."""

    def _scan_with_functions(self, behavioral_scans_client: Any) -> Any:
        mock_func = Mock()
        mock_func.function_name = "my_func"
        mock_func.entrypoint = "0x401000"
        mock_func.tokens = "IsDebuggerPresent();"
        mock_func.user_id = None

        mock_model = Mock()
        mock_model.model_name = "test_model"
        mock_model.user_id = None

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func_repo,
        ):
            mock_ml.get = AsyncMock(return_value=mock_model)
            mock_func_repo.get_functions = AsyncMock(return_value=[mock_func])
            return behavioral_scans_client.post(
                "/behavioral-scans/scan",
                json={"modelName": "test_model"},
            )

    def test_scan_persists_report(self, behavioral_scans_client: Any) -> None:
        """A successful scan saves its report via BehavioralScanReportRepository."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.save_report = AsyncMock()
            response = self._scan_with_functions(behavioral_scans_client)

        assert response.status_code == 200
        assert mock_repo.save_report.await_count == 1
        saved = mock_repo.save_report.await_args_list[0].args[0]
        assert saved["model_name"] == "test_model"
        assert saved["total_found"] >= 1

    def test_scan_succeeds_when_persistence_fails(self, behavioral_scans_client: Any) -> None:
        """A persistence failure must not fail the scan request."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.save_report = AsyncMock(side_effect=Exception("db down"))
            response = self._scan_with_functions(behavioral_scans_client)

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
        row.high_count = 0
        row.medium_count = 1
        row.low_count = 0
        row.results_json = (
            '[{"signature_id": "BEHAV-001", "behavior_name": "Debugger presence check", '
            '"category": "Anti-Debugging", "severity": "Critical", "detection_method": "api_call", '
            '"containing_function": "main", "entrypoint": "0x401000", "mitre_technique": "", '
            '"description": "d", "matched_evidence": ["IsDebuggerPresent();"], '
            '"containing_function_code": "void main() {}"}]'
        )
        row.modified_at = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
        return row

    def test_get_scan_results(self, behavioral_scans_client: Any) -> None:
        """Test retrieving a stored scan report."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.get_report = AsyncMock(return_value=self._make_row())
            response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=test_model")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        payload = data["data"]
        assert payload["model_name"] == "test_model"
        assert payload["total_functions_scanned"] == 12
        assert payload["total_found"] == 2
        assert payload["critical_count"] == 1
        assert payload["medium_count"] == 1
        assert len(payload["results"]) == 1
        assert payload["results"][0]["signature_id"] == "BEHAV-001"
        assert payload["modified_at"] == "2026-01-02T12:00:00+00:00"

    def test_get_scan_results_empty(self, behavioral_scans_client: Any) -> None:
        """Test that a target with no stored report returns a null data payload."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.get_report = AsyncMock(return_value=None)
            response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=test_model")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is None

    def test_get_scan_results_requires_auth(self, behavioral_scans_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(behavioral_scans_client, get_current_active_user, raise_unauthenticated)
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=test_model")
        assert response.status_code == 401

    def test_get_scan_results_missing_target_name(self, behavioral_scans_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)
        response = behavioral_scans_client.get("/behavioral-scans/scan-results")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /scan-results tests
# ---------------------------------------------------------------------------


class TestDeleteScanResultsEndpoint:
    """Tests for DELETE /scan-results endpoint."""

    def test_delete_scan_results(self, behavioral_scans_client: Any) -> None:
        """Test deleting a stored scan report."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.delete_for_target = AsyncMock(return_value=True)
            response = behavioral_scans_client.request(
                "DELETE", "/behavioral-scans/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == "deleted"
        mock_repo.delete_for_target.assert_awaited_once_with("test_model", 1)

    def test_delete_scan_results_not_found(self, behavioral_scans_client: Any) -> None:
        """Test deleting a target with no stored report is still a success."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)

        with patch("app.api.v1.endpoints.behavioral_scans.BehavioralScanReportRepository") as mock_repo:
            mock_repo.delete_for_target = AsyncMock(return_value=False)
            response = behavioral_scans_client.request(
                "DELETE", "/behavioral-scans/scan-results?target_name=test_model"
            )

        assert response.status_code == 200
        assert response.json()["data"] == "not_found"

    def test_delete_scan_results_requires_auth(self, behavioral_scans_client: Any) -> None:
        """Test that the endpoint requires authentication (mocked dependency raises)."""
        from fastapi import HTTPException

        def raise_unauthenticated() -> None:
            raise HTTPException(status_code=401, detail="Not authenticated")

        set_dependency_override(behavioral_scans_client, get_current_active_user, raise_unauthenticated)
        response = behavioral_scans_client.request(
            "DELETE", "/behavioral-scans/scan-results?target_name=test_model"
        )
        assert response.status_code == 401

    def test_delete_scan_results_missing_target_name(self, behavioral_scans_client: Any) -> None:
        """Test 422 when the target_name query parameter is missing."""
        set_dependency_override(behavioral_scans_client, get_current_active_user, make_mock_user)
        response = behavioral_scans_client.request("DELETE", "/behavioral-scans/scan-results")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Ownership scoping tests (real database)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", autouse=True)
async def behavioral_report_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for ownership-scoping tests."""
    await init_async_databases()

    target_tables = DB_TABLE_MAP.get("intelligence")
    if target_tables and "intelligence" in async_engines:
        async with async_engines["intelligence"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def fresh_behavioral_report_table() -> AsyncGenerator[None, None]:
    """Drop and recreate the behavioral scan report table before each test."""
    target_tables = DB_TABLE_MAP.get("intelligence")
    if target_tables and "intelligence" in async_engines:
        async with async_engines["intelligence"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield


class TestOwnershipScoping:
    """One user must not be able to read or delete another user's stored report.

    These tests exercise the real BehavioralScanReportRepository against the
    test database (no repository mocks), so the SQL-level ownership scoping
    is verified end to end.
    """

    def _scan_as_user(self, client: Any, user_id: int) -> None:
        """Run a scan as the given user, persisting a report owned by that user."""
        set_dependency_override(client, get_current_active_user, lambda: make_mock_user(user_id=user_id))

        mock_func = Mock()
        mock_func.function_name = "my_func"
        mock_func.entrypoint = "0x401000"
        mock_func.tokens = "IsDebuggerPresent();"
        mock_func.user_id = user_id

        mock_model = Mock()
        mock_model.model_name = "shared_target"
        mock_model.user_id = user_id

        with (
            patch("app.api.v1.endpoints.behavioral_scans.ModelRepository") as mock_ml,
            patch("app.api.v1.endpoints.behavioral_scans.FunctionRepository") as mock_func_repo,
        ):
            mock_ml.get = AsyncMock(return_value=mock_model)
            mock_func_repo.get_functions = AsyncMock(return_value=[mock_func])
            response = client.post("/behavioral-scans/scan", json={"modelName": "shared_target"})

        assert response.status_code == 200

    def test_owner_can_read_own_report(
        self, behavioral_scans_client: Any, fresh_behavioral_report_table: None
    ) -> None:
        """The owner can retrieve their own stored report."""
        self._scan_as_user(behavioral_scans_client, user_id=1)

        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=1))
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload is not None
        assert payload["model_name"] == "shared_target"
        assert payload["total_found"] >= 1

    def test_other_user_cannot_read_report(
        self, behavioral_scans_client: Any, fresh_behavioral_report_table: None
    ) -> None:
        """A different user cannot retrieve another user's stored report."""
        self._scan_as_user(behavioral_scans_client, user_id=1)

        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=2))
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is None

    def test_other_user_cannot_delete_report(
        self, behavioral_scans_client: Any, fresh_behavioral_report_table: None
    ) -> None:
        """A different user cannot delete another user's stored report."""
        self._scan_as_user(behavioral_scans_client, user_id=1)

        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=2))
        response = behavioral_scans_client.request(
            "DELETE", "/behavioral-scans/scan-results?target_name=shared_target"
        )
        assert response.status_code == 200
        assert response.json()["data"] == "not_found"

        # The owner's report must still be intact.
        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=1))
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.json()["data"] is not None

    def test_owner_can_delete_own_report(
        self, behavioral_scans_client: Any, fresh_behavioral_report_table: None
    ) -> None:
        """The owner can delete their own stored report."""
        self._scan_as_user(behavioral_scans_client, user_id=1)

        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=1))
        response = behavioral_scans_client.request(
            "DELETE", "/behavioral-scans/scan-results?target_name=shared_target"
        )
        assert response.status_code == 200
        assert response.json()["data"] == "deleted"

        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.json()["data"] is None

    def test_scan_persists_report_under_scanner_ownership(
        self, behavioral_scans_client: Any, fresh_behavioral_report_table: None
    ) -> None:
        """A scan by user 2 persists the report under user 2's ownership."""
        self._scan_as_user(behavioral_scans_client, user_id=2)

        # User 2 sees the report; user 1 does not.
        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=2))
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.json()["data"] is not None

        set_dependency_override(behavioral_scans_client, get_current_active_user, lambda: make_mock_user(user_id=1))
        response = behavioral_scans_client.get("/behavioral-scans/scan-results?target_name=shared_target")
        assert response.json()["data"] is None
