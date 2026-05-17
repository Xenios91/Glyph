"""Centralized logging configuration using loguru.

Uses a patcher for request context (async-safe via ContextVars) and
enqueue=True for the file handler (thread-safe for background tasks).
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from app.config.settings import get_settings
from app.utils.request_context import get_request_context


class SensitiveDataPatcher:
    """Redacts sensitive data (passwords, tokens, API keys) from log messages."""

    SENSITIVE_PATTERNS: list[tuple[str, str | Callable[[re.Match[str]], str]]] = [
        (r'(?i)bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED]'),
        (r'(?i)(sqlite|postgresql|mysql|mongodb|redis)(\+[\w]+)?://\S+', '[CONNECTION_STRING_REDACTED]'),
        (r'(?i)(?:^|[\s,;|])((?:token|secret|password|passwd|pwd)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0) or "")),
        (r'(?i)(?:^|[\s,;|])((?:api[_-]?key|apikey)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0) or "")),
        (r'(?i)(?:^|[\s,;|])((?:secret_key|jwt_secret|oauth_secret)\s*[=:]\s*\S+)', lambda m: re.sub(r'(\S+)$', '[REDACTED]', m.group(0) or "")),
        (r'(?i)(password|token|secret)[^@]*@[A-Za-z0-9\.-]+\.[A-Za-z]{2,}', '[REDACTED]'),
    ]

    def __init__(self) -> None:
        self._compiled: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [(re.compile(p), r) for p, r in self.SENSITIVE_PATTERNS]

    def __call__(self, record: dict[str, Any]) -> None:
        """Redact sensitive data from the record's message."""
        if isinstance(record.get("message"), str):
            record["message"] = self.redact(record["message"])

    def redact(self, message: str) -> str:
        """Redact sensitive patterns from a message string."""
        msg = message
        for pattern, replacement in self._compiled:
            msg = pattern.sub(replacement, msg)
        return msg


def create_module_level_filter(module_levels: dict[str, str]) -> Callable[[dict[str, Any]], bool]:
    """Create a filter for per-module log level overrides."""
    level_map: dict[str, int] = {}
    for module_name, level_name in module_levels.items():
        try:
            level_map[module_name] = logger.level(level_name.upper()).no
        except ValueError:
            level_map[module_name] = logger.level("INFO").no

    def filter_func(record: dict[str, Any]) -> bool:
        name: str = record.get("name", "")
        record_level: int = record["level"].no
        for module, min_level in level_map.items():
            if name.startswith(module):
                return record_level >= min_level
        return True

    return filter_func


def _loguru_patcher(sensitive: SensitiveDataPatcher) -> Callable[[dict[str, Any]], None]:
    """Create the loguru patcher for sensitive data redaction and request context."""
    def patcher(record: dict[str, Any]) -> None:
        sensitive(record)
        ctx = get_request_context()
        extra: dict[str, Any] = record["extra"]
        if ctx.request_id:
            extra["request_id"] = ctx.request_id
        if ctx.user_id is not None:
            extra["user_id"] = ctx.user_id
        if ctx.username:
            extra["username"] = ctx.username
        if ctx.task_id:
            extra["task_id"] = ctx.task_id

    return patcher


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
    """Set up logging using loguru's configure() method."""
    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE'}
    if level.upper() not in valid_levels:
        raise ValueError(f"Invalid log level: '{level}'. Must be one of: {', '.join(sorted(valid_levels))}")
    if console_level.upper() not in valid_levels:
        raise ValueError(f"Invalid console log level: '{console_level}'. Must be one of: {', '.join(sorted(valid_levels))}")

    combined_filter = create_module_level_filter(module_levels) if module_levels else None

    sensitive_patcher = SensitiveDataPatcher()
    patcher: Callable[[dict[str, Any]], None] = _loguru_patcher(sensitive_patcher)

    def file_opener(file: str, flags: int) -> int:
        return os.open(file, flags, 0o600)

    handlers: list[dict[str, Any]] = []

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

    diagnose_env = os.environ.get("LOGURU_DIAGNOSE")
    diagnose = diagnose_env.upper() != "NO" if diagnose_env is not None else False

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
