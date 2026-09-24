"""Tests for LLMResultRepository (stored LLM analysis results)."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.database.llm_result_repository import LLMResultRepository
from app.database.models import Base, LLMAnalysisResult
from app.database.scan_report_repository import ScanReportRepository
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    init_async_databases,
)
from sqlalchemy import exc as sa_exc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Database lifecycle fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", autouse=True)
async def llm_result_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for LLM result tests."""
    await init_async_databases()

    target_tables = DB_TABLE_MAP.get("intelligence")
    if target_tables and "intelligence" in async_engines:
        async with async_engines["intelligence"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def fresh_intelligence_tables() -> AsyncGenerator[None, None]:
    """Drop and recreate intelligence DB tables before each test."""
    target_tables = DB_TABLE_MAP.get("intelligence")
    if target_tables and "intelligence" in async_engines:
        async with async_engines["intelligence"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield


def _make_result(
    function_name: str = "strcpy",
    containing_function: str = "main",
    entrypoint: str = "0x401000",
    status: str = "success",
    analysis: str = "Use a bounded copy instead.",
    error: str = "",
    model_name: str = "gpt-4o-mini",
    elapsed_ms: int = 1234,
) -> LLMAnalysisResult:
    """Build an LLMAnalysisResult instance without persisting it."""
    return LLMAnalysisResult(
        function_name=function_name,
        containing_function=containing_function,
        entrypoint=entrypoint,
        status=status,
        analysis=analysis,
        error=error,
        model_name=model_name,
        elapsed_ms=elapsed_ms,
    )


class TestLLMAnalysisResultRegistration:
    """The new table must be created for the intelligence database at startup."""

    def test_intelligence_table_map_contains_llm_analysis_results(self) -> None:
        """LLMAnalysisResult.__table__ is registered under 'intelligence'."""
        table_names = {table.name for table in DB_TABLE_MAP["intelligence"]}
        assert "llm_analysis_results" in table_names

    async def test_intelligence_database_schema_contains_table(self) -> None:
        """The create_all path produces the llm_analysis_results table."""
        async with async_engines["intelligence"].connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            table_names = {row[0] for row in result.all()}
        assert "llm_analysis_results" in table_names


class TestUpsertMany:
    """Insert-or-update behaviour of LLMResultRepository.upsert_many."""

    async def test_inserts_new_rows(self, fresh_intelligence_tables: Any) -> None:
        """New findings are inserted with all payload fields."""
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(), _make_result(function_name="system")],
        )

        rows = await LLMResultRepository.get_for_target("target_a")
        assert len(rows) == 2
        by_name = {row.function_name: row for row in rows}
        strcpy = by_name["strcpy"]
        assert strcpy.target_name == "target_a"
        assert strcpy.status == "success"
        assert strcpy.analysis == "Use a bounded copy instead."
        assert strcpy.error == ""
        assert strcpy.model_name == "gpt-4o-mini"
        assert strcpy.elapsed_ms == 1234
        assert by_name["system"].containing_function == "main"

    async def test_updates_existing_row_and_advances_modified_at(self, fresh_intelligence_tables: Any) -> None:
        """Re-running the analysis overwrites the row and advances modified_at."""
        await LLMResultRepository.upsert_many("target_a", [_make_result(analysis="first pass")])
        await asyncio.sleep(0.01)
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(analysis="second pass", status="error", error="request timed out")],
        )

        rows = await LLMResultRepository.get_for_target("target_a")
        assert len(rows) == 1
        row = rows[0]
        assert row.analysis == "second pass"
        assert row.status == "error"
        assert row.error == "request timed out"
        assert row.modified_at > row.created_at

    async def test_mixed_batch_inserts_and_updates(self, fresh_intelligence_tables: Any) -> None:
        """A batch may contain both new and existing findings."""
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(), _make_result(function_name="system")],
        )
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(function_name="system", analysis="updated"), _make_result(function_name="gets")],
        )

        rows = await LLMResultRepository.get_for_target("target_a")
        assert len(rows) == 3
        by_name = {row.function_name: row for row in rows}
        assert by_name["system"].analysis == "updated"
        assert "gets" in by_name

    async def test_duplicate_key_in_batch_keeps_last(self, fresh_intelligence_tables: Any) -> None:
        """Same finding twice in one batch (two call sites) collapses to one row."""
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(analysis="first call site"), _make_result(analysis="second call site")],
        )

        rows = await LLMResultRepository.get_for_target("target_a")
        assert len(rows) == 1
        assert rows[0].analysis == "second call site"

    async def test_same_finding_different_targets_stays_separate(self, fresh_intelligence_tables: Any) -> None:
        """The unique key is scoped per target."""
        await LLMResultRepository.upsert_many("target_a", [_make_result()])
        await LLMResultRepository.upsert_many("target_b", [_make_result()])

        assert len(await LLMResultRepository.get_for_target("target_a")) == 1
        assert len(await LLMResultRepository.get_for_target("target_b")) == 1

    async def test_empty_list_is_noop(self, fresh_intelligence_tables: Any) -> None:
        """Upserting an empty batch changes nothing."""
        await LLMResultRepository.upsert_many("target_a", [])
        assert await LLMResultRepository.get_for_target("target_a") == []

    async def test_single_commit_for_batch(
        self, fresh_intelligence_tables: Any, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The whole batch is persisted with exactly one commit."""
        commits = 0
        original_commit = AsyncSession.commit

        async def counting_commit(self: AsyncSession) -> None:
            nonlocal commits
            commits += 1
            await original_commit(self)

        monkeypatch.setattr(AsyncSession, "commit", counting_commit)
        await LLMResultRepository.upsert_many(
            "target_a",
            [_make_result(), _make_result(function_name="system")],
        )

        assert commits == 1
        assert len(await LLMResultRepository.get_for_target("target_a")) == 2

    async def test_raises_on_database_error(self, fresh_intelligence_tables: Any) -> None:
        """A failing write rolls back and propagates the SQLAlchemyError."""
        async with async_engines["intelligence"].begin() as conn:
            tables: list[Any] = [LLMAnalysisResult.__table__]
            await conn.run_sync(Base.metadata.drop_all, tables=tables)

        with pytest.raises(sa_exc.SQLAlchemyError):
            await LLMResultRepository.upsert_many("target_a", [_make_result()])


class TestGetForTarget:
    """Read behaviour of LLMResultRepository.get_for_target."""

    async def test_unknown_target_returns_empty_list(self, fresh_intelligence_tables: Any) -> None:
        """No stored results means an empty list, not an error."""
        assert await LLMResultRepository.get_for_target("missing") == []

    async def test_ordered_by_function_name_then_containing_function(self, fresh_intelligence_tables: Any) -> None:
        """Results are returned deterministically ordered."""
        await LLMResultRepository.upsert_many(
            "target_a",
            [
                _make_result(function_name="zeta", containing_function="main"),
                _make_result(function_name="alpha", containing_function="main"),
                _make_result(function_name="zeta", containing_function="bbb"),
                _make_result(function_name="zeta", containing_function="aaa"),
            ],
        )

        rows = await LLMResultRepository.get_for_target("target_a")
        keys = [(row.function_name, row.containing_function) for row in rows]
        assert keys == [
            ("alpha", "main"),
            ("zeta", "aaa"),
            ("zeta", "bbb"),
            ("zeta", "main"),
        ]


class TestDeleteForTarget:
    """Delete behaviour of LLMResultRepository.delete_for_target."""

    async def test_delete_removes_only_that_target(self, fresh_intelligence_tables: Any) -> None:
        """Deleting one target's results leaves other targets intact."""
        await LLMResultRepository.upsert_many("target_a", [_make_result()])
        await LLMResultRepository.upsert_many("target_b", [_make_result()])

        deleted = await LLMResultRepository.delete_for_target("target_a")

        assert deleted is True
        assert await LLMResultRepository.get_for_target("target_a") == []
        assert len(await LLMResultRepository.get_for_target("target_b")) == 1

    async def test_delete_unknown_target_is_noop(self, fresh_intelligence_tables: Any) -> None:
        """Deleting a target with no stored results does not raise and reports False."""
        deleted = await LLMResultRepository.delete_for_target("missing")

        assert deleted is False


# ---------------------------------------------------------------------------
# ScanReportRepository tests
# ---------------------------------------------------------------------------


def _make_scan_report(
    target_name: str = "test_model",
    total_found: int = 1,
    results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a scan report dict matching the scanner's JSON shape."""
    if results is None:
        results = [
            {
                "function_name": "strcpy",
                "containing_function": "main",
                "entrypoint": "0x401000",
                "category": "Buffer Overflow",
                "severity": "High",
                "cwe": "CWE-120",
                "description": "Unbounded copy",
                "safe_alternative": "strlcpy",
                "usage_context": ["strcpy(buf, src);"],
                "containing_function_code": "void main() { strcpy(buf, src); }",
            }
        ]
    return {
        "model_name": target_name,
        "total_functions_scanned": 10,
        "total_found": total_found,
        "critical_count": 0,
        "high_count": total_found,
        "medium_count": 0,
        "low_count": 0,
        "results": results,
    }


class TestScanReportRepository:
    """Persistence behaviour of ScanReportRepository."""

    async def test_table_registered_under_intelligence(self) -> None:
        """ScanReport.__table__ is registered under 'intelligence'."""
        table_names = {table.name for table in DB_TABLE_MAP["intelligence"]}
        assert "scan_reports" in table_names

    async def test_save_and_get_roundtrip(self, fresh_intelligence_tables: Any) -> None:
        """A saved report is returned with all fields intact."""
        await ScanReportRepository.save_report(_make_scan_report())

        row = await ScanReportRepository.get_report("test_model")
        assert row is not None
        assert row.target_name == "test_model"
        assert row.total_functions_scanned == 10
        assert row.total_found == 1
        assert row.high_count == 1
        results = json.loads(row.results_json)
        assert len(results) == 1
        assert results[0]["function_name"] == "strcpy"
        assert results[0]["usage_context"] == ["strcpy(buf, src);"]

    async def test_get_unknown_target_returns_none(self, fresh_intelligence_tables: Any) -> None:
        """No stored report means None, not an error."""
        assert await ScanReportRepository.get_report("missing") is None

    async def test_save_overwrites_existing_report(self, fresh_intelligence_tables: Any) -> None:
        """Re-saving a target replaces the previous report."""
        await ScanReportRepository.save_report(_make_scan_report(total_found=1))
        await ScanReportRepository.save_report(_make_scan_report(total_found=0, results=[]))

        row = await ScanReportRepository.get_report("test_model")
        assert row is not None
        assert row.total_found == 0
        assert json.loads(row.results_json) == []

    async def test_empty_report_is_stored(self, fresh_intelligence_tables: Any) -> None:
        """A report with no findings is a valid stored value."""
        await ScanReportRepository.save_report(
            _make_scan_report("clean_model", total_found=0, results=[]),
        )

        row = await ScanReportRepository.get_report("clean_model")
        assert row is not None
        assert row.total_found == 0
        assert json.loads(row.results_json) == []

    async def test_reports_are_scoped_per_target(self, fresh_intelligence_tables: Any) -> None:
        """Saving one target leaves other targets' reports intact."""
        await ScanReportRepository.save_report(_make_scan_report("target_a"))
        await ScanReportRepository.save_report(
            _make_scan_report("target_b", total_found=0, results=[]),
        )

        row_a = await ScanReportRepository.get_report("target_a")
        row_b = await ScanReportRepository.get_report("target_b")
        assert row_a is not None and row_a.total_found == 1
        assert row_b is not None and row_b.total_found == 0

    async def test_delete_removes_only_that_target(self, fresh_intelligence_tables: Any) -> None:
        """Deleting one target's report leaves other targets intact."""
        await ScanReportRepository.save_report(_make_scan_report("target_a"))
        await ScanReportRepository.save_report(_make_scan_report("target_b"))

        deleted = await ScanReportRepository.delete_for_target("target_a")

        assert deleted is True
        assert await ScanReportRepository.get_report("target_a") is None
        assert await ScanReportRepository.get_report("target_b") is not None

    async def test_delete_unknown_target_is_noop(self, fresh_intelligence_tables: Any) -> None:
        """Deleting a target with no stored report returns False without raising."""
        deleted = await ScanReportRepository.delete_for_target("missing")
        assert deleted is False

    async def test_delete_does_not_affect_llm_results(
        self, fresh_intelligence_tables: Any,
    ) -> None:
        """Deleting a scan report leaves LLM analysis results untouched."""
        await LLMResultRepository.upsert_many("target_a", [_make_result()])
        await ScanReportRepository.save_report(_make_scan_report("target_a"))

        await ScanReportRepository.delete_for_target("target_a")

        assert await ScanReportRepository.get_report("target_a") is None
        assert len(await LLMResultRepository.get_for_target("target_a")) == 1
