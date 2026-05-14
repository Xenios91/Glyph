"""Bridge middleware to connect asgi-correlation-id with Glyph request context."""

from typing import Any, Callable

from starlette.types import Receive, Send, Scope

from app.utils.request_context import set_request_context, clear_request_context


class CorrelationIdBridgeMiddleware:
    """Propagate correlation_id from headers into Glyph request context."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Any]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        corr_id = self._get_correlation_id_from_scope(scope)
        if corr_id:
            set_request_context(request_id=corr_id, clear_unset=True)

        try:
            await self.app(scope, receive, send)
        finally:
            clear_request_context()

    def _get_correlation_id_from_scope(self, scope: Scope) -> str | None:
        """Extract correlation ID from scope headers."""
        headers = dict(scope.get("headers", []))
        for key in ("x-request-id", b"x-request-id"):
            value = headers.get(key)
            if value:
                if isinstance(value, bytes):
                    return value.decode("utf-8")
                return value
        return None
