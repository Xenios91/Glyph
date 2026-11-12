"""Empirical reproductions for confirmed taint-analysis bugs.

These tests assert the *correct* behavior and are expected to FAIL against the
current implementation, demonstrating each bug with concrete output.

Bug 1: A self-recursive sink is reported as its own tainted caller.
    `_backward_reachable` seeds the traversal from ``node.callers``. When the
    sink calls itself (a self-edge), the sink becomes its own depth-1 "caller",
    violating the documented invariant "The sink itself is not included" and
    inflating ``total_tainted_callers`` by one with a spurious row.

Bug 2: A function merely *named* like an input function is falsely flagged as
    an input receiver.
    `detect_input_receivers` scans the FULL ``raw_code`` (including the
    function's own signature line), unlike `build_graph_from_functions` which
    deliberately strips the signature to avoid self-matching. A function named
    ``read``/``recv``/``fgets``/... whose body calls no input function is still
    flagged, because its signature line contains ``name(``.
"""

from unittest.mock import AsyncMock, patch

from app.services.call_graph_service import CallGraphService
from app.services.taint_analysis_service import (
    MAX_DEPTH,
    TaintAnalysisService,
)


def _make_func(name: str, entrypoint: str = "0x401000", raw_code: str = "") -> "object":
    """Create a mock BinaryFunction-like object (mirrors the existing suite)."""
    from unittest.mock import MagicMock

    func = MagicMock()
    func.function_name = name
    func.entrypoint = entrypoint
    func.raw_code = raw_code
    return func


def _build_graph(functions: list, binary_id: int = 1) -> "object":
    return CallGraphService.build_graph_from_functions(binary_id, functions)


# ---------------------------------------------------------------------------
# Bug 1: self-recursive sink counts itself as a tainted caller
# ---------------------------------------------------------------------------


class TestSelfRecursiveSink:
    """The sink must never be reported as one of its own tainted callers."""

    def test_backward_reachable_excludes_self_recursive_sink(self) -> None:
        """A sink that calls itself must not appear in its own reachability map.

        Docstring of `_backward_reachable`: "The sink itself is not included."
        """
        funcs = [
            _make_func("sink", raw_code="undefined sink(void)\n{\n  sink();\n  strcpy(b, s);\n}"),
            _make_func("main", raw_code="undefined main(void)\n{\n  sink();\n  return 0;\n}"),
        ]
        graph = _build_graph(funcs)
        depths = TaintAnalysisService._backward_reachable(graph, "sink", MAX_DEPTH)
        # Correct behavior: only `main` reaches the sink; the sink is excluded.
        assert "sink" not in depths, (
            f"BUG: self-recursive sink is included in its own reachability map: {depths}"
        )
        assert depths == {"main": 1}, f"BUG: expected only main at depth 1, got {depths}"

    async def test_analyze_does_not_count_self_recursive_sink(self) -> None:
        """`analyze` must not list a self-recursive sink among its own callers."""
        funcs = [
            _make_func("sink", raw_code="undefined sink(void)\n{\n  sink();\n  strcpy(b, s);\n}"),
            _make_func("main", raw_code="undefined main(void)\n{\n  sink();\n  return 0;\n}"),
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
        caller_names = {c["function_name"] for c in report.tainted_callers}
        # Correct behavior: only `main` is a tainted caller of the sink.
        assert "sink" not in caller_names, (
            f"BUG: sink is listed as its own tainted caller: {sorted(caller_names)}"
        )
        assert report.total_tainted_callers == 1, (
            f"BUG: total_tainted_callers inflated by the sink's self-call: "
            f"{report.total_tainted_callers} (expected 1)"
        )


# ---------------------------------------------------------------------------
# Bug 2: function merely NAMED like an input function is falsely flagged
# ---------------------------------------------------------------------------


class TestInputReceiverNameFalsePositive:
    """A function name matching an input function must not imply it reads input."""

    def test_function_named_read_is_not_flagged(self) -> None:
        """`read` here is a function NAME, not a call to the libc `read()`."""
        funcs = [
            # Body calls `process`, not any input function. The only `read(`
            # token is the function's own signature.
            _make_func("read", raw_code="undefined read(char *p)\n{\n  process(p);\n}"),
            _make_func("process", raw_code="undefined process(char *p)\n{\n  return 0;\n}"),
        ]
        graph = _build_graph(funcs)
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == set(), (
            f"BUG: function merely NAMED 'read' was falsely flagged as an input "
            f"receiver: {receivers}"
        )

    def test_real_input_call_still_detected(self) -> None:
        """Sanity: a function that genuinely CALLS an input function is detected."""
        funcs = [
            _make_func("wrapper", raw_code="undefined wrapper(void)\n{\n  read(fd, buf, n);\n}"),
        ]
        graph = _build_graph(funcs)
        receivers = TaintAnalysisService.detect_input_receivers(graph, funcs)
        assert receivers == {"wrapper"}, f"real input call not detected: {receivers}"

    async def test_analyze_does_not_flag_name_only_input_receiver(self) -> None:
        """A name-only 'read' entry point must not appear as an input receiver.

        Impact: it would otherwise be reported as a source of attacker-controlled
        data and generate a spurious taint path to the sink.
        """
        funcs = [
            _make_func("read", raw_code="undefined read(void)\n{\n  sink();\n  return 0;\n}"),
            _make_func("sink", raw_code="undefined sink(void)\n{\n  strcpy(b, s);\n}"),
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
        # `read` is an entry point (nobody calls it) but does NOT read input.
        assert report.entry_points_reaching_sink == ["read"]
        assert report.input_receivers_reaching_sink == [], (
            f"BUG: 'read' (a function name, not an input call) was falsely "
            f"reported as an input receiver: {report.input_receivers_reaching_sink}"
        )
