"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- csrf: CSRF protection middleware
- request_tracing: Request ID tracing middleware
"""

from app.core.lifespan import lifespan
from app.core.csrf import CSRFMiddleware
from app.core.request_tracing import RequestIDMiddleware, get_request_id_from_scope

__all__ = [
    "lifespan",
    "CSRFMiddleware",
    "RequestIDMiddleware",
    "get_request_id_from_scope",
]
