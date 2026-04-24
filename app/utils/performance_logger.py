"""Performance logging utilities for Glyph application.

This module provides decorators and context managers for timing
and logging the performance of functions and code blocks.
"""

import time
import logging
from functools import wraps
from timeit import default_timer as timer
from typing import Any, Callable

from app.utils.logging_config import get_logger
from app.utils.request_context import get_request_context


logger = get_logger(__name__)


class PerformanceTimer:
    """Context manager for timing code blocks.
    
    Usage:
        with PerformanceTimer("operation_name") as perf_timer:
            # Code to time
            result = expensive_operation()
        
        print(f"Elapsed: {perf_timer.elapsed:.3f}s")
    """
    
    def __init__(self, name: str, logger: logging.Logger | None = None,
                 log_level: int = logging.INFO, unit: str = "seconds"):
        """Initialize the performance timer.
        
        Args:
            name: Name of the operation being timed.
            logger: Logger to use for logging. If None, uses module logger.
            log_level: Log level for the performance message.
            unit: Time unit for logging ("seconds", "milliseconds", "microseconds").
        """
        self.name = name
        self.logger = logger or get_logger(__name__)
        self.log_level = log_level
        self.unit = unit
        self.start_time: float = 0
        self.end_time: float = 0
        self.elapsed: float = 0
    
    def __enter__(self) -> "PerformanceTimer":
        """Start timing."""
        self.start_time = timer()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and log the result."""
        self.end_time = timer()
        self.elapsed = self.end_time - self.start_time
        
        # Format elapsed time based on unit
        if self.unit == "milliseconds":
            elapsed_display = self.elapsed * 1000
            unit_str = "ms"
        elif self.unit == "microseconds":
            elapsed_display = self.elapsed * 1_000_000
            unit_str = "μs"
        else:
            elapsed_display = self.elapsed
            unit_str = "s"
        
        # Get request context
        ctx = get_request_context()
        
        # Log performance
        log_message = f"Performance: {self.name} completed in {elapsed_display:.3f}{unit_str}"
        
        if ctx.request_id:
            log_message += f" (request_id={ctx.request_id})"
        
        self.logger.log(self.log_level, log_message)
    
    def get_elapsed(self) -> float:
        """Get the elapsed time in seconds.
        
        Returns:
            Elapsed time in seconds.
        """
        if self.end_time:
            return self.elapsed
        return timer() - self.start_time


def log_performance(
    log_level: int = logging.INFO,
    unit: str = "seconds",
    logger: logging.Logger | None = None
) -> Callable:
    """Decorator to log function execution time.
    
    Usage:
        @log_performance
        def process_data(data):
            ...
        
        @log_performance(log_level=logging.DEBUG, unit="milliseconds")
        def fast_operation():
            ...
    
    Args:
        log_level: Log level for the performance message.
        unit: Time unit for logging ("seconds", "milliseconds", "microseconds").
        logger: Logger to use. If None, creates a logger for the decorated function.
        
    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_logger = logger or logging.getLogger(func.__module__)
            
            with PerformanceTimer(
                name=func.__name__,
                logger=func_logger,
                log_level=log_level,
                unit=unit
            ):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_step_performance(step_name: str,
                        log_level: int = logging.INFO,
                        unit: str = "seconds",
                        logger: logging.Logger | None = None) -> Callable:
    """Decorator for logging pipeline step performance.
    
    Usage:
        @log_step_performance("data_validation")
        def validate_data(data):
            ...
    
    Args:
        step_name: Name of the pipeline step.
        log_level: Log level for the performance message.
        unit: Time unit for logging ("seconds", "milliseconds", "microseconds").
        logger: Logger to use. If None, creates a logger for the decorated function.
        
    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_logger = logger or logging.getLogger(func.__module__)
            
            with PerformanceTimer(
                name=f"{step_name} ({func.__name__})",
                logger=func_logger,
                log_level=log_level,
                unit=unit
            ):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class PerformanceMetrics:
    """Collect and aggregate performance metrics.
    
    Usage:
        metrics = PerformanceMetrics()
        
        with metrics.timer("step1"):
            step1()
        
        with metrics.timer("step2"):
            step2()
        
        metrics.log_summary()
    """
    
    def __init__(self, name: str = "metrics",
                 logger: logging.Logger | None = None):
        """Initialize performance metrics collector.
        
        Args:
            name: Name for the metrics collection.
            logger: Logger to use for logging.
        """
        self.name = name
        self.logger = logger or get_logger(__name__)
        self.timings: dict[str, float] = {}
        self._current_timer: PerformanceTimer | None = None
    
    def timer(self, operation_name: str) -> "_MetricsTimer":
        """Create a timer for an operation.
        
        Args:
            operation_name: Name of the operation.
            
        Returns:
            PerformanceTimer context manager.
        """
        return _MetricsTimer(self, operation_name)
    
    def log_summary(self, log_level: int = logging.INFO) -> None:
        """Log a summary of all collected timings.
        
        Args:
            log_level: Log level for the summary.
        """
        if not self.timings:
            return
        
        ctx = get_request_context()
        request_info = f" (request_id={ctx.request_id})" if ctx.request_id else ""
        
        summary_parts = [f"Performance summary for {self.name}{request_info}:"]
        
        for operation, elapsed in sorted(self.timings.items()):
            # Auto-select unit based on elapsed time
            if elapsed < 0.001:
                display = f"{elapsed * 1_000_000:.3f}μs"
            elif elapsed < 1:
                display = f"{elapsed * 1000:.3f}ms"
            else:
                display = f"{elapsed:.3f}s"
            
            summary_parts.append(f"  - {operation}: {display}")
        
        total = sum(self.timings.values())
        if total < 0.001:
            total_display = f"{total * 1_000_000:.3f}μs"
        elif total < 1:
            total_display = f"{total * 1000:.3f}ms"
        else:
            total_display = f"{total:.3f}s"
        
        summary_parts.append(f"  - Total: {total_display}")
        
        self.logger.log(log_level, "\n".join(summary_parts))
    
    def get_timings(self) -> dict[str, float]:
        """Get all collected timings.
        
        Returns:
            Dictionary mapping operation names to elapsed times in seconds.
        """
        return self.timings.copy()
    
    def reset(self) -> None:
        """Reset all collected timings."""
        self.timings.clear()


class _MetricsTimer:
    """Internal timer wrapper for PerformanceMetrics."""
    
    def __init__(self, metrics: "PerformanceMetrics", operation_name: str):
        self.metrics = metrics
        self.operation_name = operation_name
        self.start_time: float = 0
        self.elapsed: float = 0
    
    def __enter__(self) -> "_MetricsTimer":
        self.start_time = timer()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        end_time = timer()
        self.elapsed = end_time - self.start_time
        self.metrics.timings[self.operation_name] = self.elapsed
