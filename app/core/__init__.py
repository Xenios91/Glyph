"""Core module for Glyph application.

This module provides core functionality including:
- lifespan: Application lifespan events
- rate_limiter: Rate limiting configuration (slowapi)
- middleware: Custom ASGI middleware (CSP, request size, cached static files)
- correlation_bridge: Correlation ID bridge for asgi-correlation-id

Import from the submodules directly (e.g. ``app.core.lifespan``).
"""
