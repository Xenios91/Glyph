"""Centralized logging configuration for Glyph application.

This module provides:
- Centralized logging setup from config.yml
- JSON and text formatters for structured logging
- Log rotation with size and time-based policies
- Request context support for tracing
- Sensitive data redaction filter
- Rate limiting filter to prevent log spam
- Async logging handler for non-blocking I/O
- Log sampling filter for high-volume scenarios
- Logging best practice validation filter
- Utility functions for getting configured loggers
- Startup/shutdown health summary logging
"""

import asyncio
import json
import logging
import os
import random
import re
import stat
import sys
import threading
import time
from collections import defaultdict, deque
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
        # Database connection strings
        (r'(?i)(sqlite|postgresql|mysql|mongodb|redis)(\+[\w]+)?://\S+', '[CONNECTION_STRING_REDACTED]'),
        # Generic token assignments — require word boundary to avoid matching mid-word
        (r'(?i)(?:^|[\s,;|])((?:token|secret|password|passwd|pwd)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        # API keys (common prefixes) — require word boundary
        (r'(?i)(?:^|[\s,;|])((?:api[_-]?key|apikey)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        # Generic secrets in environment variable format — require word boundary
        (r'(?i)(?:^|[\s,;|])((?:secret_key|jwt_secret|oauth_secret)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
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
                # Redact individual tuple args that look like sensitive values
                # (value-based matching instead of message-keyword matching)
                # to avoid over-redacting non-sensitive args when the message
                # happens to contain a sensitive keyword.
                sensitive_value_patterns = [
                    r'(?i)^(password|token|secret|api_key|apikey|passwd|pwd)\s*[=:]\s*\S+',
                    r'(?i)^bearer\s+[A-Za-z0-9\-\._~\+\/]+=*',
                    r'(?i)^(sqlite|postgresql|mysql|mongodb|redis)(\+[\w]+)?://\S+',
                ]
                new_args = []
                for v in record.args:
                    if isinstance(v, str) and any(
                        re.match(pattern, v) for pattern in sensitive_value_patterns
                    ):
                        new_args.append('[REDACTED]')
                    else:
                        new_args.append(v)
                record.args = tuple(new_args)

        return True

    def filter_msg(self, message: str) -> str:
        """Redact sensitive data from a string message.

        Args:
            message: The message string to redact.

        Returns:
            The redacted message string.
        """
        new_msg = message
        for pattern, replacement in self._compiled_patterns:
            if callable(replacement):
                new_msg = pattern.sub(replacement, new_msg)
            else:
                new_msg = pattern.sub(replacement, new_msg)
        return new_msg


# Module-level sensitive data filter for components that need standalone redaction
_RATE_LIMIT_SENSITIVE_FILTER = SensitiveDataFilter()


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
        max_keys: int = 1000,
    ):
        """Initialize the rate limiting filter.

        Args:
            max_messages: Maximum number of messages allowed per period.
            period: Time period in seconds.
            key_func: Custom function to generate rate limit keys.
                      Defaults to using logger name + first 50 chars of message.
            max_keys: Maximum number of unique keys to track (memory bound).
        """
        super().__init__()
        self.max_messages = max_messages
        self.period = period
        self.key_func = key_func or self._default_key_func
        self.max_keys = max_keys
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._suppressed: dict[str, int] = defaultdict(int)
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300.0  # 5 minutes

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

    def _cleanup_stale_keys(self, now: float) -> None:
        """Remove stale keys and evict oldest if over memory limit.

        Args:
            now: Current monotonic timestamp.
        """
        cutoff = now - self.period
        # Clean old timestamps and remove empty buckets
        for key in list(self._buckets):
            self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
            if not self._buckets[key]:
                del self._buckets[key]
                self._suppressed.pop(key, None)

        # Evict oldest keys if over limit
        if len(self._buckets) > self.max_keys:
            keys_by_activity = sorted(
                self._buckets.keys(),
                key=lambda k: max(self._buckets[k]) if self._buckets[k] else 0,
            )
            keys_to_remove = keys_by_activity[:len(self._buckets) - self.max_keys]
            for key in keys_to_remove:
                del self._buckets[key]
                self._suppressed.pop(key, None)

    def filter(self, record: logging.LogRecord) -> bool:
        """Check if the log record should be allowed through.

        Args:
            record: The log record to filter.

        Returns:
            True to include the record, False to suppress.
        """
        key = self.key_func(record)
        now = time.monotonic()

        # Periodic cleanup of stale keys
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_stale_keys(now)

        self._cleanup_old_timestamps(key, now)

        # Evict if over key limit
        if len(self._buckets) > self.max_keys:
            self._cleanup_stale_keys(now)

        if len(self._buckets[key]) < self.max_messages:
            self._buckets[key].append(now)
            self._suppressed[key] = 0
            return True

        # Suppress the message but track count
        self._suppressed[key] += 1

        # Every 100 suppressed messages, log a summary using a dedicated logger
        if self._suppressed[key] % 100 == 0:
            # Use a dedicated logger that does not propagate to avoid recursive
            # rate-limit logging and ensure the summary respects the filter chain.
            _rate_limit_logger = logging.getLogger("glyph.rate_limit")
            _rate_limit_logger.propagate = False
            # Apply sensitive data redaction to prevent bypass
            redacted_msg = _RATE_LIMIT_SENSITIVE_FILTER.filter_msg(record.msg[:100])
            _rate_limit_logger.warning(
                "[Rate Limited] %d messages suppressed for: %s",
                self._suppressed[key],
                redacted_msg,
            )

        return False


class JSONFormatter(logging.Formatter):
    """Optimized JSON formatter for structured logging.

    Formats log records as JSON with standard fields using lazy context
    evaluation and shorter field names for reduced payload size:
    - t: ISO 8601 timestamp
    - l: Log level
    - logger: Logger name
    - msg: Log message
    - rid: Request ID if available
    - uid: User ID if available
    - user: Username if available
    - tid: Task ID for background tasks if available
    - exc: Exception traceback if present
    - extra: Additional context-specific fields
    """

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context
        # Local reference for faster serialization
        self._json_dumps = json.dumps

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON with lazy context evaluation.

        Args:
            record: The log record to format.

        Returns:
            str: JSON string representation of the log record.
        """
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        log_data: dict[str, Any] = {
            "t": timestamp,
            "l": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Lazy context - only add non-null values
        if self.include_context:
            ctx = get_request_context()
            if ctx.request_id:
                log_data["rid"] = ctx.request_id
            if ctx.user_id is not None:
                log_data["uid"] = ctx.user_id
            if ctx.username:
                log_data["user"] = ctx.username
            if ctx.task_id:
                log_data["tid"] = ctx.task_id

        # Add exception info only if present
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exc"] = self.formatException(record.exc_info)

        # Add stack info only if present
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        # Add extra fields only if present
        extra_data = getattr(record, 'extra_data', None)
        if extra_data:
            log_data["extra"] = extra_data

        # Debug-only fields
        if record.levelno <= logging.DEBUG:
            for field in ('filename', 'funcName', 'lineno', 'pathname', 'threadName'):
                value = getattr(record, field, None)
                if value:
                    log_data[f"_{field}"] = value

        return self._json_dumps(log_data, default=str)


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
        formatted = f"{timestamp} | {color}{levelname:<8}{reset} | {record.name} | {record.getMessage()}"

        # Append exception info if present
        if record.exc_text:
            formatted += f"\n{record.exc_text.rstrip()}"
        if record.stack_info:
            formatted += f"\n{record.stack_info.rstrip()}"

        return formatted


def _ensure_log_directory(log_path: Path) -> None:
    """Ensure the log directory exists and is writable.

    Args:
        log_path: Path to the log file.

    Raises:
        PermissionError: If the directory is not writable.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Verify the directory is writable
    if not os.access(log_path.parent, os.W_OK):
        raise PermissionError(
            f"Log directory is not writable: {log_path.parent}. "
            f"Check permissions and try again."
        )


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
    except OSError as e:
        # Log permission errors to stderr since logging may not be initialized yet
        sys.stderr.write(
            f"[LOGGING WARNING] Failed to set log file permissions for {log_path}: {e}\n"
        )


def _validate_rotation_policy(rotate: str) -> None:
    """Validate the rotation policy value.

    Args:
        rotate: Rotation policy string.

    Raises:
        ValueError: If the rotation policy is not supported.
    """
    valid_policies = {"size", "time"}
    if rotate.lower() not in valid_policies:
        raise ValueError(
            f"Invalid log rotation policy: '{rotate}'. "
            f"Must be one of: {', '.join(sorted(valid_policies))}. "
            f"Note: 'both' is no longer supported. Use 'size' or 'time'."
        )


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


class AsyncLogHandler(logging.Handler):
    """Non-blocking async log handler using a queue.

    Queues log records and processes them asynchronously to avoid
    blocking the event loop during request handling. Uses asyncio.Queue
    for thread-safe operations across concurrent contexts.
    """

    def __init__(
        self,
        target_handler: logging.Handler,
        max_queue_size: int = 1000,
    ):
        """Initialize the async log handler.

        Args:
            target_handler: The handler to forward records to.
            max_queue_size: Maximum number of records to queue.
        """
        super().__init__()
        self.target = target_handler
        self._max_queue_size = max_queue_size
        self._queue: asyncio.Queue[logging.LogRecord] | None = None
        self._sync_queue: deque[logging.LogRecord] = deque(maxlen=max_queue_size)
        self._task: asyncio.Task | None = None
        self._lock = threading.Lock()

    def _get_async_queue(self) -> asyncio.Queue[logging.LogRecord]:
        """Get or create the async queue for the current event loop.

        Thread-safe: uses self._lock to prevent race conditions where
        multiple threads could create separate Queue instances.
        """
        with self._lock:
            if self._queue is None:
                self._queue = asyncio.Queue(maxsize=self._max_queue_size)
            return self._queue

    def emit(self, record: logging.LogRecord) -> None:
        """Queue a log record for async processing.

        Args:
            record: The log record to queue.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop (e.g., during startup/shutdown)
            # Queue and process synchronously
            self._sync_queue.append(record)
            self._process_sync()
            return

        # Schedule enqueue on the running event loop without blocking.
        # run_coroutine_threadsafe is safe here because emit() is called
        # from the logging framework which runs in the same thread as the
        # event loop in FastAPI/uvicorn contexts. The future is fire-and-forget.
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._enqueue_single(record), loop
            )
            # Fire-and-forget: don't wait for result to avoid blocking
        except Exception:
            # Fallback to synchronous processing if scheduling fails
            self._sync_queue.append(record)
            self._process_sync()

    async def _enqueue_single(self, record: logging.LogRecord) -> None:
        """Enqueue a single record and ensure processor task is running.

        Args:
            record: The log record to enqueue.
        """
        q = self._get_async_queue()
        try:
            q.put_nowait(record)
        except asyncio.QueueFull:
            # Queue is full, drop the record to prevent blocking
            # Log the overflow to stderr so it is never silently lost
            # Apply sensitive data redaction to prevent secret exposure
            redacted_msg = _RATE_LIMIT_SENSITIVE_FILTER.filter_msg(
                str(record.msg)[:80]
            )
            sys.stderr.write(
                f"[LOG OVERFLOW] Dropped log record (queue full): {record.name} - {redacted_msg}\n"
            )

        with self._lock:
            if self._task is None or self._task.done():
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._process_queue())

    def _process_sync(self) -> None:
        """Process queued records synchronously (no event loop)."""
        while self._sync_queue:
            record = self._sync_queue.popleft()
            try:
                self.target.emit(record)
            except Exception:
                self.handleError(record)

    async def _process_queue(self) -> None:
        """Process queued records asynchronously.

        Uses a brief grace period after the queue appears empty to catch
        late-arriving records that were enqueued during processing.
        """
        q = self._get_async_queue()
        while True:
            try:
                record = q.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                self.target.emit(record)
            except Exception:
                self.handleError(record)
            await asyncio.sleep(0)  # Yield to event loop

        # Brief grace period to catch late-arriving records
        await asyncio.sleep(0.01)
        while True:
            try:
                record = q.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                self.target.emit(record)
            except Exception:
                self.handleError(record)

    async def _flush_async_queue(self) -> None:
        """Flush the async queue by processing all pending records."""
        async_queue = self._queue
        if async_queue is None:
            return
        while not async_queue.empty():
            try:
                record = async_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                self.target.emit(record)
            except Exception:
                self.handleError(record)
            await asyncio.sleep(0)

    def flush(self) -> None:
        """Flush all queued records synchronously."""
        self._process_sync()
        # Schedule async queue flush without blocking
        if self._queue is not None:
            try:
                loop = asyncio.get_running_loop()
                # Fire-and-forget: schedule flush on the event loop
                asyncio.run_coroutine_threadsafe(
                    self._flush_async_queue(), loop
                )
            except (RuntimeError, AssertionError):
                # No running loop or can't schedule, skip async flush
                pass

    def close(self) -> None:
        """Close the handler and flush remaining records."""
        self.flush()
        self.target.close()
        super().close()


class SamplingFilter(logging.Filter):
    """Sample log messages to reduce volume in high-traffic scenarios.

    Allows a configurable percentage of log messages through,
    useful for reducing log volume in production.
    """

    def __init__(self, sample_rate: float = 1.0):
        """Initialize the sampling filter.

        Args:
            sample_rate: Fraction of messages to allow (0.0 to 1.0).
                         1.0 means all messages, 0.1 means 10%.
        """
        super().__init__()
        self.sample_rate = max(0.0, min(1.0, sample_rate))

    def filter(self, record: logging.LogRecord) -> bool:
        """Determine if the record should be logged based on sample rate.

        Uses random sampling for statistically representative results
        instead of deterministic counter-based sampling.

        Args:
            record: The log record to filter.

        Returns:
            True to include the record, False to suppress.
        """
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
        return random.random() < self.sample_rate


class LoggingBestPracticeFilter(logging.Filter):
    """Development-only filter that validates logging best practices.

    Warns about common anti-patterns like string concatenation in log messages
    or missing exception info when logging errors.
    """

    def __init__(self, enabled: bool = False, max_warnings: int = 100):
        """Initialize the best practice filter.

        Args:
            enabled: Whether to enable validation (default: False for production).
            max_warnings: Maximum number of unique warnings to track (default: 100).
                         Stops tracking after this limit to prevent memory leaks.
        """
        super().__init__()
        self.enabled = enabled
        self.max_warnings = max_warnings
        self._warnings: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        """Validate the log record against best practices.

        Args:
            record: The log record to validate.

        Returns:
            True to always include the record (this filter only warns).
        """
        if not self.enabled:
            return True

        # Stop tracking warnings after reaching the memory limit
        if len(self._warnings) >= self.max_warnings:
            return True

        # Check for string formatting anti-patterns in message
        if isinstance(record.msg, str):
            # Warn about f-string remnants (should use % formatting)
            # Only flag if braces look like unformatted placeholders (e.g., {variable})
            # but not JSON-like braces (e.g., {"key": "value"}) or literal braces
            if re.search(r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', record.msg):
                key = f"unformatted_braces:{record.name}:{record.msg[:50]}"
                if key not in self._warnings:
                    self._warnings.add(key)
                    sys.stderr.write(
                        f"[LOGGING WARNING] Potential unformatted braces in log message "
                        f"in {record.name}. Use % formatting instead of f-strings.\n"
                    )

            # Warn about error logs without exception info
            if record.levelno == logging.ERROR and not record.exc_info:
                key = f"error_no_exc:{record.name}:{record.msg[:50]}"
                if key not in self._warnings:
                    self._warnings.add(key)
                    sys.stderr.write(
                        f"[LOGGING WARNING] Error log without exc_info in {record.name}. "
                        f"Consider using logger.exception() or exc_info=True.\n"
                    )

        return True


def log_startup_summary() -> None:
    """Log a startup summary with logging configuration details.

    Outputs a structured log message showing the current logging
    configuration, active handlers, and system state.
    """
    root_logger = logging.getLogger()
    logger = get_logger("glyph.startup")

    handler_names = [type(h).__name__ for h in root_logger.handlers]

    logger.info(
        "Logging initialized",
        extra={"extra_data": {
            "event": "startup",
            "log_level": logging.getLevelName(root_logger.level),
            "handlers": handler_names,
            "handler_count": len(handler_names),
        }}
    )


def log_shutdown_summary() -> None:
    """Log a shutdown summary with logging configuration details.

    Outputs a structured log message showing the current logging
    configuration and active handlers at shutdown time.
    """
    root_logger = logging.getLogger()
    logger = get_logger("glyph.shutdown")

    handler_names = [type(h).__name__ for h in root_logger.handlers]

    logger.info(
        "Logging shutdown summary",
        extra={"extra_data": {
            "event": "shutdown",
            "log_level": logging.getLevelName(root_logger.level),
            "handlers": handler_names,
            "handler_count": len(handler_names),
        }}
    )


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
    rate_limit_max_keys: int = 1000,
    module_levels: dict[str, str] | None = None,
    async_logging: bool = False,
    async_max_queue: int = 1000,
    sampling_enabled: bool = False,
    sampling_rate: float = 1.0,
    best_practice_filter: bool = False,
) -> None:
    """Set up logging configuration.

    This function configures logging with:
    - File handler with rotation
    - Console handler with optional colors
    - JSON or text formatting
    - Sensitive data redaction
    - Optional rate limiting with memory bounds
    - Per-module log level overrides
    - Async logging support
    - Log sampling for high-volume scenarios
    - Best practice validation filter

    Args:
        level: Log level for file handler (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format: Log format ("json" or "text").
        log_file: Path to log file. Set to None to disable file logging.
        max_size_mb: Maximum log file size in MB before rotation.
        backup_count: Number of backup files to keep.
        rotate: Rotation policy ("size" or "time").
        time_interval: Time interval for time-based rotation.
        console_enabled: Whether to enable console logging.
        console_level: Log level for console handler.
        colorize: Whether to colorize console output.
        rate_limit: Whether to enable rate limiting.
        rate_limit_max: Maximum messages per period when rate limiting enabled.
        rate_limit_period: Time period in seconds for rate limiting.
        rate_limit_max_keys: Maximum unique keys to track in rate limiter.
        module_levels: Dict mapping module names to log level overrides.
        async_logging: Whether to wrap handlers in AsyncLogHandler.
        async_max_queue: Maximum queue size for async logging.
        sampling_enabled: Whether to enable log sampling.
        sampling_rate: Fraction of messages to allow (0.0 to 1.0).
        best_practice_filter: Whether to enable logging best practice validation.
    """
    # Validate and get log levels
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'NOTSET'}
    if level.upper() not in valid_levels:
        raise ValueError(
            f"Invalid log level: '{level}'. Must be one of: {', '.join(sorted(valid_levels))}"
        )
    if console_level.upper() not in valid_levels:
        raise ValueError(
            f"Invalid console log level: '{console_level}'. Must be one of: {', '.join(sorted(valid_levels))}"
        )
    log_level = getattr(logging, level.upper(), logging.INFO)
    console_log_level = getattr(logging, console_level.upper(), logging.INFO)

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(max(log_level, console_log_level) if console_enabled else log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Apply per-module log level overrides
    if module_levels:
        for module_name, module_level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(getattr(logging, module_level.upper(), logging.INFO))

    # Create shared filters
    sensitive_filter = SensitiveDataFilter()

    rate_filter: RateLimitingFilter | None = None
    if rate_limit:
        rate_filter = RateLimitingFilter(
            max_messages=rate_limit_max,
            period=rate_limit_period,
            max_keys=rate_limit_max_keys,
        )

    sampling_filter: SamplingFilter | None = None
    if sampling_enabled:
        sampling_filter = SamplingFilter(sample_rate=sampling_rate)

    best_practice: LoggingBestPracticeFilter | None = None
    if best_practice_filter:
        best_practice = LoggingBestPracticeFilter(enabled=True)

    # Build base handler
    base_handler: logging.Handler | None = None

    # Validate rotation policy
    _validate_rotation_policy(rotate)

    # Set up file handler if log_file is specified
    if log_file:
        log_path = Path(log_file)
        _ensure_log_directory(log_path)

        # Create appropriate handler based on rotation policy
        if rotate == "time":
            base_handler = TimedRotatingFileHandler(
                filename=log_path,
                when=_get_time_interval(time_interval),
                backupCount=backup_count,
                encoding="utf-8"
            )
        else:  # size or default
            base_handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8"
            )

        # Enable compression for rotated log files (Python 3.9+)
        if hasattr(base_handler, 'compress'):
            base_handler.compress = True  # type: ignore[attr-defined]

        # Set file mode for append
        base_handler.mode = "a"
        base_handler.setLevel(log_level)

        # Set file permissions after handler is configured
        _set_log_file_permissions(log_path)

    # Wrap in async handler if enabled
    file_handler: logging.Handler = base_handler if base_handler else logging.NullHandler()
    if async_logging and base_handler:
        file_handler = AsyncLogHandler(target_handler=base_handler, max_queue_size=async_max_queue)
        file_handler.setLevel(log_level)

    # Set formatter
    if format == "json":
        file_handler.setFormatter(JSONFormatter(include_context=True))
    else:
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )

    # Add filters to file handler
    file_handler.addFilter(sensitive_filter)
    if rate_filter:
        file_handler.addFilter(rate_filter)
    if sampling_filter:
        file_handler.addFilter(sampling_filter)
    if best_practice:
        file_handler.addFilter(best_practice)

    if log_file:
        root_logger.addHandler(file_handler)

    # Set up console handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_log_level)

        if format == "json":
            console_handler.setFormatter(JSONFormatter(include_context=True))
        else:
            console_handler.setFormatter(ColoredFormatter(colorize=colorize))

        console_handler.addFilter(sensitive_filter)
        if rate_filter:
            console_handler.addFilter(rate_filter)
        if sampling_filter:
            console_handler.addFilter(sampling_filter)
        if best_practice:
            console_handler.addFilter(best_practice)

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

    # Access Pydantic model attributes directly (not .get())
    rate_limit_config = getattr(log_config, 'rate_limit', None)
    rate_limit_enabled = rate_limit_config.enabled if rate_limit_config else False
    rate_limit_max = rate_limit_config.max_messages if rate_limit_config else 10
    rate_limit_period = rate_limit_config.period if rate_limit_config else 60.0
    rate_limit_max_keys = rate_limit_config.max_keys if rate_limit_config else 1000

    # Build module levels
    module_levels = getattr(log_config, 'module_levels', None)

    # Build async logging config
    async_config = getattr(log_config, 'async_logging', None)
    async_enabled = async_config.enabled if async_config else False
    async_max_queue = async_config.max_queue_size if async_config else 1000

    # Build sampling config
    sampling_config = getattr(log_config, 'sampling', None)
    sampling_enabled = sampling_config.enabled if sampling_config else False
    sampling_rate = sampling_config.rate if sampling_config else 1.0

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
        rate_limit=rate_limit_enabled,
        rate_limit_max=rate_limit_max,
        rate_limit_period=rate_limit_period,
        rate_limit_max_keys=rate_limit_max_keys,
        module_levels=dict(module_levels) if module_levels else None,
        async_logging=async_enabled,
        async_max_queue=async_max_queue,
        sampling_enabled=sampling_enabled,
        sampling_rate=sampling_rate,
        best_practice_filter=os.environ.get("GLYPH_LOG_BEST_PRACTICE", "false").lower() == "true",
    )
