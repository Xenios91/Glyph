"""Centralized logging configuration for Glyph application using loguru.

This module provides:
- Centralized logging setup from config.yml using logger.configure()
- Log rotation with size and time-based policies
- Request context support for tracing
- Sensitive data redaction via patch
- Per-module log level overrides
- Native JSON serialization using loguru's serialize=True parameter
"""

import os
import re
import sys
from pathlib import Path

from loguru import logger

from app.config.settings import get_settings
from app.utils.request_context import get_request_context


# =============================================================================
# Sensitive Data Redaction
# =============================================================================

class SensitiveDataFilter:
    """Redacts sensitive data from log messages (passwords, tokens, API keys)."""

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

    def __call__(self, record: dict) -> bool:
        if isinstance(record.get("message"), str):
            record["message"] = self.filter_msg(record["message"])
        return True

    def filter_msg(self, message: str) -> str:
        msg = message
        for pattern, replacement in self._compiled:
            if callable(replacement):
                msg = pattern.sub(replacement, msg)
            else:
                msg = pattern.sub(replacement, msg)
        return msg


# =============================================================================
# Module Level Filter
# =============================================================================

def create_module_level_filter(module_levels: dict[str, str]):
    """Create a filter for per-module log level overrides."""
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
# Main Setup
# =============================================================================

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
    module_levels: dict[str, str] | None = None,
    diagnose: bool = False) -> None:
    """Set up logging using loguru's configure() method.

    Args:
        level: Log level for file handler.
        format: Log format ("json" or "text").
        log_file: Path to log file. None disables file logging.
        max_size_mb: Maximum log file size in MB before rotation.
        backup_count: Number of days to retain backup files.
        rotate: Rotation policy ("size" or "time").
        time_interval: Time interval for time-based rotation.
        console_enabled: Whether to enable console logging.
        console_level: Log level for console handler.
        colorize: Whether to colorize console output.
        module_levels: Dict mapping module names to log level overrides.
        diagnose: Whether to enable variable diagnosis in exceptions.
    """
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE'}
    if level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: '{level}'. Must be one of: {', '.join(sorted(valid_levels))}")
    if console_level.upper() not in valid_levels:
        raise ValueError(f"Invalid console log level: '{console_level}'. Must be one of: {', '.join(sorted(valid_levels))}")

    # Build rotation string
    if rotate == "size":
        rotation = f"{max_size_mb} MB"
    else:
        interval_map = {"midnight": "00:00", "daily": "00:00", "weekly": "1 week", "monthly": "1 month"}
        rotation = interval_map.get(time_interval.lower(), "00:00")

    # Build filter (module levels only)
    if module_levels:
        combined_filter = create_module_level_filter(module_levels)
    else:
        combined_filter = None

    # Patcher: sensitive data redaction + request context
    sensitive_filter = SensitiveDataFilter()

    def patcher(record: dict) -> None:  # type: ignore[assignment]
        sensitive_filter(record)
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

    # File opener for permissions (0o640)
    def file_opener(file: str, flags: int) -> int:
        return os.open(file, flags, 0o640)

    handlers = []

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(log_path.parent, os.W_OK):
            raise PermissionError(f"Log directory is not writable: {log_path.parent}")

        if format == "json":
            handlers.append({
                "sink": log_file,
                "level": level.upper(),
                "serialize": True,
                "rotation": rotation,
                "retention": f"{backup_count} days",
                "compression": "zip",
                "filter": combined_filter,
                "enqueue": False,
                "opener": file_opener,
                "backtrace": True,
                "diagnose": diagnose,
                "colorize": False,
                "encoding": "utf-8",
            })
        else:
            handlers.append({
                "sink": log_file,
                "level": level.upper(),
                "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name} | {message}\n{exception}",
                "rotation": rotation,
                "retention": f"{backup_count} days",
                "compression": "zip",
                "filter": combined_filter,
                "enqueue": False,
                "opener": file_opener,
                "backtrace": True,
                "diagnose": diagnose,
                "colorize": False,
                "encoding": "utf-8",
            })

    # Console handler (uses loguru default format)
    if console_enabled:
        handlers.append({
            "sink": sys.stdout,
            "level": console_level.upper(),
            "filter": combined_filter,
            "colorize": colorize,
        })

    logger.configure(handlers=handlers, patcher=patcher)  # type: ignore[arg-type]


def setup_logging_from_config() -> None:
    """Set up logging from config.yml."""
    settings = get_settings()
    log_config = settings.logging

    # LOGURU_DIAGNOSE: Enable/disable variable diagnosis in exceptions
    diagnose_env = os.environ.get("LOGURU_DIAGNOSE")
    diagnose = diagnose_env.upper() != "NO" if diagnose_env is not None else False

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
        module_levels=dict(log_config.module_levels) if log_config.module_levels else None,
        diagnose=diagnose)
