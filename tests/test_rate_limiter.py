"""Tests for rate limiting (slowapi).

Tests verify that the slowapi-based rate limiter properly limits requests
and respects trusted proxy configuration.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.rate_limiter import (
    limiter,
    LOGIN_LIMIT,
    REGISTER_LIMIT,
    PASSWORD_CHANGE_LIMIT,
    REFRESH_LIMIT,
    rate_limit_key_func,
    _build_rate_limit,
)


class TestBuildRateLimit:
    """Tests for _build_rate_limit utility."""

    def test_default_minute(self) -> None:
        """Test building rate limit string for 60-second window."""
        result = _build_rate_limit(10, 60, "TEST")
        assert result == "10/minute"

    def test_default_5_minutes(self) -> None:
        """Test building rate limit string for 300-second window."""
        result = _build_rate_limit(5, 300, "TEST")
        assert result == "5/5 minutes"

    def test_default_hour(self) -> None:
        """Test building rate limit string for 3600-second window."""
        result = _build_rate_limit(20, 3600, "TEST")
        assert result == "20/hour"

    def test_custom_seconds(self) -> None:
        """Test building rate limit string for custom window."""
        result = _build_rate_limit(3, 120, "TEST")
        assert result == "3/120 seconds"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("GLYPH_RATE_LIMIT_TEST_MAX", "50")
        monkeypatch.setenv("GLYPH_RATE_LIMIT_TEST_WINDOW", "120")
        result = _build_rate_limit(10, 60, "TEST")
        assert result == "50/120 seconds"


class TestRateLimitKeyFunc:
    """Tests for rate_limit_key_func."""

    def test_direct_ip(self) -> None:
        """Test extracting direct IP from request."""
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = {}

        # Patch at the location where get_settings is imported
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            result = rate_limit_key_func(request)
            assert result == "192.168.1.1"

    def test_trusted_proxy_forwarded_for(self) -> None:
        """Test extracting IP from X-Forwarded-For when behind trusted proxy."""
        request = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18"}

        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            result = rate_limit_key_func(request)
            assert result == "203.0.113.50"

    def test_untrusted_proxy_ignores_forwarded_for(self) -> None:
        """Test that X-Forwarded-For is ignored when not from trusted proxy."""
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = {"X-Forwarded-For": "203.0.113.50"}

        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            result = rate_limit_key_func(request)
            assert result == "192.168.1.1"


class TestRateLimitConstants:
    """Tests for rate limit constant values."""

    def test_login_limit(self) -> None:
        """Test login rate limit is configured (respects environment overrides for tests)."""
        # In test environment, GLYPH_RATE_LIMIT_LOGIN_MAX=1000 overrides the default of 10.
        assert LOGIN_LIMIT == "1000/minute"

    def test_register_limit(self) -> None:
        """Test registration rate limit is configured (respects environment overrides for tests)."""
        # In test environment, GLYPH_RATE_LIMIT_REGISTER_MAX=1000 overrides the default of 5.
        assert REGISTER_LIMIT == "1000/minute"

    def test_password_change_limit(self) -> None:
        """Test password change rate limit is configured (respects environment overrides for tests)."""
        # In test environment, GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX=1000 overrides the default of 5.
        assert PASSWORD_CHANGE_LIMIT == "1000/minute"

    def test_refresh_limit(self) -> None:
        """Test token refresh rate limit is configured (respects environment overrides for tests)."""
        # In test environment, GLYPH_RATE_LIMIT_REFRESH_MAX=1000 overrides the default of 10.
        assert REFRESH_LIMIT == "1000/minute"


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with FastAPI."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a test FastAPI app with rate limiting."""
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded

        test_app = FastAPI()
        test_app.state.limiter = limiter
        test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        @test_app.get("/test")
        @limiter.limit("3/minute")
        async def test_endpoint(request: Request):  # pyright: ignore[reportUnusedFunction]
            return {"message": "ok"}

        return test_app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_allows_requests_under_limit(self, client: TestClient) -> None:
        """Test that requests under the limit are allowed."""
        for _ in range(3):
            response = client.get("/test")
            assert response.status_code == 200

    def test_blocks_requests_over_limit(self, client: TestClient) -> None:
        """Test that requests over the limit return 429."""
        # Use up the limit
        for _ in range(3):
            client.get("/test")

        # Next request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429
