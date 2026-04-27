"""Centralized logging configuration for Glyph application using loguru.

This module provides:
- Centralized logging setup from config.yml using logger.configure()
- Log rotation with size and time-based policies
- Request context support for tracing via ContextVars (async-safe)
- Sensitive data redaction via patcher
- Per-module log level overrides
- Native JSON serialization using loguru's serialize=True parameter
- Enqueued file handler for thread safety

Key design decisions:
- Uses a patcher (not logger.contextualize()) for request context because
  contextualize() relies on thread-local storage which doesn't work with
  async/await. The patcher reads from ContextVars which are async-safe.
- Uses enqueue=True for the file handler to avoid concurrent write issues
  when background threads log simultaneously with request handlers.
"""

import os
import re
import sys
from pathlib import Path

from loguru import logger

from app.config.settings import get_settings
from app.utils.request_context import get_request_context


# =============================================================================
# Sensitive Data Redaction Patcher
# =============================================================================

class SensitiveDataPatcher:
    """Redacts sensitive data from log messages (passwords, tokens, API keys).

    Used as a loguru patcher that mutates the record's message field to remove
    sensitive patterns before the message is written to any handler.
    """

    SENSITIVE_PATTERNS = [
        (r'(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED]'),
        (r'(?i)(sqlite|postgresql|mysql|mongodb|redis)(\+[\w]+)?://\S+', '[CONNECTION_STRING_REDACTED]'),
        (r'(?i)(?:^|[\s,;|])((?:token|secret|password|passwd|pwd)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        (r'(?i)(?:^|[\s,;|])((?:api[_-]?key|apikey)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        (r'(?i)(?:^|[\s,;|])((?:secret_key|jwt_secret|oauth_secret)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0))),
        (r'(?i)(password|token|secret)[^@]*@[A-Za-z0-9\.-]+\.[A-Za-z]{2,}', '[REDACTED]'),
    ]

    def __init__(self):
        self._compiled = [(re.compile(p), r) for p, r in self.SENSITIVE_PATTERNS]

    def __call__(self, record: dict) -> None:
        """Redact sensitive data from the record's message."""
        if isinstance(record.get("message"), str):
            record["message"] = self.redact(record["message"])

    def redact(self, message: str) -> str:
        """Redact sensitive patterns from a message string."""
        msg = message
        for pattern, replacement in self._compiled:
            msg = pattern.sub(replacement, msg)
        return msg


# =============================================================================
# Module Level Filter
# =============================================================================

def create_module_level_filter(module_levels: dict[str, str]):
    """Create a filter function for per-module log level overrides.

    Args:
        module_levels: Dict mapping module name prefixes to minimum log levels.

    Returns:
        Filter function that returns False for records below the module minimum.
    """
    level_map = {}
    for module_name, level_name in module_levels.items():
        try:
            level_map[module_name] = logger.level(level_name.upper()).no
        except ValueError:
            level_map[module_name] = logger.level("INFO").no

    def filter_func(record: dict) -> bool:
        name = record.get("name", "")
        record_level = record["level"].no
        for module, min_level in level_map.items():
            if name.startswith(module):
                return record_level >= min_level
        return True

    return filter_func


# =============================================================================
# Loguru Patcher (Sensitive Data + Request Context)
# =============================================================================

def _loguru_patcher(sensitive: SensitiveDataPatcher):
    """Create the loguru patcher for sensitive data redaction and request context.

    This patcher is applied to every log record before it reaches any handler.
    It performs two tasks:
    1. Redacts sensitive data (passwords, tokens, API keys) from the message.
    2. Injects request context (request_id, user_id, username, task_id) from
       ContextVars into the record's extra dict for async-safe tracing.

    Args:
        sensitive: The sensitive data patcher instance.

    Returns:
        Patcher function that applies both redaction and context injection.
    """
    def patcher(record: dict) -> None:  # type: ignore[assignment]
        sensitive(record)
        ctx = get_request_context()
        extra = record["extra"]
        if ctx.request_id:
            extra["request_id"] = ctx.request_id
        if ctx.user_id is not None:
            extra["user_id"] = ctx.user_id
        if ctx.username:
            extra["username"] = ctx.username
        if ctx.task_id:
            extra["task_id"] = ctx.task_id

    return patcher


# =============================================================================
# Main Setup
# =============================================================================

def setup_logging(
    level: str = "INFO",
    format: str = "json",
    log_file: str | None = "logs/glyph.log",
    rotation: str = "50 MB",
    retention: str = "10 days",
    console_enabled: bool = True,
    console_level: str = "INFO",
    colorize: bool = True,
    module_levels: dict[str, str] | None = None,
    diagnose: bool = False,
    enqueue: bool = True) -> None:
    """Set up logging using loguru's configure() method.

    Args:
        level: Log level for file handler.
        format: Log format ("json" or "text").
        log_file: Path to log file. None disables file logging.
        rotation: Loguru rotation string (e.g., "50 MB", "00:00", "1 week").
        retention: Loguru retention string (e.g., "10 days", "1 month").
        console_enabled: Whether to enable console logging.
        console_level: Log level for console handler.
        colorize: Whether to colorize console output.
        module_levels: Dict mapping module names to log level overrides.
        diagnose: Whether to enable variable diagnosis in exceptions.
        enqueue: Whether to use enqueued logging for file handler (thread-safe).
    """
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE'}
    if level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: '{level}'. Must be one of: {', '.join(sorted(valid_levels))}")
    if console_level.upper() not in valid_levels:
        raise ValueError(f"Invalid console log level: '{console_level}'. Must be one of: {', '.join(sorted(valid_levels))}")

    # Build filter (module levels only)
    combined_filter = create_module_level_filter(module_levels) if module_levels else None

    # Create patcher for sensitive data redaction + request context injection
    sensitive_patcher = SensitiveDataPatcher()
    patcher = _loguru_patcher(sensitive_patcher)

    # File opener for secure permissions (owner rw only - logs may contain sensitive data)
    def file_opener(file: str, flags: int) -> int:
        return os.open(file, flags, 0o600)

    handlers = []

    # File handler with rotation and compression
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(log_path.parent, os.W_OK):
            raise PermissionError(f"Log directory is not writable: {log_path.parent}")

        file_handler_config = {
            "sink": log_file,
            "level": level.upper(),
            "rotation": rotation,
            "retention": retention,
            "compression": "zip",
            "filter": combined_filter,
            "enqueue": enqueue,
            "opener": file_opener,
            "backtrace": True,
            "diagnose": diagnose,
            "colorize": False,
            "encoding": "utf-8",
        }

        if format == "json":
            file_handler_config["serialize"] = True
        else:
            file_handler_config["format"] = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name} | {message}\n{exception}"

        handlers.append(file_handler_config)

    # Console handler (uses sys.stderr per loguru convention for log aggregation)
    if console_enabled:
        handlers.append({
            "sink": sys.stderr,
            "level": console_level.upper(),
            "filter": combined_filter,
            "colorize": colorize,
        })

    logger.configure(handlers=handlers, patcher=patcher)  # type: ignore[arg-type]


def setup_logging_from_config() -> None:
    """Set up logging from config.yml."""
    settings = get_settings()
    log_config = settings.logging

    # LOGURU_DIAGNOSE: Enable/disable variable diagnosis in exceptions.
    # Default to False in production for security (prevents credentials in logs).
    diagnose_env = os.environ.get("LOGURU_DIAGNOSE")
    diagnose = diagnose_env.upper() != "NO" if diagnose_env is not None else False

    # LOGURU_ENQUEUE: Enable/disable enqueued logging for file handler.
    # Default to True for thread safety with background tasks.
    enqueue_env = os.environ.get("LOGURU_ENQUEUE")
    enqueue = enqueue_env.upper() != "NO" if enqueue_env is not None else True

    setup_logging(
        level=log_config.level,
        format=log_config.format,
        log_file=log_config.file.path,
        rotation=log_config.file.rotation,
        retention=log_config.file.retention,
        console_enabled=log_config.console.enabled,
        console_level=log_config.console.level,
        colorize=log_config.console.colorize,
        module_levels=dict(log_config.module_levels) if log_config.module_levels else None,
        diagnose=diagnose,
        enqueue=enqueue)
