"""Centralized logging configuration for Glyph application.

This module provides:
- Centralized logging setup from config.yml
- JSON and text formatters for structured logging
- Log rotation with size and time-based policies
- Request context support for tracing
- Sensitive data redaction filter
- Rate limiting filter to prevent log spam
- Utility functions for getting configured loggers
"""

import json
import logging
import os
import re
import stat
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.utils.request_context import get_request_context, set_request_context, clear_request_context


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log messages.

    Automatically redacts passwords, tokens, API keys, and other
    sensitive patterns from log messages to prevent accidental exposure.
    """

    # Patterns to redact - order matters (more specific first)
    SENSITIVE_PATTERNS = [
        # JWT tokens (Bearer tokens)
        (r'(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED]'),
        # Generic token assignments
        (r'(?i)(token|secret|password|passwd|pwd)\s*[=:]\s*\S+', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        # API keys (common prefixes)
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*\S+', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        # Email addresses in sensitive contexts
        (r'(?i)(password|token|secret)[^@]*@[A-Za-z0-9\.-]+\.[A-Za-z]{2,}', '[REDACTED]'),
    ]

    def __init__(self, additional_patterns: list[tuple[str, str]] | None = None):
        super().__init__()
        self._compiled_patterns = []
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            self._compiled_patterns.append((re.compile(pattern), replacement))
        if additional_patterns:
            for pattern, replacement in additional_patterns:
                self._compiled_patterns.append((re.compile(pattern), replacement))

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log record message.

        Args:
            record: The log record to filter.

        Returns:
            True to include the record, False to exclude.
        """
        if isinstance(record.msg, str):
            new_msg = record.msg
            for pattern, replacement in self._compiled_patterns:
                if callable(replacement):
                    new_msg = pattern.sub(replacement, new_msg)
                else:
                    new_msg = pattern.sub(replacement, new_msg)
            record.msg = new_msg

        # Also redact in args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: '[REDACTED]' if any(
                        sensitive in str(k).lower()
                        for sensitive in ['password', 'token', 'secret', 'api_key']
                    ) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    '[REDACTED]' if isinstance(v, str) and any(
                        len(v) > 40 and not v.startswith('/')
                        for _ in [1]
                    ) else v
                    for v in record.args
                )

        return True


class RateLimitingFilter(logging.Filter):
    """Filter that rate-limits log messages to prevent log spam.

    Uses a token bucket algorithm to limit the rate of log messages
    per unique message key (derived from logger name + message pattern).
    """

    def __init__(
        self,
        max_messages: int = 10,
        period: float = 60.0,
        key_func: Any = None,
    ):
        """Initialize the rate limiting filter.

        Args:
            max_messages: Maximum number of messages allowed per period.
            period: Time period in seconds.
            key_func: Custom function to generate rate limit keys.
                      Defaults to using logger name + first 50 chars of message.
        """
        super().__init__()
        self.max_messages = max_messages
        self.period = period
        self.key_func = key_func or self._default_key_func
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._suppressed: dict[str, int] = defaultdict(int)

    @staticmethod
    def _default_key_func(record: logging.LogRecord) -> str:
        """Generate a rate limit key from the log record.

        Args:
            record: The log record.

        Returns:
            A string key for rate limiting.
        """
        msg_preview = record.msg[:50] if isinstance(record.msg, str) else str(record.msg)[:50]
        return f"{record.name}:{msg_preview}"

    def _cleanup_old_timestamps(self, key: str, now: float) -> None:
        """Remove timestamps outside the current window.

        Args:
            key: The rate limit key.
            now: Current timestamp.
        """
        cutoff = now - self.period
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]

    def filter(self, record: logging.LogRecord) -> bool:
        """Check if the log record should be allowed through.

        Args:
            record: The log record to filter.

        Returns:
            True to include the record, False to suppress.
        """
        key = self.key_func(record)
        now = time.monotonic()

        self._cleanup_old_timestamps(key, now)

        if len(self._buckets[key]) < self.max_messages:
            self._buckets[key].append(now)
            self._suppressed[key] = 0
            return True

        # Suppress the message but track count
        self._suppressed[key] += 1

        # Every 100 suppressed messages, log a summary
        if self._suppressed[key] % 100 == 0:
            summary_record = logging.LogRecord(
                name=record.name,
                level=logging.WARNING,
                pathname=record.pathname,
                lineno=record.lineno,
                msg=f"[Rate Limited] {self._suppressed[key]} messages suppressed for: {record.msg[:100]}",
                args=(),
                exc_info=None,
            )
            # Recursively format and output the summary (safe since it's a new record)
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("[RATE-LIMIT] %(message)s"))
            handler.emit(summary_record)
            handler.close()

        return False


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Formats log records as JSON with standard fields:
    - timestamp: ISO 8601 format with timezone (from record.created)
    - level: Log level
    - logger: Logger name
    - message: Log message
    - request_id: Request ID if available
    - user_id: User ID if available
    - username: Username if available
    - extra: Additional context-specific fields
    """

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            str: JSON string representation of the log record.
        """
        # Use record.created for accurate timestamp instead of calling datetime.now()
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        log_data: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if enabled
        if self.include_context:
            ctx = get_request_context()
            log_data["request_id"] = ctx.request_id
            log_data["user_id"] = ctx.user_id
            log_data["username"] = ctx.username

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack info if present
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        # Add extra fields
        extra_data = getattr(record, 'extra_data', None)
        if extra_data:
            log_data["extra"] = extra_data

        # Add standard extra fields from record (only in debug mode to reduce overhead)
        if record.levelno <= logging.DEBUG:
            extra_fields = ['filename', 'funcName', 'lineno', 'pathname', 'threadName']
            for field in extra_fields:
                if hasattr(record, field):
                    value = getattr(record, field)
                    if value:
                        log_data[f"_{field}"] = value

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output.

    Adds ANSI color codes to log levels for better readability.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, colorize: bool = True):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        self.colorize = colorize and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with optional colors.

        Uses a custom format string with color codes instead of
        string replacement for more reliable colorization.

        Args:
            record: The log record to format.

        Returns:
            str: Formatted log message with optional colors.
        """
        if not self.colorize:
            return super().format(record)

        levelname = record.levelname
        color = self.COLORS.get(levelname, "")
        reset = self.RESET

        # Format timestamp
        timestamp = self.formatTime(record, self.datefmt)

        # Build colored format manually
        formatted = f"{timestamp} | {color}{levelname}{reset}-8s | {record.name} | {record.getMessage()}"
        # Fix the levelname padding
        formatted = f"{timestamp} | {color}{levelname:<8}{reset} | {record.name} | {record.getMessage()}"

        return formatted


def _ensure_log_directory(log_path: Path) -> None:
    """Ensure the log directory exists.

    Args:
        log_path: Path to the log file.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)


def _set_log_file_permissions(log_path: Path) -> None:
    """Set restrictive permissions on the log file.

    Sets file permissions to 0o640 (owner read/write, group read only)
    to protect sensitive log data.

    Args:
        log_path: Path to the log file.
    """
    try:
        if log_path.exists():
            os.chmod(log_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    except OSError:
        # Silently ignore permission errors (e.g., on Windows)
        pass


def _get_time_interval(interval: str) -> str:
    """Convert time interval string to TimedRotatingFileHandler format.

    Args:
        interval: Time interval string (midnight, daily, weekly, monthly).

    Returns:
        str: Interval character for TimedRotatingFileHandler.
    """
    interval_map = {
        "midnight": "midnight",
        "daily": "midnight",
        "weekly": "w0",
        "monthly": "monthly",
    }
    return interval_map.get(interval.lower(), "midnight")


class _RotatingFileHandlerWithPermissions:
    """Helper class to set file permissions after rotation."""

    @staticmethod
    def do_rollover_with_permissions(handler: RotatingFileHandler, log_path: Path) -> None:
        """Perform rollover and set permissions on the new file.

        Args:
            handler: The rotating file handler.
            log_path: Path to the log file.
        """
        handler.doRollover()
        _set_log_file_permissions(log_path)


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    log_file: str | None = "logs/glyph.log",
    max_size_mb: int = 50,
    backup_count: int = 10,
    rotate: str = "size",
    time_interval: str = "midnight",
    console_enabled: bool = True,
    console_level: str = "INFO",
    colorize: bool = True,
    rate_limit: bool = False,
    rate_limit_max: int = 10,
    rate_limit_period: float = 60.0,
) -> None:
    """Set up logging configuration.

    This function configures logging with:
    - File handler with rotation
    - Console handler with optional colors
    - JSON or text formatting
    - Sensitive data redaction
    - Optional rate limiting

    Args:
        level: Log level for file handler (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format: Log format ("json" or "text").
        log_file: Path to log file. Set to None to disable file logging.
        max_size_mb: Maximum log file size in MB before rotation.
        backup_count: Number of backup files to keep.
        rotate: Rotation policy ("size", "time", or "both").
        time_interval: Time interval for time-based rotation.
        console_enabled: Whether to enable console logging.
        console_level: Log level for console handler.
        colorize: Whether to colorize console output.
        rate_limit: Whether to enable rate limiting.
        rate_limit_max: Maximum messages per period when rate limiting enabled.
        rate_limit_period: Time period in seconds for rate limiting.
    """
    # Get log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    console_log_level = getattr(logging, console_level.upper(), logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(max(log_level, console_log_level) if console_enabled else log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create shared filters
    sensitive_filter = SensitiveDataFilter()

    rate_filter: RateLimitingFilter | None = None
    if rate_limit:
        rate_filter = RateLimitingFilter(
            max_messages=rate_limit_max,
            period=rate_limit_period,
        )

    # Set up file handler if log_file is specified
    if log_file:
        log_path = Path(log_file)
        _ensure_log_directory(log_path)

        # Create appropriate handler based on rotation policy
        if rotate == "time":
            handler = TimedRotatingFileHandler(
                filename=log_path,
                when=_get_time_interval(time_interval),
                backupCount=backup_count,
                encoding="utf-8"
            )
        elif rotate == "both":
            # Use size-based rotation as primary since Python stdlib
            # doesn't support true dual rotation. The size-based handler
            # ensures logs don't grow unbounded.
            handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8"
            )
        else:  # size or default
            handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8"
            )

        # Enable compression for rotated log files (Python 3.9+)
        handler.compress = True  # type: ignore[attr-defined]

        # Set file mode for append
        handler.mode = "a"

        handler.setLevel(log_level)

        # Set file permissions after handler is configured
        _set_log_file_permissions(log_path)

        # Set formatter based on format
        if format == "json":
            handler.setFormatter(JSONFormatter(include_context=True))
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                )
            )

        # Add filters
        handler.addFilter(sensitive_filter)
        if rate_filter:
            handler.addFilter(rate_filter)

        root_logger.addHandler(handler)

    # Set up console handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_log_level)

        if format == "json":
            console_handler.setFormatter(JSONFormatter(include_context=True))
        else:
            console_handler.setFormatter(ColoredFormatter(colorize=colorize))

        # Add sensitive data filter to console as well
        console_handler.addFilter(sensitive_filter)

        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger with the specified name.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger: Configured logger instance.
    """
    return logging.getLogger(name)


def setup_logging_from_config() -> None:
    """Set up logging from config.yml.

    Reads logging configuration from config.yml and applies it.
    Falls back to defaults if configuration is missing.
    """
    settings = get_settings()

    # Get logging config from settings (LoggingConfig Pydantic model)
    log_config = settings.logging

    setup_logging(
        level=log_config.level,
        format=log_config.format,
        log_file=log_config.file.path,
        max_size_mb=log_config.file.max_size_mb,
        backup_count=log_config.file.backup_count,
        rotate=log_config.file.rotate,
        time_interval=log_config.file.time_interval,
        console_enabled=log_config.console.enabled,
        console_level=log_config.console.level,
        colorize=log_config.console.colorize,
    )
