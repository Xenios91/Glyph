"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- request_tracing: Request ID tracing middleware
"""

from app.core.lifespan import lifespan
from app.core.request_tracing import RequestIDMiddleware, get_request_id_from_scope

__all__ = [
    "lifespan",
    "RequestIDMiddleware",
    "get_request_id_from_scope",
]
