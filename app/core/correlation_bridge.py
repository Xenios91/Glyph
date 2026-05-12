"""Bridge middleware to connect asgi-correlation-id with Glyph request context.

The asgi-correlation-id library stores the correlation ID in its own ContextVar
and also updates the request headers (when update_request_header=True, which is
the default). This middleware reads the correlation ID from the updated request
headers and sets it into the Glyph request context system so that existing code
using get_request_context() continues to work without changes.

Usage:
    app.add_middleware(CorrelationIdBridgeMiddleware)

This middleware should be added after CorrelationIdMiddleware in the stack
so the correlation ID header is already set by the time this runs.
"""

from typing import Any, Callable

from starlette.types import Receive, Send, Scope

from app.utils.request_context import set_request_context, clear_request_context


class CorrelationIdBridgeMiddleware:
    """Bridge middleware that propagates correlation_id to request context.

    This middleware:
    - Reads the correlation ID from request headers (set by CorrelationIdMiddleware)
    - Sets it into the Glyph request context for downstream compatibility
    - Clears the request context after the request completes
    """

    def __init__(self, app: Callable[[Scope, Receive, Send], Any]) -> None:
        """Initialize the bridge middleware.

        Args:
            app: The ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request.

        Args:
            scope: The ASGI scope dictionary.
            receive: Awaitable callable for receiving events.
            send: Awaitable callable for sending events.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Read correlation ID from request headers.
        # CorrelationIdMiddleware (added before this) updates the scope headers
        # with the generated/extracted correlation ID when update_request_header=True.
        corr_id = self._get_correlation_id_from_scope(scope)

        # Set into Glyph request context - clear any leftover state
        if corr_id:
            set_request_context(request_id=corr_id, clear_unset=True)

        try:
            await self.app(scope, receive, send)
        finally:
            # Clear request context after request is complete
            clear_request_context()

    def _get_correlation_id_from_scope(self, scope: Scope) -> str | None:
        """Extract correlation ID from scope headers.

        Args:
            scope: The ASGI scope dictionary.

        Returns:
            The correlation ID if found, None otherwise.
        """
        headers = dict(scope.get("headers", []))
        # Check both byte and string keys (ASGI uses bytes, but some test mocks use strings)
        for key in ("x-request-id", b"x-request-id"):
            value = headers.get(key)
            if value:
                if isinstance(value, bytes):
                    return value.decode("utf-8")
                return value
        return None
