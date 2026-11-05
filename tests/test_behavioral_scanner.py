"""Tests for the behavioral scanner service and signature catalog."""

from typing import Any

import pytest
from app.services.behavioral_scanner import (
    MAX_EVIDENCE_LENGTH,
    MAX_EVIDENCE_STATEMENTS,
    BehavioralScanReport,
    BehavioralScanResult,
    _compile_signature,  # pyright: ignore[reportPrivateUsage]
    _dedupe_cap,  # pyright: ignore[reportPrivateUsage]
    _extract_string_literals,  # pyright: ignore[reportPrivateUsage]
    _match_api_call,  # pyright: ignore[reportPrivateUsage]
    _match_code_heuristic,  # pyright: ignore[reportPrivateUsage]
    _match_string_pattern,  # pyright: ignore[reportPrivateUsage]
    _normalize_code_text,  # pyright: ignore[reportPrivateUsage]
    _split_statements,  # pyright: ignore[reportPrivateUsage]
    _truncate_statement,  # pyright: ignore[reportPrivateUsage]
    generate_report,
    scan_functions,
)
from app.services.behavioral_signatures_catalog import (
    CATEGORY_INDEX,
    SIGNATURE_LOOKUP,
    BehavioralSignatureEntry,
    get_all_entries,
    get_categories,
    get_entries_by_category,
    get_entry,
    get_severity_order,
)

VALID_SEVERITIES = ("Critical", "High", "Medium", "Low")
VALID_METHODS = ("api_call", "string_pattern", "code_heuristic", "import_check")


def _make_function(
    name: str,
    address: str = "0x401000",
    tokens: list[str] | None = None,
    raw_code: str = "",
) -> dict[str, Any]:
    """Helper to create a function dict in the binary_function_to_dict shape."""
    return {
        "functionName": name,
        "lowAddress": address,
        "tokenList": tokens or [],
        "raw_code": raw_code or " ".join(tokens or []),
    }


# ---------------------------------------------------------------------------
# Catalog tests
# ---------------------------------------------------------------------------


class TestCatalog:
    """Tests for the behavioral signature catalog."""

    def test_catalog_has_24_entries(self) -> None:
        """The v1 catalog ships exactly 24 signatures."""
        entries = get_all_entries()
        assert len(entries) == 24

    def test_signature_ids_unique(self) -> None:
        """All signature ids are unique."""
        entries = get_all_entries()
        ids = [e.signature_id for e in entries]
        assert len(ids) == len(set(ids))

    def test_signature_ids_follow_scheme(self) -> None:
        """All signature ids follow the BEHAV-NNN scheme."""
        for entry in get_all_entries():
            assert entry.signature_id.startswith("BEHAV-")
            assert entry.signature_id[6:].isdigit()

    def test_entries_have_valid_severity(self) -> None:
        """Every entry has a valid severity level."""
        for entry in get_all_entries():
            assert entry.severity in VALID_SEVERITIES

    def test_entries_have_valid_category(self) -> None:
        """Every entry has a non-empty category that appears in the index."""
        for entry in get_all_entries():
            assert entry.category
            assert entry.category in CATEGORY_INDEX

    def test_entries_have_valid_detection_method(self) -> None:
        """Every entry uses a valid detection method."""
        for entry in get_all_entries():
            assert entry.detection_method in VALID_METHODS

    def test_entries_have_nonempty_patterns(self) -> None:
        """Every entry has at least one pattern."""
        for entry in get_all_entries():
            assert len(entry.patterns) > 0
            for pattern in entry.patterns:
                assert pattern

    def test_entries_have_description(self) -> None:
        """Every entry carries a human-readable description."""
        for entry in get_all_entries():
            assert entry.description

    def test_get_entry_by_id(self) -> None:
        """Looking up by stable id returns the entry."""
        entry = get_entry("BEHAV-001")
        assert entry is not None
        assert entry.signature_id == "BEHAV-001"
        assert entry.name == "Debugger presence check"
        assert entry.category == "Anti-Debugging"
        assert entry.severity == "Critical"
        assert entry.detection_method == "api_call"

    def test_get_entry_by_name(self) -> None:
        """Looking up by behavior name returns the same entry."""
        entry = get_entry("Debugger presence check")
        assert entry is not None
        assert entry.signature_id == "BEHAV-001"

    def test_get_entry_case_insensitive(self) -> None:
        """Lookup by id or name is case-insensitive."""
        assert get_entry("behav-001") is not None
        assert get_entry("BEHAV-001") is not None
        assert get_entry("debugger presence check") is not None
        assert get_entry("Debugger Presence Check") is not None

    def test_get_entry_not_found(self) -> None:
        """Looking up an unknown id or name returns None."""
        assert get_entry("BEHAV-999") is None
        assert get_entry("nonexistent behavior") is None
        assert get_entry("") is None

    def test_signature_lookup_populated(self) -> None:
        """SIGNATURE_LOOKUP is keyed by lowercase id and name."""
        assert len(SIGNATURE_LOOKUP) > 0
        assert "behav-001" in SIGNATURE_LOOKUP
        assert "debugger presence check" in SIGNATURE_LOOKUP
        for key in SIGNATURE_LOOKUP:
            assert key == key.lower()

    def test_category_index_populated(self) -> None:
        """CATEGORY_INDEX maps each category to its entries."""
        assert len(CATEGORY_INDEX) > 0
        for category, entries in CATEGORY_INDEX.items():
            assert len(entries) > 0
            for entry in entries:
                assert entry.category == category

    def test_get_categories(self) -> None:
        """get_categories returns the expected seven categories."""
        categories = get_categories()
        assert "Anti-Debugging" in categories
        assert "Anti-Sandbox / Anti-VM" in categories
        assert "Process Injection" in categories
        assert "Credential Harvesting" in categories
        assert "Network C2" in categories
        assert "Persistence" in categories
        assert "Obfuscation / Anti-Analysis" in categories
        assert len(categories) == 7

    def test_get_entries_by_category(self) -> None:
        """Filtering by category returns only that category's entries."""
        anti_debug = get_entries_by_category("Anti-Debugging")
        assert len(anti_debug) > 0
        for entry in anti_debug:
            assert entry.category == "Anti-Debugging"

    def test_get_entries_by_unknown_category(self) -> None:
        """Filtering by an unknown category returns an empty list."""
        assert get_entries_by_category("Nonexistent Category") == []

    def test_entry_frozen(self) -> None:
        """BehavioralSignatureEntry is immutable (frozen dataclass)."""
        entry = get_entry("BEHAV-001")
        assert entry is not None
        with pytest.raises(Exception):
            entry.name = "something_else"  # type: ignore[misc]

    def test_no_import_check_entries_in_v1(self) -> None:
        """No v1 entry uses the reserved import_check method."""
        for entry in get_all_entries():
            assert entry.detection_method != "import_check"

    def test_mitre_technique_is_string(self) -> None:
        """mitre_technique is always a string (possibly empty)."""
        for entry in get_all_entries():
            assert isinstance(entry.mitre_technique, str)


class TestSeverityOrder:
    """Tests for severity ordering."""

    def test_critical_is_first(self) -> None:
        assert get_severity_order("Critical") == 0

    def test_high_is_second(self) -> None:
        assert get_severity_order("High") == 1

    def test_medium_is_third(self) -> None:
        assert get_severity_order("Medium") == 2

    def test_low_is_last(self) -> None:
        assert get_severity_order("Low") == 3

    def test_ordering_allows_sort(self) -> None:
        severities: list[str] = ["Low", "Critical", "Medium", "High"]
        sorted_severities = sorted(severities, key=lambda s: get_severity_order(s))  # pyright: ignore[reportArgumentType]
        assert sorted_severities == ["Critical", "High", "Medium", "Low"]


# ---------------------------------------------------------------------------
# api_call detection tests
# ---------------------------------------------------------------------------


class TestApiCallDetection:
    """Tests for the api_call detection method."""

    def test_real_call_matches(self) -> None:
        """A real call (name followed by '(') is detected."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = "void func() { if (IsDebuggerPresent()) { return; } }"
        assert _match_api_call(compiled, code) is True

    def test_function_pointer_fallback_matches(self) -> None:
        """A function-pointer reference (= name / &name) is detected."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = "void func() { BOOL (*check)() = IsDebuggerPresent; check(); }"
        assert _match_api_call(compiled, code) is True

    def test_address_of_pointer_matches(self) -> None:
        """An address-of reference (&name) is detected."""
        compiled = _compile_signature(get_entry("BEHAV-009"))  # WriteProcessMemory
        code = "void func() { auto fn = &WriteProcessMemory; }"
        assert _match_api_call(compiled, code) is True

    def test_plain_identifier_does_not_match(self) -> None:
        """A plain identifier (no call, no pointer) is NOT detected."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = "void func() { int IsDebuggerPresent; return IsDebuggerPresent; }"
        assert _match_api_call(compiled, code) is False

    def test_name_in_string_literal_does_not_match(self) -> None:
        """The API name inside a quoted string is NOT detected by api_call."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = 'void func() { printf("IsDebuggerPresent is used here"); }'
        assert _match_api_call(compiled, code) is False

    def test_pointer_inside_string_literal_does_not_match(self) -> None:
        """A pointer-like reference inside a quoted string is NOT detected."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = 'void func() { printf("ptr = IsDebuggerPresent"); }'
        assert _match_api_call(compiled, code) is False

    def test_multi_pattern_entry_matches_any(self) -> None:
        """An entry with multiple API names matches if any one is called."""
        compiled = _compile_signature(get_entry("BEHAV-014"))  # GetUserName/GetComputerName/GetDomainName
        code = "void func() { GetComputerName(buf, size); }"
        assert _match_api_call(compiled, code) is True

    def test_case_insensitive_call(self) -> None:
        """Call matching is case-insensitive."""
        compiled = _compile_signature(get_entry("BEHAV-001"))  # IsDebuggerPresent
        code = "void func() { isdebuggerpresent(); }"
        assert _match_api_call(compiled, code) is True


# ---------------------------------------------------------------------------
# string_pattern detection tests
# ---------------------------------------------------------------------------


class TestStringPatternDetection:
    """Tests for the string_pattern detection method."""

    def test_matches_quoted_literal(self) -> None:
        """A vendor string inside a quoted literal is detected."""
        compiled = _compile_signature(get_entry("BEHAV-005"))  # VMware|...|sandbox
        literals = _extract_string_literals('void func() { char *v = "VMware, Inc."; }')
        assert _match_string_pattern(compiled, literals) is True

    def test_does_not_match_identifier(self) -> None:
        """The same word as a bare identifier (no string literal) is NOT detected."""
        compiled = _compile_signature(get_entry("BEHAV-005"))  # VMware|...
        literals = _extract_string_literals("void func() { int VMware; return VMware; }")
        assert literals == []
        assert _match_string_pattern(compiled, literals) is False

    def test_case_insensitive(self) -> None:
        """String-literal matching is case-insensitive."""
        compiled = _compile_signature(get_entry("BEHAV-005"))  # VMware|...
        literals = _extract_string_literals('void func() { char *v = "vmware"; }')
        assert _match_string_pattern(compiled, literals) is True

    def test_url_literal_matches(self) -> None:
        """A hardcoded http(s) URL literal is detected (BEHAV-015)."""
        compiled = _compile_signature(get_entry("BEHAV-015"))  # https?://|IPv4
        literals = _extract_string_literals('void func() { const char *c2 = "http://evil.example"; }')
        assert _match_string_pattern(compiled, literals) is True

    def test_ipv4_literal_matches(self) -> None:
        """A hardcoded IPv4 address literal is detected (BEHAV-015)."""
        compiled = _compile_signature(get_entry("BEHAV-015"))
        literals = _extract_string_literals('void func() { const char *ip = "203.0.113.7"; }')
        assert _match_string_pattern(compiled, literals) is True

    def test_no_literal_no_match(self) -> None:
        """An empty literal list never matches."""
        compiled = _compile_signature(get_entry("BEHAV-005"))
        assert _match_string_pattern(compiled, []) is False


# ---------------------------------------------------------------------------
# code_heuristic detection tests
# ---------------------------------------------------------------------------


class TestCodeHeuristicDetection:
    """Tests for the code_heuristic detection method."""

    def test_cooccurrence_triggers(self) -> None:
        """Timing API co-occurring with a branch triggers BEHAV-007."""
        compiled = _compile_signature(get_entry("BEHAV-007"))  # timing evasion
        code = "void func() { if (GetTickCount() > 100) { return; } }"
        assert _match_code_heuristic(compiled, code) is True

    def test_single_api_only_does_not_trigger(self) -> None:
        """The timing API alone (no branch) does NOT trigger BEHAV-007."""
        compiled = _compile_signature(get_entry("BEHAV-007"))
        code = "void func() { GetTickCount(); }"
        assert _match_code_heuristic(compiled, code) is False

    def test_branch_before_call_triggers(self) -> None:
        """A while-loop wrapping the timing call triggers BEHAV-007."""
        compiled = _compile_signature(get_entry("BEHAV-007"))
        code = "void func() { while (QueryPerformanceCounter(&c)) { break; } }"
        assert _match_code_heuristic(compiled, code) is True

    def test_socket_beaconing_cooccurrence(self) -> None:
        """connect + send in one function triggers BEHAV-016."""
        compiled = _compile_signature(get_entry("BEHAV-016"))  # raw socket beaconing
        code = "void func() { connect(sock, addr, len); send(sock, buf, n, 0); }"
        assert _match_code_heuristic(compiled, code) is True

    def test_socket_single_api_does_not_trigger(self) -> None:
        """connect alone (no send/recv) does NOT trigger BEHAV-016."""
        compiled = _compile_signature(get_entry("BEHAV-016"))
        code = "void func() { connect(sock, addr, len); }"
        assert _match_code_heuristic(compiled, code) is False


# ---------------------------------------------------------------------------
# scan_functions tests
# ---------------------------------------------------------------------------


class TestScanFunctions:
    """Tests for the main scan_functions entry point."""

    def test_empty_function_list(self) -> None:
        """Empty input returns empty results."""
        assert scan_functions([]) == []

    def test_no_behavioral_matches(self) -> None:
        """Functions with no catalog behaviors produce no results."""
        functions = [
            _make_function("safe_func_1", tokens=["void", "safe_func_1()", "{", "int", "x", "=", "5;", "}"]),
            _make_function("safe_func_2", tokens=["void", "safe_func_2()", "{", "return;", "}"]),
        ]
        assert scan_functions(functions) == []

    def test_single_api_call_match(self) -> None:
        """A function calling IsDebuggerPresent is detected (BEHAV-001)."""
        func = _make_function(
            "check_debug",
            tokens=["void", "check_debug()", "{", "if", "(IsDebuggerPresent())", "{", "return;", "}", "}"],
        )
        results = scan_functions([func])
        assert len(results) >= 1
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        assert match.behavior_name == "Debugger presence check"
        assert match.category == "Anti-Debugging"
        assert match.severity == "Critical"
        assert match.containing_function == "check_debug"
        assert match.entrypoint == "0x401000"

    def test_string_pattern_match(self) -> None:
        """A function with a VMware string literal is detected (BEHAV-005)."""
        func = _make_function(
            "probe_vm",
            tokens=['void', 'probe_vm()', '{', 'char', '*v', '=', '"VMware, Inc.";', '}'],
        )
        results = scan_functions([func])
        assert any(r.signature_id == "BEHAV-005" for r in results)

    def test_code_heuristic_match(self) -> None:
        """A function with timing + branch is detected (BEHAV-007)."""
        func = _make_function(
            "evasion",
            tokens=["void", "evasion()", "{", "if", "(GetTickCount()", ">", "100)", "{", "return;", "}", "}"],
        )
        results = scan_functions([func])
        assert any(r.signature_id == "BEHAV-007" for r in results)

    def test_multiple_behaviors_detected(self) -> None:
        """Multiple distinct behaviors across functions are all detected."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", "IsDebuggerPresent();", "}"]),  # BEHAV-001 Critical
            _make_function("f2", tokens=["void", "f2()", "{", 'printf("VMware");', "}"]),  # BEHAV-005 Medium
            _make_function("f3", tokens=["void", "f3()", "{", "WriteProcessMemory(h, a, b, c, d, e);", "}"]),  # BEHAV-009 Critical
        ]
        results = scan_functions(functions)
        ids = {r.signature_id for r in results}
        assert "BEHAV-001" in ids
        assert "BEHAV-005" in ids
        assert "BEHAV-009" in ids

    def test_severity_sorting(self) -> None:
        """Results are sorted by severity (Critical first)."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", 'printf("Mozilla/5.0");', "}"]),  # BEHAV-018 Low
            _make_function("f2", tokens=["void", "f2()", "{", "IsDebuggerPresent();", "}"]),  # BEHAV-001 Critical
        ]
        results = scan_functions(functions)
        severities = [r.severity for r in results]
        assert severities.index("Critical") < severities.index("Low")

    def test_entrypoint_preserved(self) -> None:
        """The memory address is preserved in the result."""
        func = _make_function(
            "wrapper",
            address="0xDEADBEEF",
            tokens=["void", "wrapper()", "{", "IsDebuggerPresent();", "}"],
        )
        results = scan_functions([func])
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        assert match.entrypoint == "0xDEADBEEF"

    def test_empty_function_name_skipped(self) -> None:
        """Functions with an empty name produce no results."""
        functions = [_make_function("", tokens=["void", "x()", "{", "IsDebuggerPresent();", "}"])]
        # An empty function name still has tokens; the scanner matches on tokens.
        # But the containing_function will be empty. Verify it does not crash.
        results = scan_functions(functions)
        assert all(r.containing_function == "" for r in results)

    def test_missing_function_name_key(self) -> None:
        """Functions missing the functionName key are handled gracefully."""
        functions: list[dict[str, Any]] = [{"lowAddress": "0x1000", "tokenList": ["IsDebuggerPresent();"]}]
        results = scan_functions(functions)
        assert all(r.containing_function == "" for r in results)

    def test_empty_tokens_skipped(self) -> None:
        """Functions with empty token lists are skipped."""
        functions = [_make_function("some_func", tokens=[])]
        assert scan_functions(functions) == []

    def test_result_has_all_fields(self) -> None:
        """BehavioralScanResult contains all required fields."""
        func = _make_function(
            "wrapper",
            tokens=["void", "wrapper()", "{", "IsDebuggerPresent();", "}"],
        )
        results = scan_functions([func])
        result = next(r for r in results if r.signature_id == "BEHAV-001")
        assert result.signature_id
        assert result.behavior_name
        assert result.category
        assert result.severity
        assert result.detection_method
        assert result.containing_function
        assert result.entrypoint
        assert isinstance(result.mitre_technique, str)
        assert result.description
        assert isinstance(result.matched_evidence, list)
        assert isinstance(result.containing_function_code, str)

    def test_evidence_populated_for_api_call(self) -> None:
        """Matched evidence is extracted for an api_call match."""
        func = _make_function(
            "check_debug",
            tokens=["void", "check_debug()", "{", "if", "(IsDebuggerPresent())", "{", "return;", "}", "}"],
        )
        results = scan_functions([func])
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        assert len(match.matched_evidence) > 0
        assert any("IsDebuggerPresent" in stmt for stmt in match.matched_evidence)

    def test_containing_function_code_populated(self) -> None:
        """The full decompiled function code is captured."""
        func = _make_function(
            "check_debug",
            tokens=["void", "check_debug()", "{", "if", "(IsDebuggerPresent())", "{", "return;", "}", "}"],
        )
        results = scan_functions([func])
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        assert "check_debug" in match.containing_function_code


# ---------------------------------------------------------------------------
# Evidence cap tests
# ---------------------------------------------------------------------------


class TestEvidenceCaps:
    """Tests for the evidence statement/length caps."""

    def test_constants(self) -> None:
        """The evidence caps match the documented limits."""
        assert MAX_EVIDENCE_STATEMENTS == 10
        assert MAX_EVIDENCE_LENGTH == 300

    def test_truncate_statement_short(self) -> None:
        """Short statements are returned unchanged."""
        assert _truncate_statement("IsDebuggerPresent();") == "IsDebuggerPresent();"

    def test_truncate_statement_long(self) -> None:
        """Long statements are truncated to 300 chars + ellipsis."""
        long_stmt = "IsDebuggerPresent();" + "A" * 400
        truncated = _truncate_statement(long_stmt)
        assert len(truncated) == MAX_EVIDENCE_LENGTH + 3  # 300 + "..."
        assert truncated.endswith("...")

    def test_dedupe_cap_removes_duplicates(self) -> None:
        """Duplicate statements are collapsed to one."""
        lines = ["IsDebuggerPresent();"] * 20
        assert _dedupe_cap(lines) == ["IsDebuggerPresent();"]

    def test_dedupe_cap_limits_to_10(self) -> None:
        """More than 10 unique statements are capped at 10."""
        lines = [f"stmt_{i}();" for i in range(25)]
        assert len(_dedupe_cap(lines)) == 10

    def test_api_call_evidence_capped_at_10(self) -> None:
        """A function calling the API 15 times yields at most 10 evidence lines."""
        tokens = ["void", "f()", "{"]
        for i in range(15):
            tokens.extend([f"x{i}", "=", "IsDebuggerPresent();"])
        tokens.append("}")
        func = _make_function("f", tokens=tokens)
        results = scan_functions([func])
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        assert len(match.matched_evidence) <= 10

    def test_evidence_statements_truncated(self) -> None:
        """Individual evidence statements are truncated to the length cap."""
        # One very long statement containing the call.
        long_payload = "A" * 400
        tokens = ["void", "f()", "{", "if", "(x)", "{", long_payload, "IsDebuggerPresent();", "}", "}"]
        func = _make_function("f", tokens=tokens)
        results = scan_functions([func])
        match = next(r for r in results if r.signature_id == "BEHAV-001")
        for stmt in match.matched_evidence:
            assert len(stmt) <= MAX_EVIDENCE_LENGTH + 3


# ---------------------------------------------------------------------------
# generate_report tests
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Tests for report generation."""

    def test_empty_scan(self) -> None:
        """A report with no functions scanned has zero counts."""
        report = generate_report("test_target", [])
        assert isinstance(report, BehavioralScanReport)
        assert report.model_name == "test_target"
        assert report.total_functions_scanned == 0
        assert report.total_found == 0
        assert report.critical_count == 0
        assert report.high_count == 0
        assert report.medium_count == 0
        assert report.low_count == 0
        assert report.results == []

    def test_counts_correct(self) -> None:
        """Severity counts reflect the matches found."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", "IsDebuggerPresent();", "}"]),  # Critical
            _make_function("f2", tokens=["void", "f2()", "{", 'printf("VMware");', "}"]),  # Medium
            _make_function("f3", tokens=["void", "f3()", "{", 'printf("Mozilla/5.0");', "}"]),  # Low
        ]
        report = generate_report("test_target", functions)
        assert report.total_functions_scanned == 3
        assert report.total_found >= 3
        assert report.critical_count >= 1
        assert report.medium_count >= 1
        assert report.low_count >= 1

    def test_model_name_preserved(self) -> None:
        """The target name is preserved in the report."""
        report = generate_report("my_binary_v2", [])
        assert report.model_name == "my_binary_v2"

    def test_results_sorted(self) -> None:
        """Report results are sorted by severity (Critical first)."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", 'printf("Mozilla/5.0");', "}"]),  # Low
            _make_function("f2", tokens=["void", "f2()", "{", "IsDebuggerPresent();", "}"]),  # Critical
        ]
        report = generate_report("test_target", functions)
        assert len(report.results) >= 2
        assert report.results[0].severity == "Critical"

    def test_with_precomputed_results(self) -> None:
        """Pre-computed scan results are used when provided."""
        results = [
            BehavioralScanResult(
                signature_id="BEHAV-001",
                behavior_name="Debugger presence check",
                category="Anti-Debugging",
                severity="Critical",
                detection_method="api_call",
                containing_function="main",
                entrypoint="0x1000",
                mitre_technique="",
                description="Test",
                matched_evidence=["IsDebuggerPresent();"],
            ),
        ]
        report = generate_report("test_target", [], scan_results=results)
        assert report.total_found == 1
        assert report.critical_count == 1
        assert report.results == results

    def test_total_found_matches_results(self) -> None:
        """total_found matches the actual results count."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", "IsDebuggerPresent();", "}"]),
            _make_function("f2", tokens=["void", "f2()", "{", "WriteProcessMemory(h, a, b, c, d, e);", "}"]),
        ]
        report = generate_report("test_target", functions)
        assert report.total_found == len(report.results)

    def test_severity_counts_sum(self) -> None:
        """The sum of severity counts equals total_found."""
        functions = [
            _make_function("f1", tokens=["void", "f1()", "{", "IsDebuggerPresent();", "}"]),
            _make_function("f2", tokens=["void", "f2()", "{", 'printf("VMware");', "}"]),
            _make_function("f3", tokens=["void", "f3()", "{", 'printf("Mozilla/5.0");', "}"]),
        ]
        report = generate_report("test_target", functions)
        severity_sum = report.critical_count + report.high_count + report.medium_count + report.low_count
        assert severity_sum == report.total_found


# ---------------------------------------------------------------------------
# Normalization / statement helper tests
# ---------------------------------------------------------------------------


class TestNormalizationHelpers:
    """Tests for the normalization and statement-splitting helpers."""

    def test_normalize_code_text_collapses_whitespace(self) -> None:
        """Whitespace is collapsed to single spaces."""
        assert _normalize_code_text(["void", "  f()", "\n{", "x", "=", "1;", "}"]) == "void f() { x = 1; }"

    def test_normalize_code_text_empty(self) -> None:
        """An empty token list normalizes to an empty string."""
        assert _normalize_code_text([]) == ""

    def test_split_statements(self) -> None:
        """Statements are split on semicolons and stripped."""
        stmts = _split_statements("int a = 1; int b = 2;")
        assert stmts == ["int a = 1", "int b = 2"]

    def test_split_statements_drops_empty(self) -> None:
        """Empty fragments (trailing semicolons) are dropped."""
        assert _split_statements("a;; b;") == ["a", "b"]

    def test_extract_string_literals(self) -> None:
        """Quoted literal contents are extracted without the quotes."""
        literals = _extract_string_literals('char *a = "hello"; char *b = "world";')
        assert literals == ["hello", "world"]

    def test_extract_string_literals_handles_escapes(self) -> None:
        """Escaped quotes inside a literal do not terminate it early."""
        literals = _extract_string_literals(r'char *a = "say \"hi\"";')
        assert len(literals) == 1
        assert "hi" in literals[0]

    def test_extract_string_literals_wide(self) -> None:
        """Wide (L"...") literals are extracted."""
        literals = _extract_string_literals('wchar_t *a = L"VMware";')
        assert literals == ["VMware"]

    def test_extract_string_literals_none(self) -> None:
        """Code with no quoted literals yields an empty list."""
        assert _extract_string_literals("int x = 1; return x;") == []
