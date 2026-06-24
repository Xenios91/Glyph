"""Call graph generation service for binary analysis.

Extracts function call relationships from decompiled C code by parsing
function calls in the raw decompiled output. Builds a directed graph
representing which functions call which other functions within a binary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class CallEdge:
    """A single edge in the call graph.

    Attributes:
        caller: Name of the calling function.
        callee: Name of the called function.
        call_count: Number of times caller invokes callee.
    """

    caller: str
    callee: str
    call_count: int = 1


@dataclass
class CallGraphNode:
    """A node in the call graph representing a single function.

    Attributes:
        name: Function name.
        entrypoint: Memory address of the function.
        callers: Functions that call this function.
        callees: Functions called by this function.
    """

    name: str
    entrypoint: str = ""
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)


@dataclass
class CallGraph:
    """Complete call graph for a single binary.

    Attributes:
        binary_id: Database ID of the parent binary.
        nodes: All functions in the graph.
        edges: All call relationships between functions.
        known_functions: Set of known function names (for filtering).
    """

    binary_id: int
    nodes: dict[str, CallGraphNode] = field(default_factory=dict)
    edges: list[CallEdge] = field(default_factory=list)
    known_functions: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the call graph to a dictionary.

        Returns:
            Dictionary with nodes and edges suitable for JSON serialization.
        """
        return {
            "binary_id": self.binary_id,
            "nodes": [
                {
                    "name": node.name,
                    "entrypoint": node.entrypoint,
                    "callers": sorted(set(node.callers)),
                    "callees": sorted(set(node.callees)),
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {"caller": e.caller, "callee": e.callee, "call_count": e.call_count}
                for e in self.edges
            ],
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }


# Regex pattern to match function calls in C code.
# Matches identifier followed by opening parenthesis, excluding common
# false positives like control flow keywords.
_CALL_PATTERN = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
)

# Keywords and patterns that look like function calls but are not.
_NON_CALL_KEYWORDS: set[str] = {
    "if", "else", "for", "while", "do", "switch", "case", "return",
    "sizeof", "typeof", "alignof", "offsetof", "typedef", "struct",
    "union", "enum", "void", "int", "char", "short", "long", "float",
    "double", "unsigned", "signed", "const", "static", "volatile",
    "extern", "register", "auto", "goto", "break", "continue",
    "default", "typedef",
}


class CallGraphService:
    """Service for generating call graphs from decompiled functions.

    Parses raw decompiled C code to extract function call relationships
    and builds a directed graph of caller-callee relationships.
    """

    @staticmethod
    async def generate_call_graph(binary_id: int) -> CallGraph:
        """Generate a call graph for the given binary.

        Loads all functions for the binary from the database, parses
        each function's decompiled code for call sites, and builds
        the call graph.

        Args:
            binary_id: Database ID of the binary.

        Returns:
            CallGraph containing all nodes and edges.
        """
        from app.database.sql_service import SQLUtil

        functions = await SQLUtil.get_binary_functions(binary_id)

        if not functions:
            logger.warning("No functions found for binary {}", binary_id)
            return CallGraph(binary_id=binary_id)

        # Collect known function names for filtering
        known_functions = {f.function_name for f in functions}
        function_map = {f.function_name: f for f in functions}

        graph = CallGraph(binary_id=binary_id, known_functions=known_functions)

        # Create nodes for all functions
        for f in functions:
            graph.nodes[f.function_name] = CallGraphNode(
                name=f.function_name,
                entrypoint=str(f.entrypoint),
            )

        # Parse call sites
        edge_counts: dict[tuple[str, str], int] = {}

        for f in functions:
            caller = f.function_name
            raw_code = f.raw_code or ""

            # Extract all potential call targets
            for match in _CALL_PATTERN.finditer(raw_code):
                callee_candidate = match.group(1)

                # Skip non-call keywords
                if callee_candidate in _NON_CALL_KEYWORDS:
                    continue

                # Only include edges where callee is a known function
                if callee_candidate in known_functions:
                    key = (caller, callee_candidate)
                    edge_counts[key] = edge_counts.get(key, 0) + 1

        # Build edges from counted calls
        for (caller, callee), count in edge_counts.items():
            edge = CallEdge(caller=caller, callee=callee, call_count=count)
            graph.edges.append(edge)

            # Update node relationships
            if caller in graph.nodes:
                graph.nodes[caller].callees.append(callee)
            if callee in graph.nodes:
                graph.nodes[callee].callers.append(caller)

        logger.info(
            "Call graph for binary {}: {} nodes, {} edges",
            binary_id,
            len(graph.nodes),
            len(graph.edges),
        )

        return graph

    @staticmethod
    def get_function_callers(graph: CallGraph, function_name: str) -> list[str]:
        """Get all functions that call the specified function.

        Args:
            graph: The generated call graph.
            function_name: Name of the target function.

        Returns:
            List of caller function names.
        """
        node = graph.nodes.get(function_name)
        if node is None:
            return []
        return sorted(set(node.callers))

    @staticmethod
    def get_function_callees(graph: CallGraph, function_name: str) -> list[str]:
        """Get all functions called by the specified function.

        Args:
            graph: The generated call graph.
            function_name: Name of the target function.

        Returns:
            List of callee function names.
        """
        node = graph.nodes.get(function_name)
        if node is None:
            return []
        return sorted(set(node.callees))

    @staticmethod
    def find_entry_points(graph: CallGraph) -> list[str]:
        """Find functions that are never called by any other function.

        These are typically entry points (main, start, etc.) or orphaned
        functions.

        Args:
            graph: The generated call graph.

        Returns:
            List of entry point function names.
        """
        entry_points = []
        for name, node in graph.nodes.items():
            if not node.callers:
                entry_points.append(name)
        return sorted(entry_points)
