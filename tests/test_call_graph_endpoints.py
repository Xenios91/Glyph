"""Endpoint tests for the call graph API (authz, 404s, success shape)."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import create_app_client
from tests.factories import make_user


class _FakeFunction:
    """Minimal stand-in for a BinaryFunction ORM row."""

    def __init__(self, function_name: str, entrypoint: str, raw_code: str) -> None:
        self.function_name = function_name
        self.entrypoint = entrypoint
        self.raw_code = raw_code


def _make_graph() -> Any:
    """Build a real CallGraph: main() calls helper() twice."""
    from app.services.call_graph_service import CallGraphService

    functions = [
        _FakeFunction("main", "0x401000", "undefined main(void) { helper(1); helper(2); return 0; }"),
        _FakeFunction("helper", "0x401100", "int helper(int x) { return x + 1; }"),
    ]
    return CallGraphService.build_graph_from_functions(binary_id=1, functions=functions)


def _client(user: Any) -> Any:
    from app.api.v1.endpoints import call_graph
    from app.auth.dependencies import get_current_active_user

    return create_app_client(
        routers=[(call_graph.router, "/call-graph")],
        dependency_overrides={get_current_active_user: lambda: user},
    )


def _owned_binary(owner_id: int) -> Any:
    binary = MagicMock()
    binary.uploaded_by = owner_id
    return binary


class TestGetCallGraph:
    """Tests for GET /call-graph/{binary_id}/graph."""

    @pytest.fixture
    def owner(self) -> Any:
        return make_user(user_id=1, username="owner")

    @pytest.fixture
    def intruder(self) -> Any:
        return make_user(user_id=99, username="intruder")

    def test_call_graph_binary_not_found(self, owner: Any) -> None:
        """Requesting a non-existent binary should return 404 BINARY_NOT_FOUND."""
        from app.database.binary_repository import BinaryRepository

        client = _client(owner)
        with patch.object(BinaryRepository, "get", new=AsyncMock(return_value=None)):
            response = client.get("/call-graph/1/graph")

        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "BINARY_NOT_FOUND"

    def test_call_graph_other_user_denied(self, owner: Any, intruder: Any) -> None:
        """Requesting another user's binary should return 403 ACCESS_DENIED."""
        from app.database.binary_repository import BinaryRepository

        client = _client(intruder)
        with patch.object(BinaryRepository, "get", new=AsyncMock(return_value=_owned_binary(owner.id))):
            response = client.get("/call-graph/1/graph")

        assert response.status_code == 403
        assert response.json()["detail"]["error"]["code"] == "ACCESS_DENIED"

    def test_call_graph_success_shape(self, owner: Any) -> None:
        """A successful call graph exposes nodes, edges, totals, and entry points."""
        from app.database.binary_repository import BinaryRepository
        from app.services.call_graph_service import CallGraphService

        client = _client(owner)
        graph = _make_graph()
        with (
            patch.object(BinaryRepository, "get", new=AsyncMock(return_value=_owned_binary(owner.id))),
            patch.object(CallGraphService, "generate_call_graph", new=AsyncMock(return_value=graph)),
        ):
            response = client.get("/call-graph/1/graph")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["binary_id"] == 1
        assert data["total_nodes"] == 2
        assert data["total_edges"] == 1
        assert data["entry_points"] == ["main"]
        assert data["edges"] == [{"caller": "main", "callee": "helper", "call_count": 2}]

        by_name = {node["name"]: node for node in data["nodes"]}
        assert by_name["main"]["entrypoint"] == "0x401000"
        assert by_name["main"]["callees"] == ["helper"]
        assert by_name["main"]["callers"] == []
        assert by_name["helper"]["callers"] == ["main"]
        assert by_name["helper"]["callees"] == []


class TestFunctionCallersCallees:
    """Tests for GET /call-graph/{binary_id}/callers|callees/{function_name}."""

    @pytest.fixture
    def owner(self) -> Any:
        return make_user(user_id=1, username="owner")

    def _patched_client(self, owner: Any, graph: Any) -> Any:
        from app.database.binary_repository import BinaryRepository
        from app.services.call_graph_service import CallGraphService

        client = _client(owner)
        patches = [
            patch.object(BinaryRepository, "get", new=AsyncMock(return_value=_owned_binary(owner.id))),
            patch.object(CallGraphService, "generate_call_graph", new=AsyncMock(return_value=graph)),
        ]
        for p in patches:
            p.start()
        client._graph_patches = patches  # type: ignore[attr-defined]
        return client

    @staticmethod
    def _stop_patches(client: Any) -> None:
        for p in client._graph_patches:  # type: ignore[attr-defined]
            p.stop()

    def test_callers_function_not_found(self, owner: Any) -> None:
        """Querying callers for an unknown function should return 404 FUNCTION_NOT_FOUND."""
        client = self._patched_client(owner, _make_graph())
        try:
            response = client.get("/call-graph/1/callers/ghost")
        finally:
            self._stop_patches(client)

        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "FUNCTION_NOT_FOUND"
        assert "ghost" in response.json()["detail"]["error"]["message"]

    def test_callees_function_not_found(self, owner: Any) -> None:
        """Querying callees for an unknown function should return 404 FUNCTION_NOT_FOUND."""
        client = self._patched_client(owner, _make_graph())
        try:
            response = client.get("/call-graph/1/callees/ghost")
        finally:
            self._stop_patches(client)

        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "FUNCTION_NOT_FOUND"

    def test_callers_success(self, owner: Any) -> None:
        """Callers of helper() should list main() with a matching count."""
        client = self._patched_client(owner, _make_graph())
        try:
            response = client.get("/call-graph/1/callers/helper")
        finally:
            self._stop_patches(client)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["function_name"] == "helper"
        assert data["callers"] == ["main"]
        assert data["caller_count"] == 1

    def test_callees_success(self, owner: Any) -> None:
        """Callees of main() should list helper() with a matching count."""
        client = self._patched_client(owner, _make_graph())
        try:
            response = client.get("/call-graph/1/callees/main")
        finally:
            self._stop_patches(client)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["function_name"] == "main"
        assert data["callees"] == ["helper"]
        assert data["callee_count"] == 1
