"""Taint analysis service for dangerous function scan findings.

Performs a static, call-graph-based taint approximation for a dangerous
function call site (the "sink") found by the dangerous function scanner.
Because dangerous functions such as ``strcpy`` or ``system`` are external
libc calls, they are not nodes in the binary's call graph; the sink is the
in-binary function that *calls* the dangerous function. The service answers:
*which functions in the binary (especially entry points and functions that
receive external input) can reach the sink?*

This is a reachability approximation, not intra-procedural data-flow
taint tracking: the results identify functions that *can* reach the sink,
not proven flows of attacker-controlled data.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.services.call_graph_service import CallGraph, CallGraphService

# Maximum backward traversal depth from the sink. Call chains deeper than
# this are unlikely to be exploitable and the guard keeps the traversal
# bounded on pathological graphs.
MAX_DEPTH = 16

# Cap on the number of enumerated taint paths (source -> ... -> sink) so a
# highly connected graph cannot produce an unbounded report.
MAX_PATHS = 50

# Built-in set of external input-receiving functions. A binary function whose
# decompiled code calls any of these is considered an "input receiver"
# (i.e. it can obtain externally controlled data).
INPUT_FUNCTIONS: set[str] = {
    "scanf",
    "sscanf",
    "fscanf",
    "vscanf",
    "vfscanf",
    "gets",
    "fgets",
    "getline",
    "fread",
    "read",
    "recv",
    "receive",
    "getchar",
}

# Regex matching an identifier followed by an opening parenthesis, i.e. a
# function call site in decompiled C code. Mirrors the pattern used by the
# call graph service so detection stays consistent with graph construction.
_INPUT_CALL_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")


class TaintSinkNotFoundError(Exception):
    """Raised when the resolved taint sink is not a function of the binary.

    The endpoint maps this to a 404 response.
    """

    def __init__(self, sink_function: str, binary_id: int) -> None:
        self.sink_function = sink_function
        self.binary_id = binary_id
        super().__init__(f"Sink function '{sink_function}' not found in binary {binary_id}")


@dataclass
class TaintReport:
    """Result of a taint analysis for a single dangerous function finding.

    Attributes:
        binary_id: Database ID of the analyzed binary.
        sink_function: In-binary function that calls the dangerous function.
        dangerous_function: The dangerous (external) function, e.g. ``strcpy``.
        containing_function: Function reported by the scanner as containing
            the dangerous call site.
        total_tainted_callers: Number of binary functions that can reach the sink.
        entry_points_reaching_sink: Entry points (never called by any other
            binary function) that can reach the sink.
        input_receivers_reaching_sink: Functions that receive external input
            and can reach the sink.
        tainted_callers: One entry per function that can reach the sink.
        paths: Enumerated simple call chains from a source (entry point or
            input receiver) to the sink, each a list of function names in
            call order (source first, sink last).
        max_depth: Maximum traversal depth used for the analysis.

    """

    binary_id: int
    sink_function: str
    dangerous_function: str
    containing_function: str
    total_tainted_callers: int = 0
    entry_points_reaching_sink: list[str] = field(default_factory=list)
    input_receivers_reaching_sink: list[str] = field(default_factory=list)
    tainted_callers: list[dict[str, Any]] = field(default_factory=list)
    paths: list[list[str]] = field(default_factory=list)
    max_depth: int = MAX_DEPTH

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a JSON-friendly dictionary.

        Returns:
            Dictionary suitable for inclusion in an API response.

        """
        return {
            "binary_id": self.binary_id,
            "sink_function": self.sink_function,
            "dangerous_function": self.dangerous_function,
            "containing_function": self.containing_function,
            "total_tainted_callers": self.total_tainted_callers,
            "entry_points_reaching_sink": self.entry_points_reaching_sink,
            "input_receivers_reaching_sink": self.input_receivers_reaching_sink,
            "tainted_callers": self.tainted_callers,
            "paths": self.paths,
            "max_depth": self.max_depth,
        }


class TaintAnalysisService:
    """Service for static taint analysis of dangerous function call sites.

    Builds the binary's call graph and performs a backward reachability
    traversal from the sink (the in-binary function that calls the dangerous
    function), identifying entry points and input-receiving functions that
    can reach it.
    """

    @staticmethod
    def resolve_sink(function_name: str, containing_function: str | None) -> str:
        """Resolve the in-binary taint sink for a scan finding.

        Dangerous functions are external calls and are not graph nodes, so
        the sink is the in-binary function that calls them: the containing
        function when the finding is a body call, or the function itself
        when the finding is the function's own signature.

        Args:
            function_name: Dangerous function name from the finding.
            containing_function: Containing function from the finding.

        Returns:
            The in-binary sink function name.

        """
        if containing_function and containing_function != function_name:
            return containing_function
        return function_name

    @staticmethod
    def detect_input_receivers(graph: CallGraph, functions: list[Any]) -> set[str]:
        """Detect binary functions that receive external input.

        A function is an input receiver when its decompiled code contains a
        call to any function in the built-in input function set.

        Args:
            graph: The binary's call graph (used to restrict to known functions).
            functions: Function objects with ``function_name`` and ``raw_code``.

        Returns:
            Set of function names that receive external input.

        """
        receivers: set[str] = set()
        for f in functions:
            name = f.function_name
            if name not in graph.nodes:
                continue
            raw_code = f.raw_code or ""
            for match in _INPUT_CALL_PATTERN.finditer(raw_code):
                if match.group(1) in INPUT_FUNCTIONS:
                    receivers.add(name)
                    break
        return receivers

    @staticmethod
    def _backward_reachable(graph: CallGraph, sink: str, max_depth: int) -> dict[str, int]:
        """Compute all functions that can reach the sink, with their minimum depth.

        Performs a breadth-first traversal backward from the sink's direct
        callers, tracking the minimum number of call hops from each function
        to the sink. A visited set and the depth guard keep the traversal
        bounded and safe on graphs with cycles (e.g. mutual recursion).

        Args:
            graph: The binary's call graph.
            sink: Sink function name (must be a graph node).
            max_depth: Maximum traversal depth from the sink.

        Returns:
            Mapping of function name to minimum hop count to the sink
            (direct callers have depth 1). The sink itself is not included.

        """
        node = graph.nodes.get(sink)
        if node is None:
            return {}

        depths: dict[str, int] = {}
        queue: list[tuple[str, int]] = []
        for caller in sorted(set(node.callers)):
            if caller not in depths:
                depths[caller] = 1
                queue.append((caller, 1))

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            current_node = graph.nodes.get(current)
            if current_node is None:
                continue
            for caller in sorted(set(current_node.callers)):
                if caller not in depths:
                    depths[caller] = depth + 1
                    queue.append((caller, depth + 1))

        return depths

    @staticmethod
    def _enumerate_paths(
        graph: CallGraph,
        sink: str,
        sources: set[str],
        max_depth: int,
        max_paths: int,
    ) -> list[list[str]]:
        """Enumerate simple call chains from sources to the sink.

        A path is a list of function names in call order: the source first,
        the sink last. Each function appears at most once per path (simple
        paths), which also makes enumeration cycle-safe. Enumeration stops
        once ``max_paths`` paths have been found.

        The traversal starts at the sink and walks backward through callers;
        whenever a source (entry point or input receiver) is reached, the
        accumulated chain is recorded in call order (reversed).

        Args:
            graph: The binary's call graph.
            sink: Sink function name.
            sources: Candidate source functions (entry points / input receivers).
            max_depth: Maximum path length in edges (source -> ... -> sink).
            max_paths: Maximum number of paths to return.

        Returns:
            List of paths, each a list of function names.

        """
        # Reverse adjacency: function -> functions that call it.
        reverse: dict[str, set[str]] = {name: set(node.callers) for name, node in graph.nodes.items()}

        paths: list[list[str]] = []

        def extend(chain: list[str]) -> None:
            # chain is built backward from the sink: [sink, ..., current].
            if len(paths) >= max_paths:
                return
            current = chain[-1]
            if len(chain) - 1 >= max_depth:
                return  # depth guard: do not record sources deeper than max_depth
            for caller in sorted(reverse.get(current, ())):
                if caller in chain:
                    continue  # keep paths simple (cycle-safe)
                new_chain = [*chain, caller]
                if caller in sources:
                    # Reached a source; record the path in call order.
                    paths.append(list(reversed(new_chain)))
                extend(new_chain)
                if len(paths) >= max_paths:
                    return

        extend([sink])

        return paths

    @staticmethod
    async def analyze(
        binary_id: int,
        function_name: str,
        containing_function: str | None = None,
    ) -> TaintReport:
        """Run taint analysis for a dangerous function finding.

        Resolves the sink from the finding, builds the binary's call graph,
        detects input-receiving functions, performs a backward reachability
        traversal from the sink, and enumerates taint paths from entry
        points and input receivers to the sink.

        Args:
            binary_id: Database ID of the binary to analyze.
            function_name: Dangerous function name from the finding.
            containing_function: Containing function from the finding. When
                it differs from ``function_name`` it is used as the sink.

        Returns:
            TaintReport describing which functions can reach the sink.

        Raises:
            TaintSinkNotFoundError: When the resolved sink is not a function
                of the binary.

        """
        from app.database.binary_repository import BinaryRepository

        sink = TaintAnalysisService.resolve_sink(function_name, containing_function)

        functions = await BinaryRepository.get_functions(binary_id=binary_id)

        # An empty binary has no functions, so there is nothing to analyze:
        # return an empty (but valid) report rather than a sink error.
        if not functions:
            logger.info("Taint analysis for binary {}: no functions found, returning empty report", binary_id)
            return TaintReport(
                binary_id=binary_id,
                sink_function=sink,
                dangerous_function=function_name,
                containing_function=containing_function or function_name,
            )

        graph = CallGraphService.build_graph_from_functions(binary_id, functions)

        if sink not in graph.nodes:
            raise TaintSinkNotFoundError(sink, binary_id)

        entry_points = set(CallGraphService.find_entry_points(graph))
        input_receivers = TaintAnalysisService.detect_input_receivers(graph, functions)

        depths = TaintAnalysisService._backward_reachable(graph, sink, MAX_DEPTH)

        sink_node = graph.nodes[sink]
        tainted_callers: list[dict[str, Any]] = []
        for name in sorted(depths):
            node = graph.nodes.get(name)
            tainted_callers.append(
                {
                    "function_name": name,
                    "entrypoint": node.entrypoint if node else "",
                    "depth": depths[name],
                    "call_count": sink_node.callers.count(name) if name != sink else 0,
                    "is_entry_point": name in entry_points,
                    "is_input_receiver": name in input_receivers,
                }
            )

        sources = (entry_points | input_receivers) & set(depths)
        paths = TaintAnalysisService._enumerate_paths(graph, sink, sources, MAX_DEPTH, MAX_PATHS)

        report = TaintReport(
            binary_id=binary_id,
            sink_function=sink,
            dangerous_function=function_name,
            containing_function=containing_function or function_name,
            total_tainted_callers=len(tainted_callers),
            entry_points_reaching_sink=sorted(entry_points & set(depths)),
            input_receivers_reaching_sink=sorted(input_receivers & set(depths)),
            tainted_callers=tainted_callers,
            paths=paths,
            max_depth=MAX_DEPTH,
        )

        logger.info(
            "Taint analysis for binary {} sink '{}': {} tainted callers, {} entry points, {} paths",
            binary_id,
            sink,
            report.total_tainted_callers,
            len(report.entry_points_reaching_sink),
            len(report.paths),
        )

        return report
