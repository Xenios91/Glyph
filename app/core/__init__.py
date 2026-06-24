"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- rate_limiter: Rate limiting configuration (slowapi)
"""

from app.core.lifespan import lifespan
from app.core.rate_limiter import LOGIN_LIMIT, PASSWORD_CHANGE_LIMIT, REFRESH_LIMIT, REGISTER_LIMIT, limiter

__all__ = [
    "LOGIN_LIMIT",
    "PASSWORD_CHANGE_LIMIT",
    "REFRESH_LIMIT",
    "REGISTER_LIMIT",
    "lifespan",
    "limiter",
]
