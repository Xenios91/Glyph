"""Tests for dangerous function scanner service and catalog."""

from typing import Any

import pytest

from app.services.dangerous_functions_catalog import (
    DangerousFunctionEntry,
    get_entry,
    get_all_entries,
    get_categories,
    get_entries_by_category,
    get_severity_order,
    FUNCTION_LOOKUP,
    CATEGORY_INDEX,
)
from app.services.dangerous_function_scanner import (
    ScanResult,
    scan_functions,
    generate_report,
    _extract_usage_context,  # pyright: ignore[reportPrivateUsage]
    _get_function_body_context,  # pyright: ignore[reportPrivateUsage]
    _scan_function_bodies,  # pyright: ignore[reportPrivateUsage]
)


# ---------------------------------------------------------------------------
# Catalog tests
# ---------------------------------------------------------------------------

class TestCatalog:
    """Tests for the dangerous function catalog."""

    def test_get_entry_exists(self) -> None:
        """Test looking up a known dangerous function."""
        entry = get_entry("strcpy")
        assert entry is not None
        assert entry.name == "strcpy"
        assert entry.category == "Buffer Overflow"
        assert entry.severity == "High"
        assert "CWE-120" in entry.cwe

    def test_get_entry_case_insensitive(self) -> None:
        """Test that lookup is case-insensitive."""
        assert get_entry("STRCPY") is not None
        assert get_entry("StrCpy") is not None

    def test_get_entry_not_exists(self) -> None:
        """Test looking up a non-dangerous function returns None."""
        assert get_entry("safe_function") is None
        assert get_entry("malloc") is None  # malloc is not in catalog

    def test_get_entry_empty_string(self) -> None:
        """Test looking up empty string returns None."""
        assert get_entry("") is None

    def test_get_entry_none(self) -> None:
        """Test looking up None name returns None."""
        # get_entry expects a string, passing empty simulates missing name
        assert get_entry("") is None

    def test_function_lookup_populated(self) -> None:
        """Test that FUNCTION_LOOKUP dict is populated."""
        assert len(FUNCTION_LOOKUP) > 0
        assert "strcpy" in FUNCTION_LOOKUP
        assert "gets" in FUNCTION_LOOKUP
        assert "sprintf" in FUNCTION_LOOKUP

    def test_function_lookup_case_insensitive(self) -> None:
        """Test that FUNCTION_LOOKUP keys are lowercase."""
        for key in FUNCTION_LOOKUP:
            assert key == key.lower()

    def test_get_all_entries(self) -> None:
        """Test getting all catalog entries."""
        entries = get_all_entries()
        assert len(entries) > 0
        # All entries should be DangerousFunctionEntry instances
        for entry in entries:
            assert isinstance(entry, DangerousFunctionEntry)
            assert entry.name
            assert entry.category
            assert entry.severity in ("Critical", "High", "Medium", "Low")
            assert entry.cwe
            assert entry.description
            assert entry.safe_alternative

    def test_get_categories(self) -> None:
        """Test getting all categories."""
        categories = get_categories()
        assert len(categories) > 0
        assert "Buffer Overflow" in categories
        assert "Format String" in categories
        assert "Cryptographic Weakness" in categories

    def test_get_entries_by_category(self) -> None:
        """Test filtering entries by category."""
        buffer_overflow = get_entries_by_category("Buffer Overflow")
        assert len(buffer_overflow) > 0
        for entry in buffer_overflow:
            assert entry.category == "Buffer Overflow"

    def test_get_entries_by_unknown_category(self) -> None:
        """Test filtering by unknown category returns empty list."""
        entries = get_entries_by_category("Nonexistent Category")
        assert entries == []

    def test_category_index_populated(self) -> None:
        """Test that CATEGORY_INDEX dict is populated."""
        assert len(CATEGORY_INDEX) > 0
        for category, entries in CATEGORY_INDEX.items():
            assert len(entries) > 0
            for entry in entries:
                assert entry.category == category

    def test_entry_frozen(self) -> None:
        """Test that DangerousFunctionEntry is immutable."""
        entry = get_entry("strcpy")
        assert entry is not None
        with pytest.raises(Exception):
            entry.name = "something_else"  # type: ignore[fuzzy-comparison]

    def test_gets_is_critical(self) -> None:
        """Test that 'gets' is marked as Critical severity."""
        entry = get_entry("gets")
        assert entry is not None
        assert entry.severity == "Critical"

    def test_system_is_critical(self) -> None:
        """Test that 'system' is marked as Critical severity."""
        entry = get_entry("system")
        assert entry is not None
        assert entry.severity == "Critical"


class TestSeverityOrder:
    """Tests for severity ordering."""

    def test_critical_is_first(self) -> None:
        """Critical should have lowest sort order (comes first)."""
        assert get_severity_order("Critical") == 0

    def test_high_is_second(self) -> None:
        """High should have second sort order."""
        assert get_severity_order("High") == 1

    def test_medium_is_third(self) -> None:
        """Medium should have third sort order."""
        assert get_severity_order("Medium") == 2

    def test_low_is_last(self) -> None:
        """Low should have highest sort order (comes last)."""
        assert get_severity_order("Low") == 3

    def test_ordering_allows_sort(self) -> None:
        """Test that severity ordering allows correct sorting."""
        severities: list[str] = ["Low", "Critical", "Medium", "High"]
        sorted_severities: list[str] = sorted(severities, key=lambda s: get_severity_order(s))  # pyright: ignore[reportArgumentType]
        assert sorted_severities == ["Critical", "High", "Medium", "Low"]


# ---------------------------------------------------------------------------
# Scanner tests
# ---------------------------------------------------------------------------

class TestExtractUsageContext:
    """Tests for _extract_usage_context helper."""

    def test_empty_tokens(self) -> None:
        """Empty token list returns empty context."""
        assert _extract_usage_context([], "strcpy") == []

    def test_no_match(self) -> None:
        """Tokens without dangerous function return empty context."""
        tokens = ["int", "x", "=", "5", ";", "return", "x", ";"]
        result = _extract_usage_context(tokens, "strcpy")
        assert result == []

    def test_basic_match(self) -> None:
        """Tokens containing dangerous function are returned."""
        tokens = [
            "void", "process()", "{",
            "char", "buf[100];",
            "strcpy(buf,", "user_input);",
            "}",
        ]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) > 0
        assert any("strcpy" in line for line in result)

    def test_case_insensitive_match(self) -> None:
        """Matching is case-insensitive."""
        tokens = ["StrCpy(buf,", "src);"]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) > 0

    def test_multiple_matches(self) -> None:
        """Multiple statements with dangerous function are all captured."""
        tokens = [
            "strcpy(buf1,", "src1);",
            "strcpy(buf2,", "src2);",
            "strcpy(buf3,", "src3);",
        ]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) >= 2

    def test_deduplication(self) -> None:
        """Duplicate lines are removed."""
        tokens = [
            "strcpy(buf,", "src);",
            "strcpy(buf,", "src);",
            "strcpy(buf,", "src);",
        ]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) == 1

    def test_max_lines_limit(self) -> None:
        """Results are limited to 10 lines."""
        # Create 15 unique statements with strcpy
        tokens: list[str] = []
        for i in range(15):
            tokens.append(f"strcpy(buf{i}, src{i});")
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) <= 10

    def test_line_truncation(self) -> None:
        """Long lines are truncated to 300 chars."""
        long_token = "A" * 500
        tokens = [f"strcpy(buf, {long_token});"]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) > 0
        assert len(result[0]) <= 303  # 300 + "..."

    def test_statement_level_granularity(self) -> None:
        """Results are split by semicolons for statement granularity."""
        tokens = [
            "char", "a;",
            "strcpy(a,", "b);",
            "char", "c;",
        ]
        result = _extract_usage_context(tokens, "strcpy")
        assert len(result) > 0
        # Should not include unrelated statements
        for line in result:
            assert "strcpy" in line


class TestGetFunctionBodyContext:
    """Tests for _get_function_body_context helper."""

    def test_empty_tokens(self) -> None:
        """Empty tokens return empty context."""
        assert _get_function_body_context([]) == []

    def test_basic_context(self) -> None:
        """First few statements are returned as context."""
        tokens = [
            "void", "func()", "{",
            "int", "x", "=", "0;",
            "x", "=", "x", "+", "1;",
            "return", "x;",
            "}",
        ]
        result = _get_function_body_context(tokens, max_lines=3)
        assert len(result) > 0
        assert len(result) <= 3

    def test_max_lines_respected(self) -> None:
        """max_lines parameter limits output."""
        tokens = [f"stmt{i}; " for i in range(20)]
        result = _get_function_body_context(tokens, max_lines=5)
        assert len(result) <= 5

    def test_long_lines_truncated(self) -> None:
        """Long lines are truncated."""
        tokens = [("X" * 400 + ";") for _ in range(3)]
        result = _get_function_body_context(tokens, max_lines=3)
        for line in result:
            assert len(line) <= 303


# ---------------------------------------------------------------------------
# scan_functions tests
# ---------------------------------------------------------------------------

class TestScanFunctions:
    """Tests for the main scan_functions entry point."""

    def _make_function(self, name: str, address: str = "0x401000", tokens: list[str] | None = None) -> dict[str, Any]:
        """Helper to create a function dict."""
        return {
            "functionName": name,
            "lowAddress": address,
            "tokenList": tokens or [],
        }

    def test_empty_function_list(self) -> None:
        """Empty input returns empty results."""
        assert scan_functions([]) == []

    def test_no_dangerous_functions(self) -> None:
        """Functions not in catalog produce no results."""
        functions = [
            self._make_function("safe_func_1"),
            self._make_function("safe_func_2"),
        ]
        results = scan_functions(functions)
        assert results == []

    def test_single_dangerous_function(self) -> None:
        """Single dangerous function is detected."""
        functions = [self._make_function("strcpy")]
        results = scan_functions(functions)
        assert len(results) >= 1
        assert results[0].function_name == "strcpy"
        assert results[0].severity == "High"

    def test_multiple_dangerous_functions(self) -> None:
        """Multiple dangerous functions are all detected."""
        functions = [
            self._make_function("strcpy"),
            self._make_function("gets"),
            self._make_function("sprintf"),
        ]
        results = scan_functions(functions)
        names = {r.function_name for r in results}
        assert "strcpy" in names
        assert "gets" in names
        assert "sprintf" in names

    def test_severity_sorting(self) -> None:
        """Results are sorted by severity (Critical first)."""
        functions = [
            self._make_function("sprintf"),  # High
            self._make_function("gets"),     # Critical
        ]
        results = scan_functions(functions)
        assert len(results) >= 2
        # Critical should come before High
        severities = [r.severity for r in results]
        assert severities.index("Critical") < severities.index("High")

    def test_entrypoint_preserved(self) -> None:
        """Memory address is preserved in result."""
        functions = [self._make_function("strcpy", address="0xDEADBEEF")]
        results = scan_functions(functions)
        assert len(results) >= 1
        assert results[0].entrypoint == "0xDEADBEEF"

    def test_empty_function_name_skipped(self) -> None:
        """Functions with empty names are skipped."""
        functions = [self._make_function("")]
        results = scan_functions(functions)
        assert results == []

    def test_missing_function_name_key(self) -> None:
        """Functions missing functionName key are skipped."""
        functions: list[dict[str, Any]] = [{"lowAddress": "0x1000", "tokenList": []}]
        results = scan_functions(functions)
        assert results == []

    def test_usage_context_included(self) -> None:
        """Usage context is extracted for dangerous functions."""
        tokens = [
            "void", "strcpy()", "{",
            "char", "*", "dst", "=", "dest;",
            "strcpy(dst,", "src);",
            "}",
        ]
        functions = [self._make_function("strcpy", tokens=tokens)]
        results = scan_functions(functions)
        assert len(results) >= 1
        # Should have body context since direct match
        assert len(results[0].usage_context) > 0

    def test_result_has_all_fields(self) -> None:
        """ScanResult contains all required fields."""
        functions = [self._make_function("strcpy")]
        results = scan_functions(functions)
        assert len(results) >= 1
        result = results[0]
        assert result.function_name
        assert result.containing_function
        assert result.entrypoint
        assert result.category
        assert result.severity
        assert result.cwe
        assert result.description
        assert result.safe_alternative
        assert isinstance(result.usage_context, list)


# ---------------------------------------------------------------------------
# _scan_function_bodies tests
# ---------------------------------------------------------------------------

class TestScanFunctionBodies:
    """Tests for scanning function bodies for dangerous function calls."""

    def _make_function(self, name: str, tokens: list[str]) -> dict[str, Any]:
        return {
            "functionName": name,
            "lowAddress": "0x401000",
            "tokenList": tokens,
        }

    def test_no_calls_found(self) -> None:
        """Function body without dangerous calls returns empty."""
        func = self._make_function(
            "process_input",
            ["void", "process_input()", "{", "int", "x", "=", "5;", "}"],
        )
        results = _scan_function_bodies([func])
        assert results == []

    def test_call_to_dangerous_function(self) -> None:
        """Function calling strcpy is detected."""
        func = self._make_function(
            "process_input",
            ["void", "process_input()", "{", "char", "buf[100];", "strcpy(buf,", "input);", "}"],
        )
        results = _scan_function_bodies([func])
        assert len(results) >= 1
        assert results[0].function_name == "strcpy"
        assert results[0].containing_function == "process_input"

    def test_skips_self_named_functions(self) -> None:
        """Don't double-detect when function IS the dangerous function."""
        func = self._make_function(
            "strcpy",
            ["void", "strcpy()", "{", "return;", "}"],
        )
        results = _scan_function_bodies([func])
        # Should not find strcpy inside strcpy (self-reference skipped)
        assert not any(r.function_name == "strcpy" and r.containing_function == "strcpy" for r in results)

    def test_multiple_calls_in_body(self) -> None:
        """Multiple dangerous calls in one function are detected."""
        func = self._make_function(
            "vulnerable_func",
            [
                "void", "vulnerable_func()", "{",
                "strcpy(a,", "b);",
                "sprintf(c,", "fmt);",
                "}",
            ],
        )
        results = _scan_function_bodies([func])
        names = {r.function_name for r in results}
        assert "strcpy" in names
        assert "sprintf" in names

    def test_word_boundary_matching(self) -> None:
        """Only whole-word matches are detected (no false positives)."""
        # "my_strcpy_wrapper" should NOT match "strcpy" due to word boundary
        func = self._make_function(
            "safe_func",
            ["void", "safe_func()", "{", "my_strcpy_wrapper();", "}"],
        )
        results = _scan_function_bodies([func])
        # Should not match because "my_strcpy_wrapper" is not a word-boundary match for "strcpy"
        assert not any(r.function_name == "strcpy" for r in results)

    def test_empty_tokens_skipped(self) -> None:
        """Functions with empty token lists are skipped."""
        func = self._make_function("some_func", [])
        results = _scan_function_bodies([func])
        assert results == []

    def test_severity_sorting(self) -> None:
        """Results from body scanning are sorted by severity."""
        funcs = [
            self._make_function(
                "func1",
                ["void", "f1()", "{", "sprintf(a,", "b);", "}"],  # High
            ),
            self._make_function(
                "func2",
                ["void", "f2()", "{", "gets(buf);", "}"],  # Critical
            ),
        ]
        results = _scan_function_bodies(funcs)
        assert len(results) >= 2
        severities = [r.severity for r in results]
        assert severities.index("Critical") < severities.index("High")

    def test_usage_context_extracted(self) -> None:
        """Usage context is extracted for body-scanned calls."""
        func = self._make_function(
            "reader",
            ["void", "reader()", "{", "char", "buf[64];", "gets(buf);", "}"],
        )
        results = _scan_function_bodies([func])
        assert len(results) >= 1
        assert len(results[0].usage_context) > 0


# ---------------------------------------------------------------------------
# generate_report tests
# ---------------------------------------------------------------------------

class TestGenerateReport:
    """Tests for report generation."""

    def _make_function(self, name: str, tokens: list[str] | None = None) -> dict[str, Any]:
        return {
            "functionName": name,
            "lowAddress": "0x401000",
            "tokenList": tokens or [],
        }

    def test_empty_scan(self) -> None:
        """Report with no functions scanned."""
        report = generate_report("test_model", [])
        assert report.model_name == "test_model"
        assert report.total_functions_scanned == 0
        assert report.total_found == 0
        assert report.critical_count == 0
        assert report.high_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0
        assert report.results == []

    def test_counts_correct(self) -> None:
        """Severity counts are correct."""
        functions = [
            self._make_function("gets"),     # Critical
            self._make_function("strcpy"),   # High
            self._make_function("sprintf"),  # High
        ]
        report = generate_report("test_model", functions)
        assert report.total_functions_scanned == 3
        assert report.total_found >= 3
        assert report.critical_count >= 1
        assert report.high_count >= 2

    def test_model_name_preserved(self) -> None:
        """Model name is preserved in report."""
        report = generate_report("my_binary_v2", [])
        assert report.model_name == "my_binary_v2"

    def test_results_sorted(self) -> None:
        """Report results are sorted by severity."""
        functions = [
            self._make_function("sprintf"),  # High
            self._make_function("gets"),     # Critical
        ]
        report = generate_report("test_model", functions)
        if len(report.results) >= 2:
            assert report.results[0].severity == "Critical"

    def test_with_precomputed_results(self) -> None:
        """Pre-computed scan results are used when provided."""
        results = [
            ScanResult(
                function_name="strcpy",
                containing_function="strcpy",
                entrypoint="0x1000",
                category="Buffer Overflow",
                severity="High",
                cwe="CWE-120",
                description="Test",
                safe_alternative="strncpy",
                usage_context=[],
            ),
        ]
        report = generate_report("test_model", [], scan_results=results)
        assert report.total_found == 1
        assert report.high_count == 1
        assert report.results == results

    def test_total_found_matches_results(self) -> None:
        """total_found matches actual results count."""
        functions = [
            self._make_function("strcpy"),
            self._make_function("gets"),
        ]
        report = generate_report("test_model", functions)
        assert report.total_found == len(report.results)

    def test_severity_counts_sum(self) -> None:
        """Sum of severity counts equals total_found."""
        functions = [
            self._make_function("gets"),
            self._make_function("strcpy"),
            self._make_function("sprintf"),
        ]
        report = generate_report("test_model", functions)
        severity_sum = report.critical_count + report.high_count + report.medium_count + report.low_count
        assert severity_sum == report.total_found
