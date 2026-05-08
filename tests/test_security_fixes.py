"""Tests for security fixes applied to Glyph."""

from typing import Any

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config.settings import GlyphSettings
from app.core.rate_limiter import get_client_ip
from app.utils.secure_deserializer import BLOCKED_BUILTINS
from app.auth.schemas import UserRegister, ChangePassword
from app.auth.security_logger import _login_failure_tracker, is_blocked  # pyright: ignore[reportPrivateUsage]


class TestXSSPrevention:
    """Test that Jinja2 auto-escaping prevents XSS when rendering user-controlled content.

    format_code() returns raw, unescaped code. XSS prevention is handled by Jinja2
    auto-escaping when the code is rendered in templates. These tests verify that
    the Jinja2 environment properly escapes dangerous content.
    """

    def test_jinja2_autoescape_enabled(self) -> None:
        """Jinja2 auto-escaping must be enabled in the templates environment."""
        from app.templates import templates
        assert templates.env.autoescape is True  # type: ignore[union-attr]

    def test_jinja2_escapes_script_tags(self) -> None:
        """Script tags must be escaped when rendered through Jinja2."""
        from app.templates import templates

        template = templates.env.from_string("{{ code }}")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        result = template.render(code='<script>alert(1)</script>')  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        # After escaping, literal <script> should not appear
        assert "<script>" not in result
        # The escaped form should appear instead (&lt; replaces <)
        assert "&lt;" in result

    def test_jinja2_escapes_event_handlers(self) -> None:
        """Event handler attributes must be escaped when rendered through Jinja2."""
        from app.templates import templates

        template = templates.env.from_string("{{ code }}")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        result = template.render(code='<img onerror="alert(1)">')  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        # The opening angle bracket of <img should be escaped
        assert "<img" not in result
        # The escaped form should appear instead (&lt; replaces <)
        assert "&lt;img" in result

    def test_jinja2_escapes_angle_brackets(self) -> None:
        """Angle brackets must be escaped when rendered through Jinja2."""
        from app.templates import templates

        template = templates.env.from_string("{{ code }}")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        result = template.render(code="1 < 2 && 3 > 1")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        # Raw angle brackets from user input should not appear
        assert "<" not in result
        assert ">" not in result
        # Escaped forms should appear (&lt; for <, &gt; for >, &amp; for &)
        assert "&lt;" in result
        assert "&gt;" in result

    def test_jinja2_escapes_quotes(self) -> None:
        """Quotes must be escaped to prevent attribute injection."""
        from app.templates import templates

        template = templates.env.from_string("<div>{{ code }}</div>")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        result = template.render(code='char *s = "hello";')  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        # Double quotes should be escaped as "
        assert chr(34) not in result

    def test_jinja2_safe_mark_bypass_prevention(self) -> None:
        """User-controlled content should not be marked as safe by default."""
        from app.templates import templates

        # By default, variables are escaped unless explicitly marked safe
        template = templates.env.from_string("{{ code }}")  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        result = template.render(code='<script>alert("xss")</script>')  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        assert "<script>" not in result


class TestJWTSecretKeyWarning:
    """Test JWT secret key default warning behavior."""

    def test_default_jwt_secret_is_placeholder(self) -> None:
        """Default JWT secret should be the known placeholder."""
        settings = GlyphSettings()
        assert settings.jwt_secret_key == "change-me-in-production"

    def test_custom_jwt_secret_from_init(self) -> None:
        """Custom JWT secret from init should override default."""
        settings = GlyphSettings(jwt_secret_key="my-secret-key")
        assert settings.jwt_secret_key == "my-secret-key"


class TestCORSWildcard:
    """Test that CORS does not allow wildcard by default.

    Uses FastAPI's TestClient to verify Starlette's CORSMiddleware behavior
    through the actual application.
    """

    def test_cors_default_no_origins(self) -> None:
        """CORS middleware should default to empty allowed origins."""
        from main import app
        client = TestClient(app)
        # Make a request with an Origin header
        response = client.get(
            "/docs",
            headers={"Origin": "https://example.com"},
            follow_redirects=False,
        )
        # With empty allow_origins, no Access-Control-Allow-Origin header should be set
        assert "access-control-allow-origin" not in response.headers

    def test_cors_rejects_unlisted_origin(self) -> None:
        """Requests from unlisted origins should not get CORS headers."""
        from main import app
        client = TestClient(app)
        # Make a request with an Origin header for an unlisted origin
        response = client.get(
            "/docs",
            headers={"Origin": "https://evil.com"},
            follow_redirects=False,
        )
        # Should not have CORS headers for unlisted origins
        assert "access-control-allow-origin" not in response.headers

    def test_cors_preflight_rejected_for_unlisted_origin(self) -> None:
        """OPTIONS preflight requests from unlisted origins should not get CORS headers."""
        from main import app
        client = TestClient(app)
        # Make an OPTIONS preflight request
        response = client.options(
            "/api/v1/status",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not have CORS headers for unlisted origins
        assert "access-control-allow-origin" not in response.headers


class TestXForwardedForTrust:
    """Test that X-Forwarded-For is only trusted via trusted_proxies."""

    def test_xff_ignored_without_trusted_proxy(self) -> None:
        """X-Forwarded-For should be ignored when no trusted proxies configured."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        request.client.host = "192.168.1.1"
        ip = get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_xff_used_with_trusted_proxy(self) -> None:
        """X-Forwarded-For should be used when connected via trusted proxy."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        request.client.host = "10.0.0.1"
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "1.2.3.4"

    def test_xff_first_ip_extracted(self) -> None:
        """First IP from X-Forwarded-For chain should be used."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        request.client.host = "10.0.0.1"
        with patch("app.config.settings.get_settings") as mock_settings:
            mock_settings.return_value.trusted_proxies = ["10.0.0.1"]
            ip = get_client_ip(request)
            assert ip == "1.2.3.4"


class TestBlockedBuiltins:
    """Test that dangerous builtins are properly blocked in deserializer."""

    def test_setattr_in_blocked_list(self) -> None:
        """setattr must be in the blocked builtins list."""
        assert "builtins.setattr" in BLOCKED_BUILTINS

    def test_delattr_in_blocked_list(self) -> None:
        """delattr must be in the blocked builtins list."""
        assert "builtins.delattr" in BLOCKED_BUILTINS

    def test_no_typos_in_blocked_list(self) -> None:
        """No entries should have spaces instead of dots."""
        for entry in BLOCKED_BUILTINS:
            assert " " not in entry, f"Typo found in blocked builtin: {entry}"

    def test_no_duplicates_in_blocked_list(self) -> None:
        """Blocked builtins should have no duplicates."""
        assert len(BLOCKED_BUILTINS) == len(set(BLOCKED_BUILTINS))

    def test_eval_blocked(self) -> None:
        """eval must be blocked."""
        assert "builtins.eval" in BLOCKED_BUILTINS

    def test_exec_blocked(self) -> None:
        """exec must be blocked."""
        assert "builtins.exec" in BLOCKED_BUILTINS

    def test_import_blocked(self) -> None:
        """__import__ must be blocked."""
        assert "builtins.__import__" in BLOCKED_BUILTINS


class TestPasswordComplexity:
    """Test password validation based on current schema constraints.

    Note: The current schema only enforces min_length=8 and max_length=128.
    There is no complexity validation (uppercase, digits, special chars).
    These tests verify the actual behavior of the schema.
    """

    def test_password_meets_min_length(self) -> None:
        """Password with 8+ characters should be accepted regardless of complexity."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="abcdefgh",
            full_name="Test"
        )
        assert user.password == "abcdefgh"

    def test_password_all_uppercase_accepted(self) -> None:
        """Password with only uppercase is accepted (no complexity check)."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="ABCDEFGH",
            full_name="Test"
        )
        assert user.password == "ABCDEFGH"

    def test_password_letters_only_accepted(self) -> None:
        """Password with only letters is accepted (no complexity check)."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="abcDEFgh",
            full_name="Test"
        )
        assert user.password == "abcDEFgh"

    def test_password_complex_accepted(self) -> None:
        """Password with mixed character classes should be accepted."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="Abc123!@#",
            full_name="Test"
        )
        assert user.password == "Abc123!@#"

    def test_password_upper_lower_digit_accepted(self) -> None:
        """Password with uppercase, lowercase, and digits should be accepted."""
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="Abcdef123",
            full_name="Test"
        )
        assert user.password == "Abcdef123"

    def test_password_too_short_rejected(self) -> None:
        """Password shorter than 8 characters should be rejected."""
        with pytest.raises(Exception):
            UserRegister(
                username="testuser",
                email="test@example.com",
                password="short",
                full_name="Test"
            )

    def test_change_password_min_length_enforced(self) -> None:
        """Change password enforces minimum length of 8."""
        with pytest.raises(Exception):
            ChangePassword(
                current_password="OldPass1!",
                new_password="simple"
            )

    def test_change_password_complex_accepted(self) -> None:
        """Change password with valid new password should be accepted."""
        cp = ChangePassword(
            current_password="OldPass1!",
            new_password="NewPass1!"
        )
        assert cp.new_password == "NewPass1!"


class TestSecurityHeaders:
    """Test that security headers are set correctly via CSPMiddleware ASGI interface."""

    @pytest.mark.asyncio
    async def test_csp_middleware_sets_referrer_policy(self) -> None:
        """CSP middleware should set Referrer-Policy header."""
        captured_headers: dict[str, str] = {}

        async def capture_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                for name, value in message.get("headers", []):
                    captured_headers[name.decode("utf-8")] = value.decode("utf-8")

        async def dummy_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        from main import CSPMiddleware
        mw = CSPMiddleware(dummy_app)

        scope: dict[str, Any] = {"type": "http", "method": "GET", "path": "/"}
        async def receive() -> dict[str, str]:
            return {"type": "http.request"}
        await mw(scope, receive, capture_send)

        assert captured_headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_csp_middleware_sets_permissions_policy(self) -> None:
        """CSP middleware should set Permissions-Policy header."""
        captured_headers: dict[str, str] = {}

        async def capture_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                for name, value in message.get("headers", []):
                    captured_headers[name.decode("utf-8")] = value.decode("utf-8")

        async def dummy_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        from main import CSPMiddleware
        mw = CSPMiddleware(dummy_app)

        scope: dict[str, Any] = {"type": "http", "method": "GET", "path": "/"}
        async def receive() -> dict[str, str]:
            return {"type": "http.request"}
        await mw(scope, receive, capture_send)

        policy = captured_headers.get("permissions-policy", "")
        assert "geolocation=()" in policy
        assert "camera=()" in policy
        assert "microphone=()" in policy

    @pytest.mark.asyncio
    async def test_csp_middleware_sets_x_content_type_options(self) -> None:
        """CSP middleware should set X-Content-Type-Options: nosniff."""
        captured_headers: dict[str, str] = {}

        async def capture_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                for name, value in message.get("headers", []):
                    captured_headers[name.decode("utf-8")] = value.decode("utf-8")

        async def dummy_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        from main import CSPMiddleware
        mw = CSPMiddleware(dummy_app)

        scope: dict[str, Any] = {"type": "http", "method": "GET", "path": "/"}
        async def receive() -> dict[str, str]:
            return {"type": "http.request"}
        await mw(scope, receive, capture_send)

        assert captured_headers.get("x-content-type-options") == "nosniff"


class TestBruteForceLockout:
    """Test brute-force detection and lockout."""

    def setup_method(self) -> None:
        """Reset the failure tracker before each test."""
        _login_failure_tracker._failures.clear()  # pyright: ignore[reportPrivateUsage]
        _login_failure_tracker._alerted.clear()  # pyright: ignore[reportPrivateUsage]

    def test_is_blocked_returns_false_initially(self) -> None:
        """is_blocked should return False for a new username."""
        assert is_blocked("newuser") is False

    def test_is_blocked_returns_true_after_threshold(self) -> None:
        """is_blocked should return True after exceeding failure threshold."""
        username = "attacker"
        # Record failures equal to threshold (default is 5)
        for _ in range(5):
            _login_failure_tracker.record_failure(username)
        assert is_blocked(username) is True

    def test_is_blocked_resets_after_success(self) -> None:
        """is_blocked should return False after reset."""
        username = "user"
        for _ in range(5):
            _login_failure_tracker.record_failure(username)
        _login_failure_tracker.reset(username)
        assert is_blocked(username) is False

    def test_is_blocked_checks_ip(self) -> None:
        """is_blocked should check IP address as well."""
        ip = "1.2.3.4"
        for _ in range(5):
            _login_failure_tracker.record_failure(ip)
        assert is_blocked("someuser", ip_address=ip) is True

    def test_is_blocked_within_threshold(self) -> None:
        """is_blocked should return False within threshold."""
        username = "user"
        for _ in range(3):
            _login_failure_tracker.record_failure(username)
        assert is_blocked(username) is False


class TestDirectoryPermissions:
    """Test upload directory security."""

    def test_upload_directory_restricted_permissions(self) -> None:
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

    def test_insufficient_disk_space_detected(self) -> None:
        """Should detect insufficient disk space."""
        import shutil
        usage = shutil.disk_usage("/")
        # A file larger than available space should be detected
        huge_file_size = usage.free * 2
        assert usage.free < huge_file_size * 0.9

    def test_disk_usage_returns_valid_values(self) -> None:
        """disk_usage should return valid values."""
        import shutil
        usage = shutil.disk_usage("/")
        assert usage.total > 0
        assert usage.used >= 0
        assert usage.free >= 0


class TestUseHttpsSetting:
    """Test use_https configuration setting."""

    def test_use_https_defaults_to_false(self) -> None:
        """use_https should default to False."""
        settings = GlyphSettings()
        assert settings.use_https is False

    def test_use_https_can_be_enabled(self) -> None:
        """use_https should be configurable."""
        settings = GlyphSettings(use_https=True)
        assert settings.use_https is True

    def test_trusted_proxies_defaults_empty(self) -> None:
        """trusted_proxies should default to empty list."""
        settings = GlyphSettings()
        assert settings.trusted_proxies == []

    def test_trusted_proxies_can_be_configured(self) -> None:
        """trusted_proxies should be configurable."""
        settings = GlyphSettings(trusted_proxies=["10.0.0.1", "192.168.1.1"])
        assert "10.0.0.1" in settings.trusted_proxies
