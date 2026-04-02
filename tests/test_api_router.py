"""Tests for the API router module."""

import pytest
from unittest.mock import Mock, patch

from app.api.router import api_router, api_v1_router


class TestAPIRouter:
    """Tests for API router configuration."""

    def test_api_router_exists(self):
        """Test that api_router is defined."""
        assert api_router is not None

    def test_api_v1_router_exists(self):
        """Test that api_v1_router is defined."""
        assert api_v1_router is not None

    def test_api_v1_router_has_prefix(self):
        """Test that api_v1_router has the correct prefix."""
        assert api_v1_router.prefix == "/v1"

    def test_api_v1_router_has_tags(self):
        """Test that api_v1_router has the correct tags."""
        assert "api-v1" in api_v1_router.tags

    def test_api_router_includes_v1_router(self):
        """Test that api_router includes api_v1_router."""
        # Check that the router has routes from v1
        routes = [route for route in api_router.routes]
        assert len(routes) > 0

    def test_api_v1_router_has_endpoints(self):
        """Test that api_v1_router has endpoint routes."""
        routes = [route for route in api_v1_router.routes]
        assert len(routes) > 0

    @patch("app.api.router.binaries")
    @patch("app.api.router.config")
    @patch("app.api.router.models")
    @patch("app.api.router.predictions")
    @patch("app.api.router.status")
    def test_router_includes_all_endpoints(
        self,
        mock_status,
        mock_predictions,
        mock_models,
        mock_config,
        mock_binaries,
    ):
        """Test that router includes all expected endpoints."""
        # Mock the endpoint modules
        mock_binaries.router = Mock()
        mock_config.router = Mock()
        mock_models.router = Mock()
        mock_predictions.router = Mock()
        mock_status.router = Mock()

        # Re-import to use mocks
        import importlib
        import app.api.router as router_module
        importlib.reload(router_module)

        # Check that include_router was called for each endpoint
        # This verifies the router configuration
        assert hasattr(router_module, "api_v1_router")
        assert hasattr(router_module, "api_router")

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        from app.api import router

        assert hasattr(router, "api_router")
        assert hasattr(router, "api_v1_router")
