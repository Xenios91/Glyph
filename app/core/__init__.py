"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- rate_limiter: Rate limiting configuration (slowapi)
- middleware: Custom ASGI middleware (CSP, request size, cached static files)
"""

from app.core.lifespan import lifespan
from app.core.middleware import CSPMiddleware, CachedStaticFiles, RequestBodyTooLarge, RequestSizeMiddleware
from app.core.rate_limiter import LOGIN_LIMIT, PASSWORD_CHANGE_LIMIT, REFRESH_LIMIT, REGISTER_LIMIT, limiter

__all__ = [
    "CSPMiddleware",
    "CachedStaticFiles",
    "LOGIN_LIMIT",
    "PASSWORD_CHANGE_LIMIT",
    "REFRESH_LIMIT",
    "REGISTER_LIMIT",
    "RequestBodyTooLarge",
    "RequestSizeMiddleware",
    "lifespan",
    "limiter",
]
