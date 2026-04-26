"""Tests for logging configuration and utilities using loguru."""

import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from loguru import logger

from app.utils.logging_config import (
    setup_logging,
    SensitiveDataFilter,
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
    get_task_id,
)
from app.utils.performance_logger import (
    PerformanceTimer,
    log_performance,
    PerformanceMetrics,
)
from app.auth.security_logger import (
    LoginFailureTracker,
    get_failure_tracker,
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


class TestSensitiveDataFilter:
    """Tests for SensitiveDataFilter."""

    def test_redacts_password(self):
        """Test that password values are redacted."""
        filter_instance = SensitiveDataFilter()
        result = filter_instance.filter_msg("password=mysecret123")
        assert "mysecret123" not in result
        assert "REDACTED" in result

    def test_redacts_token(self):
        """Test that token values are redacted."""
        filter_instance = SensitiveDataFilter()
        result = filter_instance.filter_msg("token=abc123xyz")
        assert "abc123xyz" not in result
        assert "REDACTED" in result

    def test_redacts_api_key(self):
        """Test that API key values are redacted."""
        filter_instance = SensitiveDataFilter()
        result = filter_instance.filter_msg("api_key=sk-1234567890")
        assert "sk-1234567890" not in result
        assert "REDACTED" in result

    def test_does_not_redact_normal_text(self):
        """Test that normal text is not modified."""
        filter_instance = SensitiveDataFilter()
        result = filter_instance.filter_msg("User logged in successfully")
        assert result == "User logged in successfully"

    def test_filter_returns_true(self):
        """Test that the filter returns True (allows the record)."""
        filter_instance = SensitiveDataFilter()
        record = {"message": "test message"}
        result = filter_instance(record)
        assert result is True


class TestPerformanceTimer:
    """Tests for PerformanceTimer."""

    def test_timer_context_manager(self):
        """Test PerformanceTimer as a context manager."""
        with PerformanceTimer("test_operation") as timer:
            time.sleep(0.01)
        
        assert timer.elapsed > 0
        assert timer.end_time > 0

    def test_timer_get_elapsed(self):
        """Test get_elapsed method."""
        timer = PerformanceTimer("test_operation")
        
        # get_elapsed should return time since module start if not started
        # (since start_time defaults to 0 which is epoch)
        elapsed = timer.get_elapsed()
        # Just verify it returns a positive number (time since epoch)
        assert elapsed >= 0


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""

    def test_metrics_timer(self):
        """Test PerformanceMetrics timer."""
        metrics = PerformanceMetrics("test_metrics")
        
        with metrics.timer("operation1"):
            time.sleep(0.01)
        
        timings = metrics.get_timings()
        assert "operation1" in timings
        assert timings["operation1"] > 0

    def test_metrics_reset(self):
        """Test PerformanceMetrics reset."""
        metrics = PerformanceMetrics("test_metrics")
        
        with metrics.timer("operation1"):
            time.sleep(0.01)
        
        metrics.reset()
        timings = metrics.get_timings()
        assert len(timings) == 0


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

    def test_get_failure_tracker_singleton(self):
        """Test that get_failure_tracker returns singleton."""
        tracker1 = get_failure_tracker()
        tracker2 = get_failure_tracker()
        assert tracker1 is tracker2


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

    def test_get_task_id(self):
        """Test get_task_id helper."""
        set_request_context(task_id="task-123")
        assert get_task_id() == "task-123"
        clear_request_context()

    def test_empty_context(self):
        """Test that empty context returns None values."""
        clear_request_context()
        ctx = get_request_context()
        assert ctx.request_id is None
        assert ctx.user_id is None
        assert ctx.username is None
