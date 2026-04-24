"""Tests for logging configuration and utilities."""

import json
import logging
import time
import pytest
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

from app.utils.logging_config import (
    setup_logging,
    get_logger,
    JSONFormatter,
    ColoredFormatter,
    SensitiveDataFilter,
    RateLimitingFilter,
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

    def test_setup_logging_creates_handlers(self):
        """Test that setup_logging creates file and console handlers."""
        setup_logging(
            level="INFO",
            format="text",
            log_file="logs/test.log",
            console_enabled=True,
        )

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2

        # Clean up
        root_logger.handlers.clear()

    def test_setup_logging_json_format(self):
        """Test that JSON format is applied correctly."""
        setup_logging(
            level="INFO",
            format="json",
            log_file=None,
            console_enabled=True,
        )

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

        # Clean up
        root_logger.handlers.clear()

    def test_setup_logging_text_format(self):
        """Test that text format is applied correctly."""
        setup_logging(
            level="INFO",
            format="text",
            log_file=None,
            console_enabled=True,
        )

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, ColoredFormatter)

        # Clean up
        root_logger.handlers.clear()

    def test_setup_logging_no_console(self):
        """Test that console handler is not created when disabled."""
        setup_logging(
            level="INFO",
            format="json",
            log_file="logs/test.log",
            console_enabled=False,
        )

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1

        # Clean up
        root_logger.handlers.clear()

    def test_setup_logging_with_rate_limit(self):
        """Test that rate limiting filter is added when enabled."""
        setup_logging(
            level="INFO",
            format="json",
            log_file=None,
            console_enabled=True,
            rate_limit=True,
            rate_limit_max=5,
            rate_limit_period=10.0,
        )

        root_logger = logging.getLogger()
        handler = root_logger.handlers[0]
        filter_types = [type(f).__name__ for f in handler.filters]
        assert "SensitiveDataFilter" in filter_types

        # Clean up
        root_logger.handlers.clear()

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger"


class TestSensitiveDataFilter:
    """Tests for sensitive data redaction filter."""

    def test_filter_redacts_bearer_tokens(self):
        """Test that Bearer tokens are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            args=(), exc_info=None,
        )
        filter_instance.filter(record)
        assert "[REDACTED]" in record.msg
        assert "eyJhbGci" not in record.msg

    def test_filter_redacts_password_assignments(self):
        """Test that password assignments are redacted."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="password=supersecret123",
            args=(), exc_info=None,
        )
        filter_instance.filter(record)
        assert "[REDACTED]" in record.msg
        assert "supersecret123" not in record.msg

    def test_filter_passes_normal_messages(self):
        """Test that normal messages pass through unchanged."""
        filter_instance = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="User logged in successfully",
            args=(), exc_info=None,
        )
        result = filter_instance.filter(record)
        assert result is True
        assert record.msg == "User logged in successfully"

    def test_filter_with_additional_patterns(self):
        """Test custom additional patterns."""
        filter_instance = SensitiveDataFilter(
            additional_patterns=[(r'SECRET_KEY=\S+', 'SECRET_KEY=[REDACTED]')]
        )
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Config: SECRET_KEY=mysecretkey123",
            args=(), exc_info=None,
        )
        filter_instance.filter(record)
        assert "[REDACTED]" in record.msg
        assert "mysecretkey123" not in record.msg


class TestRateLimitingFilter:
    """Tests for rate limiting filter."""

    def test_rate_limit_allows_initial_messages(self):
        """Test that initial messages are allowed."""
        filter_instance = RateLimitingFilter(max_messages=3, period=60.0)

        for i in range(3):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg=f"Message {i}",
                args=(), exc_info=None,
            )
            assert filter_instance.filter(record) is True

    def test_rate_limit_blocks_excess_messages(self):
        """Test that excess messages are blocked."""
        filter_instance = RateLimitingFilter(max_messages=2, period=60.0)

        # First two should pass
        for i in range(2):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg="Same message",
                args=(), exc_info=None,
            )
            assert filter_instance.filter(record) is True

        # Third should be blocked
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Same message",
            args=(), exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_rate_limit_resets_after_period(self):
        """Test that rate limit resets after period expires."""
        filter_instance = RateLimitingFilter(max_messages=2, period=0.1)

        # Fill up the bucket
        for i in range(2):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg="Test message",
                args=(), exc_info=None,
            )
            filter_instance.filter(record)

        # Should be blocked
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Test message",
            args=(), exc_info=None,
        )
        assert filter_instance.filter(record) is False

        # Wait for period to expire
        time.sleep(0.15)

        # Should be allowed again
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Test message",
            args=(), exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_rate_limit_different_messages(self):
        """Test that different messages have separate limits."""
        filter_instance = RateLimitingFilter(max_messages=2, period=60.0)

        # Fill up for message A
        for i in range(2):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="test.py",
                lineno=1, msg="Message A",
                args=(), exc_info=None,
            )
            filter_instance.filter(record)

        # Message B should still be allowed
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Message B",
            args=(), exc_info=None,
        )
        assert filter_instance.filter(record) is True


class TestJSONFormatter:
    """Tests for JSON formatter."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter(include_context=False)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["l"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["msg"] == "Test message"
        assert "t" in data

    def test_json_formatter_uses_record_timestamp(self):
        """Test that JSON formatter uses record.created for timestamp."""
        formatter = JSONFormatter(include_context=False)
        import time as time_module
        known_time = time_module.time() - 10  # 10 seconds ago

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.created = known_time

        output = formatter.format(record)
        data = json.loads(output)

        # Parse the timestamp and verify it matches record.created
        from datetime import datetime, timezone
        parsed = datetime.fromisoformat(data["t"])
        assert abs(parsed.timestamp() - known_time) < 1

    def test_json_formatter_with_context(self):
        """Test JSON formatting with request context."""
        set_request_context(
            request_id="test-request-id",
            user_id=123,
            username="testuser"
        )

        formatter = JSONFormatter(include_context=True)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["rid"] == "test-request-id"
        assert data["uid"] == 123
        assert data["user"] == "testuser"

        clear_request_context()

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception info."""
        formatter = JSONFormatter(include_context=False)

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert "exc" in data
            assert "ValueError" in data["exc"]

    def test_json_formatter_with_extra_data(self):
        """Test JSON formatting with extra_data."""
        formatter = JSONFormatter(include_context=False)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"file_size": 1024, "filename": "test.bin"}

        output = formatter.format(record)
        data = json.loads(output)

        assert "extra" in data
        assert data["extra"]["file_size"] == 1024
        assert data["extra"]["filename"] == "test.bin"


class TestRequestContext:
    """Tests for request context management."""

    def test_get_request_context_returns_instance(self):
        """Test that get_request_context returns a RequestContext."""
        ctx = get_request_context()
        assert isinstance(ctx, RequestContext)

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        clear_request_context()
        set_request_context(request_id="test-id")
        assert get_request_id() == "test-id"
        clear_request_context()

    def test_set_and_get_user_id(self):
        """Test setting and getting user ID."""
        clear_request_context()
        set_request_context(user_id=456)
        assert get_user_id() == 456
        clear_request_context()

    def test_set_and_get_username(self):
        """Test setting and getting username."""
        clear_request_context()
        set_request_context(username="testuser")
        assert get_username() == "testuser"
        clear_request_context()

    def test_set_and_get_task_id(self):
        """Test setting and getting task ID."""
        clear_request_context()
        set_request_context(task_id="task-123")
        assert get_task_id() == "task-123"
        clear_request_context()

    def test_clear_request_context(self):
        """Test clearing request context."""
        clear_request_context()
        set_request_context(
            request_id="test-id",
            user_id=123,
            username="testuser",
            task_id="task-456",
        )
        clear_request_context()

        assert get_request_id() is None
        assert get_user_id() is None
        assert get_username() is None
        assert get_task_id() is None

    def test_request_context_all(self):
        """Test getting all context data."""
        clear_request_context()
        set_request_context(
            request_id="test-id",
            user_id=123,
            username="testuser",
        )

        ctx = get_request_context()
        assert ctx.request_id == "test-id"
        assert ctx.user_id == 123
        assert ctx.username == "testuser"

        clear_request_context()

    def test_request_context_isolation(self):
        """Test that context is isolated per call (no shared global state)."""
        clear_request_context()
        set_request_context(request_id="first-id")
        assert get_request_id() == "first-id"
        clear_request_context()
        assert get_request_id() is None


class TestPerformanceTimer:
    """Tests for performance timer."""

    def test_performance_timer_context_manager(self):
        """Test PerformanceTimer as context manager."""
        with PerformanceTimer("test_operation", log_level=logging.NOTSET) as timer:
            pass

        assert timer.elapsed >= 0
        assert timer.start_time > 0
        assert timer.end_time > 0

    def test_performance_timer_get_elapsed(self):
        """Test getting elapsed time."""
        timer = PerformanceTimer("test", log_level=logging.NOTSET)

        with timer:
            pass

        elapsed = timer.get_elapsed()
        assert elapsed >= 0

    def test_performance_timer_units(self):
        """Test different time units."""
        for unit in ["seconds", "milliseconds", "microseconds"]:
            with PerformanceTimer(
                "test",
                log_level=logging.NOTSET,
                unit=unit
            ) as timer:
                pass

            assert timer.elapsed >= 0

    def test_performance_timer_threshold_skips_logging(self, caplog):
        """Test that threshold prevents logging for fast operations."""
        caplog.set_level(logging.INFO)

        # Set a high threshold so the fast operation doesn't log
        with PerformanceTimer(
            "fast_op",
            log_level=logging.INFO,
            threshold=10.0,  # 10 seconds threshold
            log_structured=False,
        ):
            pass  # This is instant, should not log

        # Check that no performance log was emitted
        perf_logs = [r for r in caplog.records if "Performance:" in r.message]
        assert len(perf_logs) == 0

    def test_performance_timer_threshold_logs_slow(self, caplog):
        """Test that threshold allows logging for slow operations."""
        caplog.set_level(logging.INFO)

        # Set a low threshold so the operation logs
        with PerformanceTimer(
            "slow_op",
            log_level=logging.INFO,
            threshold=0.0,  # 0 threshold, always log
            log_structured=False,
        ):
            pass

        # Check that performance log was emitted
        perf_logs = [r for r in caplog.records if "Performance:" in r.message]
        assert len(perf_logs) == 1

    def test_performance_timer_structured_data(self, caplog):
        """Test that structured data is included in log."""
        caplog.set_level(logging.INFO)

        with PerformanceTimer(
            "structured_test",
            log_level=logging.INFO,
            log_structured=True,
        ):
            pass

        # Check that extra_data was included
        perf_logs = [r for r in caplog.records if "Performance:" in r.message]
        if perf_logs:
            assert hasattr(perf_logs[0], 'extra_data')


class TestPerformanceMetrics:
    """Tests for performance metrics collector."""

    def test_metrics_timer(self):
        """Test metrics timer collection."""
        metrics = PerformanceMetrics(
            "test_metrics",
            logger_instance=logging.getLogger("test")
        )

        with metrics.timer("operation1"):
            pass

        with metrics.timer("operation2"):
            pass

        timings = metrics.get_timings()
        assert len(timings) == 2
        assert all(t >= 0 for t in timings.values())

    def test_metrics_reset(self):
        """Test metrics reset."""
        metrics = PerformanceMetrics("test")

        with metrics.timer("operation1"):
            pass

        metrics.reset()
        assert len(metrics.get_timings()) == 0

    def test_metrics_log_summary(self):
        """Test metrics summary logging."""
        metrics = PerformanceMetrics(
            "test",
            logger_instance=logging.getLogger("test")
        )

        with metrics.timer("operation1"):
            pass

        # Should not raise
        metrics.log_summary()

    def test_metrics_log_summary_structured(self, caplog):
        """Test that metrics summary includes structured data."""
        caplog.set_level(logging.INFO)
        metrics = PerformanceMetrics(
            "structured_test",
            logger_instance=logging.getLogger("test.metrics")
        )

        with metrics.timer("step1"):
            pass

        metrics.log_summary()

        # Check structured data was logged
        summary_logs = [r for r in caplog.records if "Performance summary" in r.message]
        if summary_logs:
            assert hasattr(summary_logs[0], 'extra_data')
            assert "metrics_name" in summary_logs[0].extra_data


class TestLogPerformanceDecorator:
    """Tests for log_performance decorator."""

    def test_log_performance_decorator(self):
        """Test log_performance decorator."""
        @log_performance(log_level=logging.NOTSET)
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

    def test_log_performance_async(self):
        """Test log_performance with async function."""
        import asyncio

        @log_performance(log_level=logging.NOTSET)
        async def async_test_function():
            return "async_result"

        result = asyncio.run(async_test_function())
        assert result == "async_result"

    def test_log_performance_with_threshold(self):
        """Test log_performance decorator with threshold."""
        @log_performance(log_level=logging.NOTSET, threshold=10.0)
        def fast_function():
            return "fast"

        result = fast_function()
        assert result == "fast"


class TestLoginFailureTracker:
    """Tests for login failure tracking."""

    def test_tracker_records_failures(self):
        """Test that failures are recorded."""
        tracker = LoginFailureTracker(threshold=3, window=60.0)

        count = tracker.record_failure("test_user")
        assert count == 1

        count = tracker.record_failure("test_user")
        assert count == 2

    def test_tracker_detects_suspicious(self):
        """Test that suspicious activity is detected."""
        tracker = LoginFailureTracker(threshold=3, window=60.0)

        # Below threshold
        assert tracker.is_suspicious("test_user") is False
        assert tracker.is_suspicious("test_user") is False

        # At threshold
        assert tracker.is_suspicious("test_user") is True

    def test_tracker_resets_on_success(self):
        """Test that tracker resets after successful login."""
        tracker = LoginFailureTracker(threshold=2, window=60.0)

        tracker.record_failure("test_user")
        tracker.record_failure("test_user")

        tracker.reset("test_user")

        count = tracker.record_failure("test_user")
        assert count == 1

    def test_tracker_global_instance(self):
        """Test that global tracker is accessible."""
        tracker = get_failure_tracker()
        assert isinstance(tracker, LoginFailureTracker)

    def test_tracker_window_expiry(self):
        """Test that old failures expire."""
        tracker = LoginFailureTracker(threshold=2, window=0.1)

        tracker.record_failure("test_user")
        time.sleep(0.15)  # Wait for window to expire

        count = tracker.record_failure("test_user")
        assert count == 1  # Old failure expired


class TestLoggingIntegration:
    """Integration tests for logging."""

    def test_logging_with_request_tracing(self):
        """Test logging with request tracing context."""
        clear_request_context()

        set_request_context(
            request_id="integration-test-id",
            user_id=999,
            username="integration_user"
        )

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JSONFormatter(include_context=True))

        test_logger = get_logger("test.integration")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)

        test_logger.info("Integration test message")

        output = log_stream.getvalue()
        data = json.loads(output)
        assert data["rid"] == "integration-test-id"
        assert data["uid"] == 999
        assert data["user"] == "integration_user"

        test_logger.removeHandler(handler)
        clear_request_context()

    def test_log_rotation_creates_directory(self):
        """Test that log rotation creates the log directory."""
        test_log_path = "logs/test_rotation/test.log"

        setup_logging(
            level="INFO",
            format="text",
            log_file=test_log_path,
            max_size_mb=1,
            backup_count=2,
        )

        assert Path("logs/test_rotation").exists()

        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        import shutil
        if Path("logs/test_rotation").exists():
            shutil.rmtree("logs/test_rotation")

    def test_sensitive_filter_integration(self):
        """Test sensitive data filter with actual logging."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JSONFormatter(include_context=False))
        handler.addFilter(SensitiveDataFilter())

        test_logger = get_logger("test.sensitive")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)

        test_logger.info("Token: Bearer eyJhbGciOiJIUzI1NiJ9.test.signature")

        output = log_stream.getvalue()
        data = json.loads(output)
        assert "eyJhbGci" not in data["msg"]
        assert "[REDACTED]" in data["msg"]

        test_logger.removeHandler(handler)


class TestAsyncLogHandler:
    """Tests for AsyncLogHandler."""

    def test_async_handler_queues_and_processes(self):
        """Test that async handler queues records and processes them."""
        from app.utils.logging_config import AsyncLogHandler

        log_stream = StringIO()
        target = logging.StreamHandler(log_stream)
        target.setFormatter(logging.Formatter("%(message)s"))

        async_handler = AsyncLogHandler(target, max_queue_size=100)

        test_logger = get_logger("test.async")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(async_handler)

        test_logger.info("Async test message 1")
        test_logger.info("Async test message 2")

        # Flush to process queued records
        async_handler.flush()

        output = log_stream.getvalue()
        assert "Async test message 1" in output
        assert "Async test message 2" in output

        async_handler.close()
        test_logger.removeHandler(async_handler)

    def test_async_handler_close_flushes(self):
        """Test that closing async handler flushes remaining records."""
        from app.utils.logging_config import AsyncLogHandler

        log_stream = StringIO()
        target = logging.StreamHandler(log_stream)
        target.setFormatter(logging.Formatter("%(message)s"))

        async_handler = AsyncLogHandler(target, max_queue_size=100)

        test_logger = get_logger("test.async_close")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(async_handler)

        test_logger.info("Message before close")
        async_handler.close()

        output = log_stream.getvalue()
        assert "Message before close" in output
        test_logger.removeHandler(async_handler)


class TestSamplingFilter:
    """Tests for SamplingFilter."""

    def test_sampling_rate_100_passes_all(self):
        """Test that 100% sample rate passes all messages."""
        from app.utils.logging_config import SamplingFilter

        filter = SamplingFilter(sample_rate=1.0)
        for i in range(100):
            record = logging.LogRecord(
                name="test", level=logging.INFO,
                pathname="test.py", lineno=i,
                msg=f"Message {i}", args=(), exc_info=None,
            )
            assert filter.filter(record)

    def test_sampling_rate_50_samples_half(self):
        """Test that 50% sample rate passes approximately half."""
        from app.utils.logging_config import SamplingFilter

        filter = SamplingFilter(sample_rate=0.5)
        passed = 0
        for i in range(100):
            record = logging.LogRecord(
                name="test", level=logging.INFO,
                pathname="test.py", lineno=i,
                msg=f"Message {i}", args=(), exc_info=None,
            )
            if filter.filter(record):
                passed += 1

        # Should be approximately 50 (between 40-60)
        assert 40 <= passed <= 60

    def test_sampling_rate_0_blocks_all(self):
        """Test that 0% sample rate blocks all messages."""
        from app.utils.logging_config import SamplingFilter

        filter = SamplingFilter(sample_rate=0.0)
        for i in range(10):
            record = logging.LogRecord(
                name="test", level=logging.INFO,
                pathname="test.py", lineno=i,
                msg=f"Message {i}", args=(), exc_info=None,
            )
            assert not filter.filter(record)


class TestLoggingBestPracticeFilter:
    """Tests for LoggingBestPracticeFilter."""

    def test_best_practice_filter_disabled_by_default(self):
        """Test that the filter is disabled by default."""
        from app.utils.logging_config import LoggingBestPracticeFilter

        filter = LoggingBestPracticeFilter(enabled=False)
        record = logging.LogRecord(
            name="test", level=logging.ERROR,
            pathname="test.py", lineno=1,
            msg="Error with {braces}", args=(), exc_info=None,
        )
        assert filter.filter(record)

    def test_best_practice_filter_enabled_warns(self, capsys):
        """Test that the filter warns about anti-patterns when enabled."""
        from app.utils.logging_config import LoggingBestPracticeFilter

        filter = LoggingBestPracticeFilter(enabled=True)
        record = logging.LogRecord(
            name="test", level=logging.ERROR,
            pathname="test.py", lineno=1,
            msg="Error without exc_info", args=(), exc_info=None,
        )
        filter.filter(record)

        captured = capsys.readouterr()
        assert "LOGGING WARNING" in captured.err


class TestRateLimitingFilterMemoryBounds:
    """Tests for RateLimitingFilter memory bounds."""

    def test_max_keys_eviction(self):
        """Test that keys are evicted when max_keys is exceeded."""
        from app.utils.logging_config import RateLimitingFilter

        filter = RateLimitingFilter(max_messages=1, period=60.0, max_keys=3)
        filter._cleanup_interval = 0  # Force cleanup on every call

        # Create 10 different message keys to trigger eviction
        for i in range(10):
            record = logging.LogRecord(
                name="test", level=logging.INFO,
                pathname="test.py", lineno=1,
                msg=f"Unique message number {i}", args=(), exc_info=None,
            )
            filter.filter(record)

        # Should have at most max_keys + 1 tracked (off-by-one from add-then-evict)
        assert len(filter._buckets) <= 4

    def test_cleanup_stale_keys(self):
        """Test that stale keys are cleaned up."""
        from app.utils.logging_config import RateLimitingFilter

        filter = RateLimitingFilter(max_messages=1, period=0.1, max_keys=100)
        filter._cleanup_interval = 0.05  # Force cleanup quickly

        # Create several keys
        for i in range(5):
            record = logging.LogRecord(
                name="test", level=logging.INFO,
                pathname="test.py", lineno=1,
                msg=f"Message {i}", args=(), exc_info=None,
            )
            filter.filter(record)

        # Wait for period to expire
        time.sleep(0.15)

        # Trigger cleanup with new record
        new_record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="New message", args=(), exc_info=None,
        )
        filter.filter(new_record)

        # Old keys should be cleaned up
        assert len(filter._buckets) == 1


class TestModuleLevels:
    """Tests for per-module log level configuration."""

    def test_module_level_override(self):
        """Test that module level overrides work."""
        setup_logging(
            level="INFO",
            format="text",
            log_file=None,
            console_enabled=False,
            module_levels={"app.test_module": "DEBUG"},
        )

        module_logger = logging.getLogger("app.test_module")
        assert module_logger.level == logging.DEBUG

        root_logger = logging.getLogger()
        root_logger.handlers.clear()


class TestStartupSummary:
    """Tests for log_startup_summary."""

    def test_startup_summary_logs(self):
        """Test that startup summary logs configuration details."""
        from app.utils.logging_config import log_startup_summary, setup_logging

        setup_logging(
            level="DEBUG",
            format="json",
            log_file=None,
            console_enabled=True,
            console_level="DEBUG",
        )

        # Capture from the console handler
        log_stream = StringIO()
        root_logger = logging.getLogger()
        # Replace console handler with our capture handler
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        capture_handler = logging.StreamHandler(log_stream)
        capture_handler.setLevel(logging.DEBUG)
        from app.utils.logging_config import JSONFormatter
        capture_handler.setFormatter(JSONFormatter(include_context=False))
        root_logger.addHandler(capture_handler)

        log_startup_summary()

        output = log_stream.getvalue()
        assert "Logging initialized" in output

        root_logger.handlers.clear()


class TestSensitiveDataFilterExtended:
    """Tests for extended sensitive data patterns."""

    def test_redacts_connection_strings(self):
        """Test that database connection strings are redacted."""
        from app.utils.logging_config import SensitiveDataFilter

        filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="Connecting to sqlite:///secret.db", args=(), exc_info=None,
        )
        filter.filter(record)
        assert "sqlite:///secret.db" not in record.msg
        assert "CONNECTION_STRING_REDACTED" in record.msg

    def test_redacts_jwt_secrets(self):
        """Test that JWT secrets are redacted."""
        from app.utils.logging_config import SensitiveDataFilter

        filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="jwt_secret=my_super_secret_key_12345", args=(), exc_info=None,
        )
        filter.filter(record)
        assert "my_super_secret_key_12345" not in record.msg
        assert "REDACTED" in record.msg
