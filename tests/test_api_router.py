"""Tests for the API router module.

Verifies router configuration including prefix, tags, route registration,
and sub-router inclusion for the main api_router and api_v1_router.
"""

import pytest
from app.api.router import api_router, api_v1_router
from fastapi import APIRouter


class TestAPIRouter:
    """Tests for API router configuration."""

    def test_api_router_is_api_router_instance(self) -> None:
        """api_router must be a FastAPI APIRouter instance."""
        assert isinstance(api_router, APIRouter)

    def test_api_v1_router_is_api_router_instance(self) -> None:
        """api_v1_router must be a FastAPI APIRouter instance."""
        assert isinstance(api_v1_router, APIRouter)

    def test_api_v1_router_has_correct_prefix(self) -> None:
        """api_v1_router should use the /v1 prefix for versioned endpoints."""
        assert api_v1_router.prefix == "/v1"

    def test_api_v1_router_has_correct_tags(self) -> None:
        """api_v1_router should be tagged 'api-v1' for OpenAPI grouping."""
        assert "api-v1" in api_v1_router.tags

    def test_api_v1_router_includes_expected_sub_routers(self) -> None:
        """api_v1_router should include routes tagged with all expected sub-router names.

        In modern FastAPI, included routers are wrapped in _IncludedRouter objects
        that store tags in include_context.tags rather than on individual route objects.
        """
        expected_tags = {"binaries", "predictions", "models", "status", "config", "dangerous-functions", "tasks"}
        actual_tags: set[str] = set()
        for route in api_v1_router.routes:
            # Tags for included routers are stored in include_context.tags
            ctx = getattr(route, "include_context", None)
            if ctx:
                tags = getattr(ctx, "tags", [])
                if tags:
                    actual_tags.update(tags)
            elif hasattr(route, "tags") and route.tags:
                actual_tags.update(route.tags)
        missing = expected_tags - actual_tags
        assert not missing, f"Missing sub-router tags: {missing}"

    def test_api_v1_router_has_registered_routes(self) -> None:
        """api_v1_router should have actual endpoint routes registered."""
        # Included routers appear as _IncludedRouter objects without a "path" attribute.
        # Count them along with any direct routes.
        routes = [route for route in api_v1_router.routes if hasattr(route, "path") or hasattr(route, "original_router")]
        assert len(routes) > 0, "api_v1_router should have at least one route"

    def test_api_router_includes_v1_routes(self) -> None:
        """api_router should include routes from the v1 sub-router.

        In modern FastAPI, included routers appear as _IncludedRouter objects
        that store the prefix in include_context.prefix rather than on individual routes.
        """
        def _collect_prefixes(router) -> set[str]:
            prefixes: set[str] = set()
            for route in router.routes:
                ctx = getattr(route, "include_context", None)
                if ctx:
                    prefix = getattr(ctx, "prefix", "")
                    if prefix:
                        prefixes.add(prefix)
                    # Recurse into nested routers
                    original = getattr(route, "original_router", None)
                    if original:
                        prefixes.update(_collect_prefixes(original))
                elif hasattr(route, "path"):
                    prefixes.add(route.path)
            return prefixes

        prefixes = _collect_prefixes(api_router)
        v1_prefixes = {p for p in prefixes if "/v1" in p}
        assert len(v1_prefixes) > 0, f"api_router should include routes with /v1 prefix, got: {prefixes}"

    def test_api_router_exports(self) -> None:
        """The router module should export api_router and api_v1_router via __all__."""
        from app.api import router

        assert hasattr(router, "__all__")
        assert "api_router" in router.__all__
        assert "api_v1_router" in router.__all__

    def test_v1_routes_have_http_methods(self) -> None:
        """All v1 routes should have at least one HTTP method defined."""
        routes = [route for route in api_v1_router.routes if hasattr(route, "methods")]
        for route in routes:
            assert len(route.methods) > 0, f"Route {route.path} has no HTTP methods"


class TestExpectedRoutes:
    """Verify that key endpoint paths are registered on the v1 router."""

    @pytest.fixture
    def route_paths(self) -> set[str]:
        """Collect all registered route paths from api_v1_router.

        In modern FastAPI, included routers are wrapped in _IncludedRouter objects.
        We need to recurse into the original_router to find actual endpoint paths.
        """
        paths: set[str] = set()

        def _collect_paths(router, prefix: str = "") -> None:
            for route in router.routes:
                ctx = getattr(route, "include_context", None)
                if ctx:
                    route_prefix = getattr(ctx, "prefix", "")
                    original = getattr(route, "original_router", None)
                    if original:
                        _collect_paths(original, route_prefix)
                elif hasattr(route, "path"):
                    full_path = prefix + route.path
                    paths.add(full_path)

        _collect_paths(api_v1_router, "/v1")
        return paths

    def test_binaries_routes_registered(self, route_paths: set[str]) -> None:
        """At least one /binaries route should be present."""
        binary_routes = {p for p in route_paths if "/binaries" in p}
        assert len(binary_routes) > 0, f"No /binaries routes found, got: {route_paths}"

    def test_models_routes_registered(self, route_paths: set[str]) -> None:
        """At least one /models route should be present."""
        model_routes = {p for p in route_paths if "/models" in p}
        assert len(model_routes) > 0, f"No /models routes found, got: {route_paths}"

    def test_predictions_routes_registered(self, route_paths: set[str]) -> None:
        """At least one /predictions route should be present."""
        prediction_routes = {p for p in route_paths if "/predictions" in p}
        assert len(prediction_routes) > 0, f"No /predictions routes found, got: {route_paths}"

    def test_tasks_routes_registered(self, route_paths: set[str]) -> None:
        """At least one /tasks route should be present."""
        task_routes = {p for p in route_paths if "/tasks" in p}
        assert len(task_routes) > 0, f"No /tasks routes found, got: {route_paths}"
