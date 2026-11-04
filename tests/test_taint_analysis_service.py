"""Tests for TaintAnalysisService and the taint report data class."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.call_graph_service import CallGraph, CallGraphService
from app.services.taint_analysis_service import (
    MAX_DEPTH,
    TaintAnalysisService,
    TaintReport,
    TaintSinkNotFoundError,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_func(name: str, entrypoint: str = "0x401000", raw_code: str = "") -> MagicMock:
    """Create a mock BinaryFunction-like object."""
    func = MagicMock()
    func.function_name = name
    func.entrypoint = entrypoint
    func.raw_code = raw_code
    return func


def _build_graph(functions: list[MagicMock], binary_id: int = 1) -> CallGraph:
    """Build a call graph from mock functions (mirrors the service)."""
    return CallGraphService.build_graph_from_functions(binary_id, functions)


# ---------------------------------------------------------------------------
# TaintReport tests
# ---------------------------------------------------------------------------


class TestTaintReport:
    """Tests for the TaintReport data class."""

    def test_report_defaults(self) -> None:
        """Test TaintReport default values."""
        report = TaintReport(
            binary_id=1,
            sink_function="sink",
            dangerous_function="strcpy",
            containing_function="sink",
        )
        assert report.binary_id == 1
        assert report.sink_function == "sink"
        assert report.dangerous_function == "strcpy"
        assert report.containing_function == "sink"
        assert report.total_tainted_callers == 0
        assert report.entry_points_reaching_sink == []
        assert report.input_receivers_reaching_sink == []
        assert report.tainted_callers == []
        assert report.paths == []
        assert report.max_depth == MAX_DEPTH

    def test_report_to_dict(self) -> None:
        """Test TaintReport serialization."""
        report = TaintReport(
            binary_id=7,
            sink_function="sink",
            dangerous_function="strcpy",
            containing_function="sink",
            total_tainted_callers=2,
            entry_points_reaching_sink=["main"],
            input_receivers_reaching_sink=["reader"],
            tainted_callers=[{"function_name": "main", "depth": 2}],
            paths=[["main", "sink"]],
            max_depth=16,
        )
        result = report.to_dict()
        assert result["binary_id"] == 7
        assert result["sink_function"] == "sink"
        assert result["dangerous_function"] == "strcpy"
        assert result["containing_function"] == "sink"
        assert result["total_tainted_callers"] == 2
        assert result["entry_points_reaching_sink"] == ["main"]
        assert result["input_receivers_reaching_sink"] == ["reader"]
        assert result["tainted_callers"] == [{"function_name": "main", "depth": 2}]
        assert result["paths"] == [["main", "sink"]]
        assert result["max_depth"] == 16


# ---------------------------------------------------------------------------
# Sink resolution tests
# ---------------------------------------------------------------------------


class TestResolveSink:
    """Tests for sink resolution from a scan finding."""

    def test_body_call_uses_containing_function(self) -> None:
        """When function_name != containing_function, the containing function is the sink."""
        assert TaintAnalysisService.resolve_sink("strcpy", "vuln_func") == "vuln_func"

    def test_signature_call_uses_function_name(self) -> None:
        """When function_name == containing_function, the function itself is the sink."""
        assert TaintAnalysisService.resolve_sink("strcpy", "strcpy") == "strcpy"

    def test_missing_containing_uses_function_name(self) -> None:
        """When containing_function is None, the function name is the sink."""
        assert TaintAnalysisService.resolve_sink("strcpy", None) == "strcpy"


# ---------------------------------------------------------------------------
# Input receiver detection tests
# ---------------------------------------------------------------------------


class TestInputReceiverDetection:
    """Tests for detecting functions that receive external input."""

    def test_detects_scanf_caller(self) -> None:
        """A function whose code calls scanf is an input receiver."""
        funcs = [
            _make_func("reader", raw_code='int x; scanf("%d", &x);'),
            _make_func("plain", raw_code="return 0;"),
        ]
        graph = _build_graph(funcs)
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == {"reader"}

    def test_detects_multiple_input_functions(self) -> None:
        """Each of the built-in input functions triggers detection."""
        for input_fn in ("scanf", "gets", "fgets", "getline", "fread", "read", "recv", "receive", "getchar"):
            funcs = [_make_func("reader", raw_code=f"{input_fn}(buf, n);")]
            graph = _build_graph(funcs)
            receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
            assert receivers == {"reader"}, f"failed to detect {input_fn}"

    def test_no_input_functions(self) -> None:
        """A function with no input calls is not an input receiver."""
        funcs = [_make_func("plain", raw_code='printf("hi");')]
        graph = _build_graph(funcs)
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == set()

    def test_ignores_unknown_functions(self) -> None:
        """Functions not present in the graph are ignored."""
        funcs = [_make_func("reader", raw_code="scanf(x);")]
        # Build a graph that does NOT contain "reader".
        graph = CallGraph(binary_id=1, known_functions=set())
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == set()

    def test_none_raw_code_is_safe(self) -> None:
        """A function with None raw_code does not crash detection."""
        funcs = [_make_func("plain", raw_code=None)]
        graph = _build_graph(funcs)
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == set()


# ---------------------------------------------------------------------------
# Backward reachability tests
# ---------------------------------------------------------------------------


class TestBackwardReachability:
    """Tests for the backward reachability traversal."""

    def test_three_function_chain(self) -> None:
        """main -> mid -> sink: both main and mid reach the sink."""
        funcs = [
            _make_func("main", raw_code="mid();"),
            _make_func("mid", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "sink", MAX_DEPTH)
        assert depths == {"mid": 1, "main": 2}

    def test_direct_caller_depth_one(self) -> None:
        """A direct caller of the sink has depth 1."""
        funcs = [
            _make_func("caller", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "sink", MAX_DEPTH)
        assert depths == {"caller": 1}

    def test_sink_with_no_callers(self) -> None:
        """A sink nobody calls yields an empty reachability map."""
        funcs = [
            _make_func("sink", raw_code="strcpy(b, s);"),
            _make_func("unrelated", raw_code="return 0;"),
        ]
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "sink", MAX_DEPTH)
        assert depths == {}

    def test_max_depth_truncation(self) -> None:
        """Chains deeper than MAX_DEPTH are truncated."""
        # f0 -> f1 -> ... -> f19 -> sink (20 functions above the sink)
        funcs = []
        for k in range(20):
            callee = f"f{k + 1}" if k < 19 else "sink"
            funcs.append(_make_func(f"f{k}", raw_code=f"{callee}();"))
        funcs.append(_make_func("sink", raw_code="strcpy(b, s);"))
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "sink", MAX_DEPTH)
        # Only f19 (depth 1) through f4 (depth 16) are reachable.
        assert len(depths) == MAX_DEPTH
        assert depths["f19"] == 1
        assert depths["f4"] == MAX_DEPTH
        assert "f3" not in depths

    def test_mutual_recursion_terminates(self) -> None:
        """Mutual recursion (a <-> b) does not loop forever."""
        funcs = [
            _make_func("a", raw_code="b();"),
            _make_func("b", raw_code="a();"),
        ]
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "a", MAX_DEPTH)
        # Both a and b are reachable from a (via the cycle); result is finite.
        assert set(depths) == {"a", "b"}
        assert all(isinstance(d, int) for d in depths.values())


# ---------------------------------------------------------------------------
# Path enumeration tests
# ---------------------------------------------------------------------------


class TestPathEnumeration:
    """Tests for taint-path enumeration from sources to the sink."""

    def test_single_path_chain(self) -> None:
        """A linear chain yields one path from the entry point to the sink."""
        funcs = [
            _make_func("main", raw_code="mid();"),
            _make_func("mid", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        paths = TaintAnalysisService._enumerate_paths(graph, "sink", {"main"}, MAX_DEPTH, 50)
        assert paths == [["main", "mid", "sink"]]

    def test_multiple_sources(self) -> None:
        """Multiple entry points each produce their own path."""
        funcs = [
            _make_func("main_a", raw_code="sink();"),
            _make_func("main_b", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        paths = TaintAnalysisService._enumerate_paths(graph, "sink", {"main_a", "main_b"}, MAX_DEPTH, 50)
        assert sorted(paths) == [["main_a", "sink"], ["main_b", "sink"]]

    def test_no_sources_no_paths(self) -> None:
        """Without candidate sources there are no paths."""
        funcs = [
            _make_func("mid", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        paths = TaintAnalysisService._enumerate_paths(graph, "sink", set(), MAX_DEPTH, 50)
        assert paths == []

    def test_path_cap(self) -> None:
        """Enumeration stops at max_paths."""
        funcs = [_make_func(f"src{i}", raw_code="sink();") for i in range(10)]
        funcs.append(_make_func("sink", raw_code="strcpy(b, s);"))
        graph = _build_graph(funcs)
        sources = {f"src{i}" for i in range(10)}
        paths = TaintAnalysisService._enumerate_paths(graph, "sink", sources, MAX_DEPTH, 3)
        assert len(paths) == 3

    def test_cycle_safe(self) -> None:
        """Paths remain simple (no repeated function) on a cycle."""
        funcs = [
            _make_func("a", raw_code="b();"),
            _make_func("b", raw_code="a(); sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        graph = _build_graph(funcs)
        paths = TaintAnalysisService._enumerate_paths(graph, "sink", {"a"}, MAX_DEPTH, 50)
        for path in paths:
            assert len(path) == len(set(path)), "path must be simple (no repeats)"
            assert path[-1] == "sink"


# ---------------------------------------------------------------------------
# End-to-end analyze() tests
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Tests for the full TaintAnalysisService.analyze flow."""

    async def test_three_function_chain(self) -> None:
        """main -> mid -> sink: report identifies both callers and the path."""
        funcs = [
            _make_func("main", raw_code="mid();"),
            _make_func("mid", raw_code="sink();"),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="sink",
            )
        assert report.sink_function == "sink"
        assert report.dangerous_function == "strcpy"
        assert report.total_tainted_callers == 2
        assert report.entry_points_reaching_sink == ["main"]
        assert report.paths == [["main", "mid", "sink"]]
        # tainted_callers carries the expected keys.
        caller_names = {c["function_name"] for c in report.tainted_callers}
        assert caller_names == {"main", "mid"}
        for caller in report.tainted_callers:
            assert set(caller) == {
                "function_name",
                "entrypoint",
                "depth",
                "call_count",
                "is_entry_point",
                "is_input_receiver",
            }

    async def test_input_receiver_reaching_sink(self) -> None:
        """An entry point that reads input is flagged as an input receiver."""
        funcs = [
            _make_func("main", raw_code='scanf("%s", buf); sink();'),
            _make_func("sink", raw_code="strcpy(b, s);"),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="sink",
            )
        assert report.entry_points_reaching_sink == ["main"]
        assert report.input_receivers_reaching_sink == ["main"]
        main_caller = next(c for c in report.tainted_callers if c["function_name"] == "main")
        assert main_caller["is_input_receiver"] is True
        assert main_caller["is_entry_point"] is True

    async def test_sink_with_no_callers_empty_report(self) -> None:
        """A sink with no callers yields a valid empty report."""
        funcs = [
            _make_func("sink", raw_code="strcpy(b, s);"),
            _make_func("unrelated", raw_code="return 0;"),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="sink",
            )
        assert report.sink_function == "sink"
        assert report.total_tainted_callers == 0
        assert report.tainted_callers == []
        assert report.entry_points_reaching_sink == []
        assert report.paths == []

    async def test_external_function_name_uses_containing_function(self) -> None:
        """When function_name is external, the containing function is the sink."""
        funcs = [
            _make_func("vuln_func", raw_code="strcpy(b, s);"),
            _make_func("main", raw_code="vuln_func();"),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="vuln_func",
            )
        assert report.sink_function == "vuln_func"
        assert report.containing_function == "vuln_func"
        assert report.total_tainted_callers == 1
        assert report.entry_points_reaching_sink == ["main"]

    async def test_empty_binary_returns_empty_report(self) -> None:
        """An empty binary returns an empty but valid report (no error)."""
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=[],
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="sink",
            )
        assert report.sink_function == "sink"
        assert report.total_tainted_callers == 0
        assert report.tainted_callers == []
        assert report.paths == []

    async def test_sink_not_in_graph_raises(self) -> None:
        """A sink that is not a function of the binary raises the typed error."""
        funcs = [
            _make_func("other", raw_code="return 0;"),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            with pytest.raises(TaintSinkNotFoundError):
                await TaintAnalysisService.analyze(
                    binary_id=1,
                    function_name="strcpy",
                    containing_function="missing_func",
                )

    async def test_sink_error_carries_context(self) -> None:
        """The typed error exposes the sink name and binary id."""
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=[_make_func("other", raw_code="return 0;")],
        ):
            with pytest.raises(TaintSinkNotFoundError) as exc_info:
                await TaintAnalysisService.analyze(
                    binary_id=9,
                    function_name="strcpy",
                    containing_function="missing_func",
                )
        assert exc_info.value.sink_function == "missing_func"
        assert exc_info.value.binary_id == 9


# ---------------------------------------------------------------------------
# Regression tests: realistic Ghidra raw_code (signature line + body)
# ---------------------------------------------------------------------------
# Real Ghidra raw_code (from getPlainC()) includes each function's own
# signature. The call-site regex matched the function's own name in its
# signature, creating a spurious self-edge for every function, so
# find_entry_points() returned [] and entry_points_reaching_sink was always
# empty (the "no input or entry" false-negative bug).


@pytest.mark.regression
class TestGhidraSignatureRegression:
    """Regression tests for the empty entry-points false negative."""

    async def test_entry_points_reaching_sink_with_realistic_signatures(self) -> None:
        """Entry points reaching a sink are reported when raw_code has signatures.

        main (reads input, calls vuln_func) -> vuln_func (calls strcpy).
        With the bug, every function had a spurious self-edge, so
        find_entry_points() returned [] and the report had no entry points.
        """
        funcs = [
            _make_func(
                "main",
                raw_code=(
                    "undefined main(void)\n"
                    "{\n"
                    "  char buf[0x20];\n"
                    '  scanf("%s", buf);\n'
                    "  vuln_func(buf);\n"
                    "  return 0;\n"
                    "}\n"
                ),
            ),
            _make_func(
                "vuln_func",
                raw_code=(
                    "undefined vuln_func(char *param_1)\n"
                    "{\n"
                    "  char local_buf[0x20];\n"
                    "  strcpy(local_buf, param_1);\n"
                    "  return;\n"
                    "}\n"
                ),
            ),
        ]
        with patch(
            "app.database.binary_repository.BinaryRepository.get_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            report = await TaintAnalysisService.analyze(
                binary_id=1,
                function_name="strcpy",
                containing_function="vuln_func",
            )
        assert report.sink_function == "vuln_func"
        assert report.total_tainted_callers == 1
        assert report.entry_points_reaching_sink == ["main"]
        assert report.input_receivers_reaching_sink == ["main"]
        assert report.paths == [["main", "vuln_func"]]
