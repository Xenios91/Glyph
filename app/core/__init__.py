"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- rate_limiter: Rate limiting configuration (slowapi)
"""

from app.core.lifespan import lifespan
from app.core.rate_limiter import limiter, LOGIN_LIMIT, REGISTER_LIMIT, PASSWORD_CHANGE_LIMIT, REFRESH_LIMIT

__all__ = [
    "lifespan",
    "limiter",
    "LOGIN_LIMIT",
    "REGISTER_LIMIT",
    "PASSWORD_CHANGE_LIMIT",
    "REFRESH_LIMIT",
]
