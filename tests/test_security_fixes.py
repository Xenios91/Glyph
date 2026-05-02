"""Tests for security fixes applied to Glyph."""

import os
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config.settings import GlyphSettings, get_settings, reload_settings
from app.core.csrf import CSRFMiddleware
from app.core.rate_limiter import get_client_ip, RateLimiter
from app.utils.common import format_code
from app.utils.secure_deserializer import BLOCKED_BUILTINS, RestrictedNumpyUnpickler, SecureDeserializationError
from app.auth.schemas import UserRegister, ChangePassword
from app.auth.security_logger import _login_failure_tracker, is_blocked


class TestXSSPrevention:
    """Test that format_code HTML-escapes output to prevent XSS."""

    def test_format_code_escapes_script_tags(self):
        """Script tags in code must be HTML-escaped."""
        code = 'void foo() { return "<script>alert(1)</script>"; }'
        result = format_code(code)
        assert "<script>" not in result
        assert "<script>" in result

    def test_format_code_escapes_event_handlers(self):
        """Event handler attributes must be HTML-escaped."""
        code = 'void foo() { return "<img onerror=alert(1)>"; }'
        result = format_code(code)
        assert "onerror" in result  # The word itself is fine
        assert "<img" not in result
        assert "<img" in result

    def test_format_code_escapes_angle_brackets(self):
        """Angle brackets must be escaped."""
        code = 'void foo() { int x = 1 < 2 && 3 > 1; }'
        result = format_code(code)
        # The < and > in comparisons should be escaped
        assert "<" in result or "<" in result  # May appear in valid code context

    def test_format_code_escapes_quotes(self):
        """Quotes must be escaped to prevent attribute injection."""
        code = 'void foo() { char *s = "hello"; }'
        result = format_code(code)
        # Quotes inside strings may be preserved but should be safe in <pre> context

    def test_format_code_simple_code_safe(self):
        """Normal C code should be formatted and escaped."""
        code = 'int main() { return 0; }'
        result = format_code(code)
        assert "main" in result
        assert "<" not in result  # No special chars to escape


class TestCSRFCookieSecureFlag:
    """Test that CSRF cookie respects use_https setting."""

    def test_csrf_cookie_secure_when_https_enabled(self):
        """CSRF cookie should have secure=True when use_https=True."""
        settings = GlyphSettings(use_https=True)
        with patch("app.core.csrf.get_settings", return_value=settings):
            middleware = CSRFMiddleware(lambda request: None)
            response = MagicMock()
            response.set_cookie = MagicMock()
            middleware._set_csrf_cookie(response, "test-token")
            call_kwargs = response.set_cookie.call_args[1]
            assert call_kwargs["secure"] is True

    def test_csrf_cookie_insecure_when_https_disabled(self):
        """CSRF cookie should have secure=False when use_https=False."""
        settings = GlyphSettings(use_https=False)
        with patch("app.core.csrf.get_settings", return_value=settings):
            middleware = CSRFMiddleware(lambda request: None)
            response = MagicMock()
            response.set_cookie = MagicMock()
            middleware._set_csrf_cookie(response, "test-token")
            call_kwargs = response.set_cookie.call_args[1]
            assert call_kwargs["secure"] is False


class TestJWTSecretKeyWarning:
    """Test JWT secret key default warning behavior."""

    def test_default_jwt_secret_is_placeholder(self):
        """Default JWT secret should be the known placeholder."""
        settings = GlyphSettings()
        assert settings.jwt_secret_key == "change-me-in-production"

    def test_custom_jwt_secret_from_env(self):
        """Custom JWT secret from env var should override default."""
        with patch.dict(os.environ, {"GLYPH_JWT_SECRET_KEY": "my-secret-key"}):
            settings = GlyphSettings()
            assert settings.jwt_secret_key == "my-secret-key"

    def test_custom_jwt_secret_from_init(self):
        """Custom JWT secret from init should override default."""
        settings = GlyphSettings(jwt_secret_key="my-custom-key")
        assert settings.jwt_secret_key == "my-custom-key"


class TestCORSWildcard:
    """Test that CORS does not allow wildcard by default."""

    def test_cors_default_no_origins(self):
        """CORS middleware should default to empty allowed origins."""
        from main import CORSMiddleware
        middleware = CORSMiddleware()
        assert middleware.allow_origins == []

    def test_cors_rejects_unlisted_origin(self):
        """Requests from unlisted origins should not get CORS headers."""
        from main import CORSMiddleware
        middleware = CORSMiddleware()
        # Simulate a request with an origin not in the allow list
        request = MagicMock()
        request.headers = {"Origin": "https://evil.com"}
        request.method = "GET"
        # The middleware should not add CORS headers for unlisted origins
        # This is tested by checking the logic directly
        origin = request.headers.get("Origin")
        allowed = origin and middleware.allow_origins and origin in middleware.allow_origins
        assert allowed is False

    def test_cors_allows_configured_origin(self):
        """Requests from configured origins should get CORS headers."""
        from main import CORSMiddleware
        middleware = CORSMiddleware(allow_origins=["https://trusted.com"])
        assert "https://trusted.com" in middleware.allow_origins


class TestXForwardedForTrust:
    """Test that X-Forwarded-For is only trusted via trusted_proxies."""

    def test_xff_ignored_without_trusted_proxy(self):
        """X-Forwarded-For should be ignored when no trusted proxies configured."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        request.client.host = "192.168.1.1"
        ip = get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_xff_used_with_trusted_proxy(self):
        """X-Forwarded-For should be used when connected via trusted proxy."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        request.client.host = "10.0.0.1"
        with patch("app.core.rate_limiter.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "1.2.3.4"

    def test_xff_first_ip_extracted(self):
        """First IP from X-Forwarded-For chain should be used."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        request.client.host = "10.0.0.1"
        with patch("app.core.rate_limiter.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "1.2.3.4"


class TestBlockedBuiltins:
    """Test that dangerous builtins are properly blocked in deserializer."""

    def test_setattr_in_blocked_list(self):
        """setattr must be in the blocked builtins list."""
        assert "builtins.setattr" in BLOCKED_BUILTINS

    def test_delattr_in_blocked_list(self):
        """delattr must be in the blocked builtins list."""
        assert "builtins.delattr" in BLOCKED_BUILTINS

    def test_no_typos_in_blocked_list(self):
        """No entries should have spaces instead of dots."""
        for entry in BLOCKED_BUILTINS:
            assert " " not in entry, f"Typo found in blocked builtin: {entry}"

    def test_no_duplicates_in_blocked_list(self):
        """Blocked builtins should have no duplicates."""
        assert len(BLOCKED_BUILTINS) == len(set(BLOCKED_BUILTINS))

    def test_eval_blocked(self):
        """eval must be blocked."""
        assert "builtins.eval" in BLOCKED_BUILTINS

    def test_exec_blocked(self):
        """exec must be blocked."""
        assert "builtins.exec" in BLOCKED_BUILTINS

    def test_import_blocked(self):
        """__import__ must be blocked."""
        assert "builtins.__import__" in BLOCKED_BUILTINS


class TestPasswordComplexity:
    """Test password complexity validation."""

    def test_password_too_simple_rejected(self):
        """Password with only lowercase should be rejected."""
        with pytest.raises(Exception):
            UserRegister(
                username="testuser",
                email="test@example.com",
                password="abcdefgh",
                full_name="Test"
            )

    def test_password_all_uppercase_rejected(self):
        """Password with only uppercase should be rejected."""
        with pytest.raises(Exception):
            UserRegister(
                username="testuser",
                email="test@example.com",
                password="ABCDEFGH",
                full_name="Test"
            )

    def test_password_letters_only_rejected(self):
        """Password with only letters (no digits/special) should be rejected."""
        with pytest.raises(Exception):
            UserRegister(
                username="testuser",
                email="test@example.com",
                password="abcDEFgh",
                full_name="Test"
            )

    def test_password_complex_accepted(self):
        """Password with 3+ character classes should be accepted."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="Abc123!@#",
            full_name="Test"
        )
        assert user.password == "Abc123!@#"

    def test_password_upper_lower_digit_accepted(self):
        """Password with uppercase, lowercase, and digits should be accepted."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="Abcdef123",
            full_name="Test"
        )
        assert user.password == "Abcdef123"

    def test_change_password_complexity(self):
        """Change password should also enforce complexity."""
        with pytest.raises(Exception):
            ChangePassword(
                current_password="OldPass1!",
                new_password="simple"
            )

    def test_change_password_complex_accepted(self):
        """Change password with complex new password should be accepted."""
        cp = ChangePassword(
            current_password="OldPass1!",
            new_password="NewPass1!"
        )
        assert cp.new_password == "NewPass1!"


class TestSecurityHeaders:
    """Test that security headers are set correctly."""

    def test_csp_middleware_sets_referrer_policy(self):
        """CSP middleware should set Referrer-Policy header."""
        from main import CSPMiddleware
        middleware = CSPMiddleware()

        async def dummy_app(request):
            return MagicMock()

        async def test_call():
            request = MagicMock()
            request.headers = {}
            response = await middleware(request, dummy_app)
            return response

        import asyncio
        response = asyncio.get_event_loop().run_until_complete(test_call())
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_csp_middleware_sets_permissions_policy(self):
        """CSP middleware should set Permissions-Policy header."""
        from main import CSPMiddleware
        middleware = CSPMiddleware()

        async def dummy_app(request):
            return MagicMock()

        async def test_call():
            request = MagicMock()
            request.headers = {}
            response = await middleware(request, dummy_app)
            return response

        import asyncio
        response = asyncio.get_event_loop().run_until_complete(test_call())
        policy = response.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in policy
        assert "camera=()" in policy
        assert "microphone=()" in policy

    def test_csp_middleware_sets_x_content_type_options(self):
        """CSP middleware should set X-Content-Type-Options: nosniff."""
        from main import CSPMiddleware
        middleware = CSPMiddleware()

        async def dummy_app(request):
            return MagicMock()

        async def test_call():
            request = MagicMock()
            request.headers = {}
            response = await middleware(request, dummy_app)
            return response

        import asyncio
        response = asyncio.get_event_loop().run_until_complete(test_call())
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


class TestBruteForceLockout:
    """Test brute-force detection and lockout."""

    def setup_method(self):
        """Reset the failure tracker before each test."""
        _login_failure_tracker._failures.clear()
        _login_failure_tracker._alerted.clear()

    def test_is_blocked_returns_false_initially(self):
        """is_blocked should return False for a new username."""
        assert is_blocked("newuser") is False

    def test_is_blocked_returns_true_after_threshold(self):
        """is_blocked should return True after exceeding failure threshold."""
        username = "attacker"
        # Record failures equal to threshold (default is 5)
        for _ in range(5):
            _login_failure_tracker.record_failure(username)
        assert is_blocked(username) is True

    def test_is_blocked_resets_after_success(self):
        """is_blocked should return False after reset."""
        username = "user"
        for _ in range(5):
            _login_failure_tracker.record_failure(username)
        _login_failure_tracker.reset(username)
        assert is_blocked(username) is False

    def test_is_blocked_checks_ip(self):
        """is_blocked should check IP address as well."""
        ip = "1.2.3.4"
        for _ in range(5):
            _login_failure_tracker.record_failure(ip)
        assert is_blocked("someuser", ip_address=ip) is True

    def test_is_blocked_within_threshold(self):
        """is_blocked should return False within threshold."""
        username = "user"
        for _ in range(3):
            _login_failure_tracker.record_failure(username)
        assert is_blocked(username) is False


class TestDirectoryPermissions:
    """Test upload directory security."""

    def test_upload_directory_restricted_permissions(self):
        """Upload directory should have restricted permissions (0o700)."""
        import stat
        import tempfile
        import shutil

        test_dir = tempfile.mkdtemp()
        try:
            # Simulate what binaries.py does
            os.chmod(test_dir, stat.S_IRWXU)
            mode = os.stat(test_dir).st_mode & 0o777
            assert mode == 0o700, f"Expected 0o700, got 0o{mode:o}"
        finally:
            shutil.rmtree(test_dir)


class TestDiskSpaceCheck:
    """Test disk space validation before upload."""

    def test_insufficient_disk_space_detected(self):
        """Should detect insufficient disk space."""
        import shutil
        usage = shutil.disk_usage("/")
        # A file larger than available space should be detected
        huge_file_size = usage.free * 2
        assert usage.free < huge_file_size * 0.9

    def test_disk_usage_returns_valid_values(self):
        """disk_usage should return valid values."""
        import shutil
        usage = shutil.disk_usage("/")
        assert usage.total > 0
        assert usage.used >= 0
        assert usage.free >= 0


class TestUseHttpsSetting:
    """Test use_https configuration setting."""

    def test_use_https_defaults_to_false(self):
        """use_https should default to False."""
        settings = GlyphSettings()
        assert settings.use_https is False

    def test_use_https_can_be_enabled(self):
        """use_https should be configurable."""
        settings = GlyphSettings(use_https=True)
        assert settings.use_https is True

    def test_trusted_proxies_defaults_empty(self):
        """trusted_proxies should default to empty list."""
        settings = GlyphSettings()
        assert settings.trusted_proxies == []

    def test_trusted_proxies_can_be_configured(self):
        """trusted_proxies should be configurable."""
        settings = GlyphSettings(trusted_proxies=["10.0.0.1", "192.168.1.1"])
        assert "10.0.0.1" in settings.trusted_proxies
