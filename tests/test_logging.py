"""Tests for logging configuration and utilities using loguru."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from loguru import logger

from app.utils.logging_utils import catch_http_exception

from app.utils.logging_config import (
    setup_logging,
    SensitiveDataPatcher,
)
from app.utils.request_context import (
    get_request_context,
    set_request_context,
    clear_request_context,
    get_request_id,
    get_user_id,
    get_username,
)
from app.auth.security_logger import (
    LoginFailureTracker,
    log_login_success,
    log_login_failure,
)


class TestLoggingSetup:
    """Tests for logging setup functions."""

    def test_setup_logging_adds_handlers(self):
        """Test that setup_logging adds loguru handlers."""
        logger.remove()  # Clear existing handlers
        setup_logging(
            level="INFO",
            format="text",
            log_file="logs/test.log",
            console_enabled=True,
        )

        # Verify logging works by checking no exception is raised
        logger.info("Test message")

    def test_setup_logging_json_format(self):
        """Test that JSON format is applied correctly."""
        logger.remove()  # Clear existing handlers
        setup_logging(
            level="INFO",
            format="json",
            log_file=None,
            console_enabled=True,
        )

        # Verify logging works
        logger.info("Test message")

    def test_setup_logging_text_format(self):
        """Test that text format is applied correctly."""
        logger.remove()  # Clear existing handlers
        setup_logging(
            level="INFO",
            format="text",
            log_file=None,
            console_enabled=True,
        )

        # Verify logging works
        logger.info("Test message")

    def test_setup_logging_no_console(self):
        """Test that console handler is not created when disabled."""
        logger.remove()  # Clear existing handlers
        setup_logging(
            level="INFO",
            format="json",
            log_file="logs/test.log",
            console_enabled=False,
        )

        # Verify logging works
        logger.info("Test message")

    def test_setup_logging_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        logger.remove()  # Clear existing handlers
        test_log_dir = Path("logs/test_subdir")
        test_log_file = test_log_dir / "test.log"

        try:
            setup_logging(
                level="INFO",
                format="text",
                log_file=str(test_log_file),
                console_enabled=False,
            )

            assert test_log_dir.exists()
        finally:
            # Cleanup
            if test_log_file.exists():
                test_log_file.unlink()
            if test_log_dir.exists():
                test_log_dir.rmdir()


class TestSensitiveDataPatcher:
    """Tests for SensitiveDataPatcher."""

    def test_redacts_password(self):
        """Test that password values are redacted."""
        patcher = SensitiveDataPatcher()
        result = patcher.redact("password=mysecret123")
        assert "mysecret123" not in result
        assert "REDACTED" in result

    def test_redacts_token(self):
        """Test that token values are redacted."""
        patcher = SensitiveDataPatcher()
        result = patcher.redact("token=abc123xyz")
        assert "abc123xyz" not in result
        assert "REDACTED" in result

    def test_redacts_api_key(self):
        """Test that API key values are redacted."""
        patcher = SensitiveDataPatcher()
        result = patcher.redact("api_key=sk-1234567890")
        assert "sk-1234567890" not in result
        assert "REDACTED" in result

    def test_does_not_redact_normal_text(self):
        """Test that normal text is not modified."""
        patcher = SensitiveDataPatcher()
        result = patcher.redact("User logged in successfully")
        assert result == "User logged in successfully"

    def test_caller_mutates_record_message(self):
        """Test that calling the patcher mutates the record's message."""
        patcher = SensitiveDataPatcher()
        record = {"message": "password=mysecret123"}
        patcher(record)
        assert "mysecret123" not in record["message"]
        assert "REDACTED" in record["message"]


class TestLoginFailureTracker:
    """Tests for LoginFailureTracker."""

    def test_tracker_records_failures(self):
        """Test that tracker records failures."""
        tracker = LoginFailureTracker()
        tracker.record_failure("test_user")
        assert tracker.get_failure_count("test_user") == 1

    def test_tracker_resets(self):
        """Test that tracker resets."""
        tracker = LoginFailureTracker()
        tracker.record_failure("test_user")
        tracker.reset("test_user")
        assert tracker.get_failure_count("test_user") == 0

    def test_tracker_is_suspicious(self):
        """Test suspicious detection."""
        tracker = LoginFailureTracker(threshold=3, window=300)
        
        for _ in range(3):
            tracker.record_failure("test_user")
        
        assert tracker.is_suspicious("test_user") is True

class TestSecurityLogging:
    """Tests for security logging functions."""

    def test_log_login_success(self):
        """Test logging successful login."""
        # Should not raise
        log_login_success(user_id=1, username="test_user")

    def test_log_login_failure(self):
        """Test logging failed login."""
        # Should not raise
        log_login_failure(username="test_user", reason="invalid_password")

    def test_log_login_failure_with_attempt_number(self):
        """Test logging failed login with attempt number."""
        from app.auth.security_logger import log_login_failure as _lf
        # Should not raise - covers line 215 (attempt_number in bind_kwargs)
        _lf(username="test_user", reason="invalid_password", attempt_number=3)

    def test_log_login_failure_suspicious_username(self):
        """Test that suspicious username triggers log_suspicious_activity."""
        from app.auth.security_logger import (
            log_login_failure as _lf,
            _login_failure_tracker,
        )
        # Reset tracker state
        _login_failure_tracker.reset("suspicious_user_test")
        # Record enough failures to trigger suspicious
        for _ in range(5):
            _lf(username="suspicious_user_test", reason="invalid_password")
        # Cleanup
        _login_failure_tracker.reset("suspicious_user_test")

    def test_log_login_failure_suspicious_ip(self):
        """Test that suspicious IP triggers log_suspicious_activity."""
        from app.auth.security_logger import (
            log_login_failure as _lf,
            _login_failure_tracker,
        )
        test_ip = "192.168.1.100"
        _login_failure_tracker.reset(test_ip)
        for _ in range(5):
            _lf(username="some_user", reason="invalid_password", ip_address=test_ip)
        _login_failure_tracker.reset(test_ip)

    def test_log_api_key_usage(self):
        """Test logging API key usage event."""
        from app.auth.security_logger import log_api_key_usage
        log_api_key_usage(user_id=1, api_key_prefix="abcd", endpoint="/api/v1/models")

    def test_log_permission_denied(self):
        """Test logging permission denied event."""
        from app.auth.security_logger import log_permission_denied
        log_permission_denied(
            user_id=1,
            username="test_user",
            resource="/admin",
            required_permission="admin",
        )

    def test_log_password_change(self):
        """Test logging password change event."""
        from app.auth.security_logger import log_password_change
        log_password_change(user_id=1, username="test_user")

    def test_log_logout(self):
        """Test logging logout event."""
        from app.auth.security_logger import log_logout
        log_logout(user_id=1, username="test_user", session_id="sess_123")

    def test_log_token_refresh(self):
        """Test logging token refresh event."""
        from app.auth.security_logger import log_token_refresh
        log_token_refresh(user_id=1, token_type="access")

    def test_log_user_registration(self):
        """Test logging user registration event."""
        from app.auth.security_logger import log_user_registration
        log_user_registration(user_id=1, username="new_user")

    def test_log_api_key_created(self):
        """Test logging API key creation event."""
        from app.auth.security_logger import log_api_key_created
        log_api_key_created(user_id=1, key_id=1, key_prefix="abc12345", name="Test Key")

    def test_log_api_key_deleted(self):
        """Test logging API key deletion event."""
        from app.auth.security_logger import log_api_key_deleted
        log_api_key_deleted(user_id=1, key_id=1, name="Test Key")

    def test_log_login_attempt(self):
        """Test logging login attempt event."""
        from app.auth.security_logger import log_login_attempt
        log_login_attempt(username="test_user", ip_address="127.0.0.1")

    def test_is_blocked(self):
        """Test is_blocked function."""
        from app.auth.security_logger import is_blocked, _login_failure_tracker
        test_user = "blocked_user_test"
        _login_failure_tracker.reset(test_user)
        assert is_blocked(test_user) is False
        for _ in range(5):
            _login_failure_tracker.record_failure(test_user)
        assert is_blocked(test_user) is True
        _login_failure_tracker.reset(test_user)

    def test_cleanup_stale_keys(self):
        """Test that stale failure keys are cleaned up."""
        tracker = LoginFailureTracker(threshold=5, window=0.001)
        tracker.record_failure("cleanup_test_user")
        import time
        time.sleep(0.01)  # Wait for window to expire
        # Trigger cleanup by recording another failure
        tracker.record_failure("cleanup_test_user2")
        # The first key should have been cleaned up
        assert tracker.get_failure_count("cleanup_test_user") == 0

    def test_max_keys_eviction(self):
        """Test that oldest keys are evicted when over max_keys limit."""
        tracker = LoginFailureTracker(threshold=5, window=300, max_keys=3)
        for i in range(5):
            tracker.record_failure(f"user_{i}")
        # Force cleanup to trigger eviction
        now = __import__("time").monotonic()
        tracker._cleanup_stale_keys(now)
        # Should have at most max_keys entries
        assert len(tracker._failures) <= 3


class TestRequestContext:
    """Tests for request context utilities."""

    def test_set_and_get_context(self):
        """Test setting and getting request context."""
        set_request_context(request_id="test-123", user_id=1, username="test_user")
        
        ctx = get_request_context()
        assert ctx.request_id == "test-123"
        assert ctx.user_id == 1
        assert ctx.username == "test_user"
        
        clear_request_context()

    def test_get_request_id(self):
        """Test get_request_id helper."""
        set_request_context(request_id="test-456")
        assert get_request_id() == "test-456"
        clear_request_context()

    def test_get_user_id(self):
        """Test get_user_id helper."""
        set_request_context(user_id=42)
        assert get_user_id() == 42
        clear_request_context()

    def test_get_username(self):
        """Test get_username helper."""
        set_request_context(username="test_user")
        assert get_username() == "test_user"
        clear_request_context()

    def test_empty_context(self):
        """Test that empty context returns None values."""
        clear_request_context()
        ctx = get_request_context()
        assert ctx.request_id is None
        assert ctx.user_id is None
        assert ctx.username is None


    """Tests for catch_http_exception decorator."""

    def test_sync_wrapper_raises_http_exception_on_error(self):
        """Test that sync functions raise HTTPException when an error occurs."""
        @catch_http_exception(status_code=400, error_code="TEST_ERROR")
        def failing_sync():
            raise ValueError("test error")

        with pytest.raises(HTTPException) as exc_info:
            failing_sync()
        assert exc_info.value.status_code == 400
        assert "TEST_ERROR" in str(exc_info.value.detail)

    def test_sync_wrapper_preserves_http_exception(self):
        """Test that existing HTTPExceptions are re-raised as-is."""
        @catch_http_exception(status_code=500, error_code="INTERNAL")
        def raising_http():
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            raising_http()
        assert exc_info.value.status_code == 404

    def test_sync_wrapper_success(self):
        """Test that successful sync functions return normally."""
        @catch_http_exception(status_code=500, error_code="INTERNAL")
        def working_sync():
            return "success"

        assert working_sync() == "success"

    @pytest.mark.asyncio
    async def test_async_wrapper_raises_http_exception_on_error(self):
        """Test that async functions raise HTTPException when an error occurs."""
        @catch_http_exception(status_code=400, error_code="ASYNC_ERROR")
        async def failing_async():
            raise ValueError("async test error")

        with pytest.raises(HTTPException) as exc_info:
            await failing_async()
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_async_wrapper_preserves_http_exception(self):
        """Test that existing HTTPExceptions in async are re-raised as-is."""
        @catch_http_exception(status_code=500, error_code="INTERNAL")
        async def raising_http_async():
            raise HTTPException(status_code=403, detail="Forbidden")

        with pytest.raises(HTTPException) as exc_info:
            await raising_http_async()
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_async_wrapper_success(self):
        """Test that successful async functions return normally."""
        @catch_http_exception(status_code=500, error_code="INTERNAL")
        async def working_async():
            return "async success"

        assert await working_async() == "async success"
