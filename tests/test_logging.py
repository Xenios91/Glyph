"""Tests for logging configuration and utilities using loguru."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from loguru import logger

from app.utils.logging_config import (
    setup_logging,
    SensitiveDataPatcher,
    setup_logging_from_config,
)
from app.utils.request_context import (
    RequestContext,
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
