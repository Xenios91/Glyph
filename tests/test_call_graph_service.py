"""Tests for CallGraphService and call graph data classes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.call_graph_service import (
    _CALL_PATTERN,
    _NON_CALL_KEYWORDS,
    CallEdge,
    CallGraph,
    CallGraphNode,
    CallGraphService,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_mock_function(
    name: str,
    entrypoint: str = "0x401000",
    raw_code: str = "",
    tokens: str = "",
    function_id: int = 1,
) -> MagicMock:
    """Create a mock BinaryFunction-like object."""
    func = MagicMock()
    func.function_id = function_id
    func.function_name = name
    func.entrypoint = entrypoint
    func.raw_code = raw_code
    func.tokens = tokens
    return func


# ---------------------------------------------------------------------------
# CallEdge tests
# ---------------------------------------------------------------------------


class TestCallEdge:
    """Tests for CallEdge dataclass."""

    def test_call_edge_defaults(self) -> None:
        """Test CallEdge default call_count is 1."""
        edge = CallEdge(caller="main", callee="helper")
        assert edge.caller == "main"
        assert edge.callee == "helper"
        assert edge.call_count == 1

    def test_call_edge_explicit_count(self) -> None:
        """Test CallEdge with explicit call_count."""
        edge = CallEdge(caller="main", callee="helper", call_count=5)
        assert edge.call_count == 5


# ---------------------------------------------------------------------------
# CallGraphNode tests
# ---------------------------------------------------------------------------


class TestCallGraphNode:
    """Tests for CallGraphNode dataclass."""

    def test_call_graph_node_defaults(self) -> None:
        """Test CallGraphNode default values."""
        node = CallGraphNode(name="main")
        assert node.name == "main"
        assert node.entrypoint == ""
        assert node.callers == []
        assert node.callees == []

    def test_call_graph_node_with_entrypoint(self) -> None:
        """Test CallGraphNode with entrypoint."""
        node = CallGraphNode(name="main", entrypoint="0x401000")
        assert node.entrypoint == "0x401000"

    def test_call_graph_node_with_relationships(self) -> None:
        """Test CallGraphNode with callers and callees."""
        node = CallGraphNode(
            name="helper",
            entrypoint="0x401100",
            callers=["main", "init"],
            callees=["printf"],
        )
        assert "main" in node.callers
        assert "init" in node.callers
        assert "printf" in node.callees


# ---------------------------------------------------------------------------
# CallGraph tests
# ---------------------------------------------------------------------------


class TestCallGraph:
    """Tests for CallGraph dataclass."""

    def test_call_graph_defaults(self) -> None:
        """Test CallGraph default values."""
        graph = CallGraph(binary_id=42)
        assert graph.binary_id == 42
        assert graph.nodes == {}
        assert graph.edges == []
        assert graph.known_functions == set()

    def test_call_graph_to_dict_empty(self) -> None:
        """Test to_dict on empty graph."""
        graph = CallGraph(binary_id=42)
        result = graph.to_dict()
        assert result["binary_id"] == 42
        assert result["nodes"] == []
        assert result["edges"] == []
        assert result["total_nodes"] == 0
        assert result["total_edges"] == 0

    def test_call_graph_to_dict_with_data(self) -> None:
        """Test to_dict with nodes and edges."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", entrypoint="0x401000", callers=[], callees=["helper"])
        graph.nodes["helper"] = CallGraphNode(name="helper", entrypoint="0x401100", callers=["main"], callees=[])
        graph.edges.append(CallEdge(caller="main", callee="helper", call_count=2))

        result = graph.to_dict()
        assert result["binary_id"] == 1
        assert result["total_nodes"] == 2
        assert result["total_edges"] == 1
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["edges"][0]["call_count"] == 2

    def test_call_graph_to_dict_sorts_callers_and_callees(self) -> None:
        """Test that to_dict returns sorted callers and callees."""
        graph = CallGraph(binary_id=1)
        graph.nodes["mid"] = CallGraphNode(
            name="mid",
            entrypoint="0x401100",
            callers=["z_func", "a_func"],
            callees=["z_callee", "a_callee"],
        )

        result = graph.to_dict()
        node = result["nodes"][0]
        assert node["callers"] == ["a_func", "z_func"]
        assert node["callees"] == ["a_callee", "z_callee"]

    def test_call_graph_to_dict_returns_new_list_each_call(self) -> None:
        """Test that to_dict returns independent copies."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main")

        result1 = graph.to_dict()
        result2 = graph.to_dict()
        result1["nodes"].append({"name": "fake"})
        assert len(result2["nodes"]) == 1


# ---------------------------------------------------------------------------
# _CALL_PATTERN regex tests
# ---------------------------------------------------------------------------


class TestCallPattern:
    """Tests for the _CALL_PATTERN regex."""

    def test_pattern_matches_simple_call(self) -> None:
        """Test pattern matches simple function call."""
        match = _CALL_PATTERN.search("foo()")
        assert match is not None
        assert match.group(1) == "foo"

    def test_pattern_matches_call_with_args(self) -> None:
        """Test pattern matches function call with arguments."""
        match = _CALL_PATTERN.search("bar(x, y)")
        assert match is not None
        assert match.group(1) == "bar"

    def test_pattern_matches_underscore_name(self) -> None:
        """Test pattern matches function with underscore."""
        match = _CALL_PATTERN.search("_start()")
        assert match is not None
        assert match.group(1) == "_start"

    def test_pattern_no_match_for_keyword(self) -> None:
        """Test pattern still matches keywords (filtered later)."""
        match = _CALL_PATTERN.search("if (x)")
        assert match is not None
        assert match.group(1) == "if"

    def test_pattern_multiple_matches(self) -> None:
        """Test pattern finds multiple calls."""
        code = "foo(); bar(x); baz();"
        matches = _CALL_PATTERN.findall(code)
        assert "foo" in matches
        assert "bar" in matches
        assert "baz" in matches

    def test_pattern_underscore_start(self) -> None:
        """Test pattern matches function names starting with underscore."""
        match = _CALL_PATTERN.search("__libc_start_main(0)")
        assert match is not None
        assert match.group(1) == "__libc_start_main"


# ---------------------------------------------------------------------------
# _NON_CALL_KEYWORDS tests
# ---------------------------------------------------------------------------


class TestNonCallKeywords:
    """Tests for _NON_CALL_KEYWORDS set."""

    def test_common_keywords_present(self) -> None:
        """Test that common C keywords are in the exclusion set."""
        keywords = {"if", "for", "while", "switch", "sizeof", "return"}
        assert keywords.issubset(_NON_CALL_KEYWORDS)

    def test_type_keywords_present(self) -> None:
        """Test that type keywords are in the exclusion set."""
        types = {"int", "char", "void", "float", "double", "long"}
        assert types.issubset(_NON_CALL_KEYWORDS)

    def test_function_name_not_in_keywords(self) -> None:
        """Test that common function names are NOT in the exclusion set."""
        functions = {"main", "printf", "malloc", "free", "exit"}
        assert functions.isdisjoint(_NON_CALL_KEYWORDS)


# ---------------------------------------------------------------------------
# CallGraphService.generate_call_graph tests
# ---------------------------------------------------------------------------
# NOTE: raw_code values use function bodies only (no declaration signatures)
# to avoid the regex matching the function's own name as a self-call.


class TestGenerateCallGraph:
    """Tests for CallGraphService.generate_call_graph."""

    @pytest.mark.asyncio
    async def test_generate_empty_when_no_functions(self) -> None:
        """Test generates empty graph when no functions exist."""
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert graph.binary_id == 1
            assert graph.nodes == {}
            assert graph.edges == []
            assert graph.known_functions == set()

    @pytest.mark.asyncio
    async def test_generate_single_function_no_calls(self) -> None:
        """Test generates graph with single function having no calls."""
        func = _make_mock_function("main", raw_code="{ return 0; }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert "main" in graph.nodes
            assert graph.edges == []
            assert graph.known_functions == {"main"}

    @pytest.mark.asyncio
    async def test_generate_simple_call_chain(self) -> None:
        """Test generates graph with simple caller-callee relationship."""
        main_func = _make_mock_function("main", raw_code="{ helper(); }")
        helper_func = _make_mock_function("helper", raw_code="{ }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[main_func, helper_func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert "main" in graph.nodes
            assert "helper" in graph.nodes
            assert len(graph.edges) == 1
            assert graph.edges[0].caller == "main"
            assert graph.edges[0].callee == "helper"
            assert graph.edges[0].call_count == 1

    @pytest.mark.asyncio
    async def test_generate_multiple_calls_same_function(self) -> None:
        """Test counts multiple calls to the same function."""
        main_func = _make_mock_function("main", raw_code="{ helper(); helper(); helper(); }")
        helper_func = _make_mock_function("helper", raw_code="{ }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[main_func, helper_func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert len(graph.edges) == 1
            assert graph.edges[0].call_count == 3

    @pytest.mark.asyncio
    async def test_generate_ignores_unknown_callees(self) -> None:
        """Test ignores calls to functions not in known_functions."""
        main_func = _make_mock_function("main", raw_code="{ printf(); helper(); }")
        helper_func = _make_mock_function("helper", raw_code="{ }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[main_func, helper_func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            # printf is not a known function, so it should be filtered out
            assert len(graph.edges) == 1
            assert graph.edges[0].callee == "helper"

    @pytest.mark.asyncio
    async def test_generate_filters_keywords(self) -> None:
        """Test that C keywords are filtered from call patterns."""
        main_func = _make_mock_function(
            "main",
            raw_code=("{\n  if (x) { helper(); }\n  for (int i=0; i<10; i++) { }\n  while (y) { }\n  sizeof(int);\n}"),
        )
        helper_func = _make_mock_function("helper", raw_code="{ }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[main_func, helper_func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert len(graph.edges) == 1
            assert graph.edges[0].callee == "helper"

    @pytest.mark.asyncio
    async def test_generate_complex_graph(self) -> None:
        """Test generates complex graph with multiple relationships."""
        funcs = [
            _make_mock_function("main", raw_code="{ init(); process(); cleanup(); }"),
            _make_mock_function("init", raw_code="{ log(); }"),
            _make_mock_function("process", raw_code="{ helper(); helper(); }"),
            _make_mock_function("cleanup", raw_code="{ log(); }"),
            _make_mock_function("helper", raw_code="{ }"),
            _make_mock_function("log", raw_code="{ }"),
        ]
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=funcs,
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert len(graph.nodes) == 6

            # main -> init, process, cleanup
            # process -> helper (x2)
            # init -> log
            # cleanup -> log
            expected_edges = 6
            # 3 from main + 1 init->log + 1 process->helper + 1 cleanup->log = 6
            assert len(graph.edges) == expected_edges

            # Verify node relationships
            main_node = graph.nodes["main"]
            assert "init" in main_node.callees
            assert "process" in main_node.callees
            assert "cleanup" in main_node.callees

            helper_node = graph.nodes["helper"]
            assert "process" in helper_node.callers

    @pytest.mark.asyncio
    async def test_generate_handles_none_raw_code(self) -> None:
        """Test handles functions with None raw_code gracefully."""
        func = _make_mock_function("main", raw_code=None)
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert "main" in graph.nodes
            assert graph.edges == []

    @pytest.mark.asyncio
    async def test_generate_recursive_function(self) -> None:
        """Test recursive function creates single edge with proper count."""
        func = _make_mock_function(
            "factorial",
            raw_code="{ if (n<=1) return 1; return n * factorial(n-1); }",
        )
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert len(graph.edges) == 1
            assert graph.edges[0].caller == "factorial"
            assert graph.edges[0].callee == "factorial"
            assert graph.edges[0].call_count == 1

    @pytest.mark.asyncio
    async def test_generate_empty_raw_code(self) -> None:
        """Test handles empty string raw_code."""
        func = _make_mock_function("main", raw_code="")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert "main" in graph.nodes
            assert graph.edges == []

    @pytest.mark.asyncio
    async def test_generate_sets_node_entrypoint(self) -> None:
        """Test that node entrypoints come from function data."""
        func = _make_mock_function("main", entrypoint="0xdeadbeef", raw_code="{ }")
        with patch(
            "app.database.sql_service.SQLUtil.get_binary_functions",
            new_callable=AsyncMock,
            return_value=[func],
        ):
            graph = await CallGraphService.generate_call_graph(binary_id=1)
            assert graph.nodes["main"].entrypoint == "0xdeadbeef"


# ---------------------------------------------------------------------------
# CallGraphService.get_function_callers tests
# ---------------------------------------------------------------------------


class TestGetFunctionCallers:
    """Tests for CallGraphService.get_function_callers."""

    def test_get_callers_returns_sorted_list(self) -> None:
        """Test returns sorted list of callers."""
        graph = CallGraph(binary_id=1)
        graph.nodes["helper"] = CallGraphNode(name="helper", callers=["z_func", "a_func", "m_func"])
        result = CallGraphService.get_function_callers(graph, "helper")
        assert result == ["a_func", "m_func", "z_func"]

    def test_get_callers_empty_when_no_callers(self) -> None:
        """Test returns empty list when function has no callers."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", callers=[])
        result = CallGraphService.get_function_callers(graph, "main")
        assert result == []

    def test_get_callers_empty_when_function_missing(self) -> None:
        """Test returns empty list when function not in graph."""
        graph = CallGraph(binary_id=1)
        result = CallGraphService.get_function_callers(graph, "nonexistent")
        assert result == []

    def test_get_callers_deduplicates(self) -> None:
        """Test deduplicates callers."""
        graph = CallGraph(binary_id=1)
        graph.nodes["helper"] = CallGraphNode(name="helper", callers=["main", "main", "init"])
        result = CallGraphService.get_function_callers(graph, "helper")
        assert result == ["init", "main"]


# ---------------------------------------------------------------------------
# CallGraphService.get_function_callees tests
# ---------------------------------------------------------------------------


class TestGetFunctionCallees:
    """Tests for CallGraphService.get_function_callees."""

    def test_get_callees_returns_sorted_list(self) -> None:
        """Test returns sorted list of callees."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", callees=["z_func", "a_func", "m_func"])
        result = CallGraphService.get_function_callees(graph, "main")
        assert result == ["a_func", "m_func", "z_func"]

    def test_get_callees_empty_when_no_callees(self) -> None:
        """Test returns empty list when function has no callees."""
        graph = CallGraph(binary_id=1)
        graph.nodes["leaf"] = CallGraphNode(name="leaf", callees=[])
        result = CallGraphService.get_function_callees(graph, "leaf")
        assert result == []

    def test_get_callees_empty_when_function_missing(self) -> None:
        """Test returns empty list when function not in graph."""
        graph = CallGraph(binary_id=1)
        result = CallGraphService.get_function_callees(graph, "nonexistent")
        assert result == []

    def test_get_callees_deduplicates(self) -> None:
        """Test deduplicates callees."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", callees=["helper", "helper", "init"])
        result = CallGraphService.get_function_callees(graph, "main")
        assert result == ["helper", "init"]


# ---------------------------------------------------------------------------
# CallGraphService.find_entry_points tests
# ---------------------------------------------------------------------------


class TestFindEntryPoints:
    """Tests for CallGraphService.find_entry_points."""

    def test_find_entry_points_returns_sorted(self) -> None:
        """Test returns sorted list of entry points."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", callers=[])
        graph.nodes["start"] = CallGraphNode(name="start", callers=[])
        graph.nodes["helper"] = CallGraphNode(name="helper", callers=["main"])

        result = CallGraphService.find_entry_points(graph)
        assert result == ["main", "start"]

    def test_find_entry_points_all_are_entry_points(self) -> None:
        """Test when all functions are entry points."""
        graph = CallGraph(binary_id=1)
        graph.nodes["a"] = CallGraphNode(name="a", callers=[])
        graph.nodes["b"] = CallGraphNode(name="b", callers=[])
        graph.nodes["c"] = CallGraphNode(name="c", callers=[])

        result = CallGraphService.find_entry_points(graph)
        assert result == ["a", "b", "c"]

    def test_find_entry_points_no_entry_points(self) -> None:
        """Test when all functions have callers (circular graph)."""
        graph = CallGraph(binary_id=1)
        graph.nodes["a"] = CallGraphNode(name="a", callers=["b"])
        graph.nodes["b"] = CallGraphNode(name="b", callers=["a"])

        result = CallGraphService.find_entry_points(graph)
        assert result == []

    def test_find_entry_points_empty_graph(self) -> None:
        """Test returns empty list for empty graph."""
        graph = CallGraph(binary_id=1)
        result = CallGraphService.find_entry_points(graph)
        assert result == []

    def test_find_entry_points_single_function(self) -> None:
        """Test single function with no callers is entry point."""
        graph = CallGraph(binary_id=1)
        graph.nodes["main"] = CallGraphNode(name="main", callers=[])

        result = CallGraphService.find_entry_points(graph)
        assert result == ["main"]
