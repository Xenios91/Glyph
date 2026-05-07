"""Tests for rate limiting utilities."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.rate_limiter import RateLimiter, check_rate_limit, get_client_ip


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_defaults(self):
        """Test default initialization values."""
        limiter = RateLimiter()
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
        assert limiter._requests == {}

    def test_init_custom_values(self):
        """Test custom initialization values."""
        limiter = RateLimiter(max_requests=5, window_seconds=120)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 120

    def test_is_rate_limited_first_request(self):
        """Test that the first request is not rate limited."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.is_rate_limited("192.168.1.1") is False

    def test_is_rate_limited_under_threshold(self):
        """Test requests under threshold are not rate limited."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(4):
            assert limiter.is_rate_limited("192.168.1.1") is False

    def test_is_rate_limited_at_threshold(self):
        """Test that requests at threshold are rate limited."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        # First 3 requests should pass
        for _ in range(3):
            assert limiter.is_rate_limited("192.168.1.1") is False
        # 4th request should be rate limited
        assert limiter.is_rate_limited("192.168.1.1") is True

    def test_is_rate_limited_different_ips(self):
        """Test that different IPs have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        # IP 1: 2 requests (at limit)
        for _ in range(2):
            limiter.is_rate_limited("192.168.1.1")
        assert limiter.is_rate_limited("192.168.1.1") is True
        # IP 2: should still be allowed
        assert limiter.is_rate_limited("192.168.1.2") is False

    def test_is_rate_limited_window_expiry(self):
        """Test that old requests expire from the window."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        # Fill up the limit
        limiter.is_rate_limited("192.168.1.1")
        limiter.is_rate_limited("192.168.1.1")
        assert limiter.is_rate_limited("192.168.1.1") is True

        # Simulate time passing by backdating requests
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        limiter._requests["192.168.1.1"] = [old_time]
        # Should no longer be rate limited after window expires
        assert limiter.is_rate_limited("192.168.1.1") is False

    def test_cleanup_removes_expired_keys(self):
        """Test that cleanup removes expired entries."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.is_rate_limited("192.168.1.1")
        limiter.is_rate_limited("192.168.1.2")
        assert len(limiter._requests) == 2

        # Backdate all requests
        old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        limiter._requests["192.168.1.1"] = [old_time]
        limiter._requests["192.168.1.2"] = [old_time]

        limiter.cleanup()
        assert len(limiter._requests) == 0

    def test_cleanup_keeps_recent_keys(self):
        """Test that cleanup keeps recent entries."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.is_rate_limited("192.168.1.1")
        limiter.is_rate_limited("192.168.1.2")
        assert len(limiter._requests) == 2

        limiter.cleanup()
        # Recent requests should remain
        assert len(limiter._requests) == 2

    def test_cleanup_removes_empty_keys(self):
        """Test that cleanup removes keys with empty request lists."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter._requests["192.168.1.1"] = []
        limiter._requests["192.168.1.2"] = [datetime.now(timezone.utc)]

        limiter.cleanup()
        assert "192.168.1.1" not in limiter._requests
        assert "192.168.1.2" in limiter._requests


class TestGetClientIP:
    """Tests for get_client_ip function."""

    def _make_request(self, host, xff=None):
        """Helper to create a mock request."""
        request = MagicMock()
        request.client.host = host
        headers = {}
        if xff:
            headers["X-Forwarded-For"] = xff
        request.headers = headers
        return request

    def test_get_client_ip_no_proxy(self):
        """Test IP extraction without proxy headers."""
        request = self._make_request("192.168.1.1")
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            ip = get_client_ip(request)
            assert ip == "192.168.1.1"

    def test_get_client_ip_with_trusted_proxy(self):
        """Test IP extraction with trusted proxy."""
        request = self._make_request("10.0.0.1", xff="203.0.113.50")
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "203.0.113.50"

    def test_get_client_ip_ignores_xff_without_trusted_proxy(self):
        """Test that X-Forwarded-For is ignored without trusted proxy."""
        request = self._make_request("192.168.1.1", xff="203.0.113.50")
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            ip = get_client_ip(request)
            assert ip == "192.168.1.1"

    def test_get_client_ip_xff_first_ip(self):
        """Test that first IP from X-Forwarded-For chain is used."""
        request = self._make_request("10.0.0.1", xff="203.0.113.50, 70.41.3.18, 150.172.238.178")
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "203.0.113.50"

    def test_get_client_ip_no_client(self):
        """Test handling when request has no client."""
        request = MagicMock()
        request.client = None
        request.headers = {}
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            ip = get_client_ip(request)
            assert ip == "unknown"


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    def test_check_rate_limit_allowed(self):
        """Test that allowed requests don't raise."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = {}
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            # Should not raise
            check_rate_limit(limiter, request)

    def test_check_rate_limit_exceeded(self):
        """Test that exceeded rate limit raises HTTPException."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = {}
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = []
            # Fill up the limit
            check_rate_limit(limiter, request)
            check_rate_limit(limiter, request)
            # Third request should raise
            with pytest.raises(HTTPException) as exc_info:
                check_rate_limit(limiter, request)
            assert exc_info.value.status_code == 429
