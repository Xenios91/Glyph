"""Centralized logging configuration for Glyph application.

This module provides:
- Centralized logging setup from config.yml
- JSON and text formatters for structured logging
- Log rotation with size and time-based policies
- Request context support for tracing
- Utility functions for getting configured loggers
"""

import json
import logging
import os
import stat
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.utils.request_context import get_request_context, set_request_context, clear_request_context


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.
    
    Formats log records as JSON with standard fields:
    - timestamp: ISO 8601 format with timezone
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
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        extra_data = getattr(record, 'extra_data', None)
        if extra_data:
            log_data["extra"] = extra_data
        
        # Add standard extra fields from record
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
        
        # Format with colors
        formatted = super().format(record)
        # Replace levelname with colored version
        formatted = formatted.replace(
            f" {levelname} ",
            f" {color}{levelname}{reset} "
        )
        
        return formatted


def _ensure_log_directory(log_path: Path) -> None:
    """Ensure the log directory exists.
    
    Args:
        log_path: Path to the log file.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)


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
) -> None:
    """Set up logging configuration.
    
    This function configures logging with:
    - File handler with rotation
    - Console handler with optional colors
    - JSON or text formatting
    
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
    """
    # Get log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    console_log_level = getattr(logging, console_level.upper(), logging.INFO)
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
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
            # Use RotatingFileHandler with size limit
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
        # Note: 'compress' attribute exists on BaseRotatingHandler but type stubs may not reflect it
        handler.compress = True  # type: ignore[attr-defined]
        
        # Set restrictive file permissions (0o640 = owner read/write, group read)
        handler.mode = "a"
        
        handler.setLevel(log_level)
        
        # Set file permissions after handler opens the file
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
        
        root_logger.addHandler(handler)
    
    # Set up console handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_log_level)
        
        if format == "json":
            console_handler.setFormatter(JSONFormatter(include_context=True))
        else:
            console_handler.setFormatter(ColoredFormatter(colorize=colorize))
        
        root_logger.addHandler(console_handler)


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
        "daily": "d",
        "weekly": "w0",
        "monthly": "D",
    }
    return interval_map.get(interval.lower(), "midnight")


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
