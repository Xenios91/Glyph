"""Logging utilities for Glyph application.

This module provides decorators built on top of loguru's logger.catch()
for consistent error handling across the codebase.

Key features:
- catch_http_exception: Decorator that logs exceptions and raises HTTPException
"""

import inspect
from functools import wraps
from typing import TypeVar, Callable, ParamSpec, cast

from fastapi import HTTPException
from loguru import logger

from app.utils.responses import create_error_response

# Type variables for preserving function signatures through the decorator
_R = TypeVar("_R")
_P = ParamSpec("_P")


def catch_http_exception(
    status_code: int = 500,
    error_code: str = "INTERNAL_ERROR",
    message: str | None = None
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Decorator that catches exceptions, logs them with logger.exception(),
    and raises an HTTPException.

    Based on loguru's logger.catch() pattern from the documentation.
    Use this to simplify try/except blocks in endpoint functions.

    Note: This uses explicit try/except rather than @logger.catch() because
    we need to transform the exception type (to HTTPException), which requires
    both logging AND re-raising a different exception type.

    Usage:
        @catch_http_exception(status_code=400, error_code="PREDICTION_ERROR")
        async def predict(request: Request):
            # No try/except needed - exceptions are caught, logged, and converted
            result = do_prediction()
            return result

    Args:
        status_code: HTTP status code for the exception.
        error_code: Error code identifier for the response.
        message: Custom log message. If None, defaults to "Error in {function_name}".

    Returns:
        Decorated function with preserved signature.
    """
    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        log_msg = message or f"Error in {func.__name__}"

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                try:
                    return await func(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.exception(log_msg)
                    raise HTTPException(
                        status_code=status_code,
                        detail=create_error_response(
                            error_code=error_code,
                            error_message=str(exc)).model_dump()) from exc
            return cast(Callable[_P, _R], async_wrapper)
        else:
            @wraps(func)
            def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                try:
                    return func(*args, **kwargs)
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.exception(log_msg)
                    raise HTTPException(
                        status_code=status_code,
                        detail=create_error_response(
                            error_code=error_code,
                            error_message=str(exc)).model_dump()) from exc
            return cast(Callable[_P, _R], sync_wrapper)

    return decorator
