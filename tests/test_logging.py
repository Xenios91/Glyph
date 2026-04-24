"""Tests for logging configuration and utilities."""

import json
import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.logging_config import (
    setup_logging,
    get_logger,
    JSONFormatter,
    ColoredFormatter,
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
from app.utils.performance_logger import (
    PerformanceTimer,
    log_performance,
    PerformanceMetrics,
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
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.logger"


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
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data
    
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
        
        assert data["request_id"] == "test-request-id"
        assert data["user_id"] == 123
        assert data["username"] == "testuser"
        
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
            
            assert "exception" in data
            assert "ValueError" in data["exception"]


class TestRequestContext:
    """Tests for request context management."""
    
    def test_get_request_context_returns_instance(self):
        """Test that get_request_context returns a RequestContext."""
        ctx = get_request_context()
        assert isinstance(ctx, RequestContext)
    
    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        clear_request_context()  # Clear any existing context
        set_request_context(request_id="test-id")
        assert get_request_id() == "test-id"
        clear_request_context()
    
    def test_set_and_get_user_id(self):
        """Test setting and getting user ID."""
        clear_request_context()  # Clear any existing context
        set_request_context(user_id=456)
        assert get_user_id() == 456
        clear_request_context()
    
    def test_set_and_get_username(self):
        """Test setting and getting username."""
        clear_request_context()  # Clear any existing context
        set_request_context(username="testuser")
        assert get_username() == "testuser"
        clear_request_context()
    
    def test_clear_request_context(self):
        """Test clearing request context."""
        clear_request_context()  # Clear any existing context
        set_request_context(
            request_id="test-id",
            user_id=123,
            username="testuser"
        )
        clear_request_context()
        
        assert get_request_id() is None
        assert get_user_id() is None
        assert get_username() is None
    
    def test_request_context_all(self):
        """Test getting all context data."""
        clear_request_context()  # Clear any existing context
        set_request_context(
            request_id="test-id",
            user_id=123,
            username="testuser"
        )
        
        ctx = get_request_context()
        # Access properties directly
        assert ctx.request_id == "test-id"
        assert ctx.user_id == 123
        assert ctx.username == "testuser"
        
        clear_request_context()


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


class TestPerformanceMetrics:
    """Tests for performance metrics collector."""
    
    def test_metrics_timer(self):
        """Test metrics timer collection."""
        metrics = PerformanceMetrics("test_metrics", logger=logging.getLogger("test"))
        
        with metrics.timer("operation1"):
            pass
        
        with metrics.timer("operation2"):
            pass
        
        # Timings should be collected immediately after context manager exits
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
        metrics = PerformanceMetrics("test", logger=logging.getLogger("test"))
        
        with metrics.timer("operation1"):
            pass
        
        # Should not raise
        metrics.log_summary()


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


class TestLoggingIntegration:
    """Integration tests for logging."""
    
    def test_logging_with_request_tracing(self):
        """Test logging with request tracing context."""
        # Clear any existing context first
        clear_request_context()
        
        # Set up request context
        set_request_context(
            request_id="integration-test-id",
            user_id=999,
            username="integration_user"
        )
        
        # Set up logging with a custom handler that captures output
        from io import StringIO
        
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JSONFormatter(include_context=True))
        
        logger = get_logger("test.integration")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        # Log a message
        logger.info("Integration test message")
        
        # Get the output
        output = log_stream.getvalue()
        
        # Check that output contains expected fields
        data = json.loads(output)
        assert data["request_id"] == "integration-test-id"
        assert data["user_id"] == 999
        assert data["username"] == "integration_user"
        
        # Clean up
        logger.removeHandler(handler)
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
        
        # Directory should be created
        assert Path("logs/test_rotation").exists()
        
        # Clean up
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Remove test directory
        import shutil
        if Path("logs/test_rotation").exists():
            shutil.rmtree("logs/test_rotation")
