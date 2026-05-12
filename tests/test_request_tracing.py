"""Tests for correlation ID middleware (asgi-correlation-id).

Tests verify that the CorrelationIdMiddleware from asgi-correlation-id
properly generates and propagates request IDs, and that the bridge
middleware connects it to the Glyph request context system.
"""

from typing import Any

import pytest

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id

from app.core.correlation_bridge import CorrelationIdBridgeMiddleware
from app.utils.request_context import (
    get_request_context,
    get_request_id,
)


class TestCorrelationIdMiddleware:
    """Tests for CorrelationIdMiddleware from asgi-correlation-id."""

    @pytest.mark.asyncio
    async def test_middleware_generates_correlation_id(self) -> None:
        """Test that middleware generates a correlation ID when none is provided."""
        received_ids: list[str] = []

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            corr_id = correlation_id.get()
            if corr_id is not None:
                received_ids.append(corr_id)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdMiddleware(dummy_app)
        scope: Any = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            pass

        await middleware(scope, receive, send)

        # Correlation ID should be generated
        assert len(received_ids) == 1
        assert received_ids[0] is not None
        # Should be a valid hex UUID (32 chars for UUID hex format)
        assert len(received_ids[0]) == 32

    @pytest.mark.asyncio
    async def test_middleware_adds_correlation_id_to_response(self) -> None:
        """Test that middleware adds X-Request-ID to response headers."""
        response_headers: list[tuple[bytes, bytes]] = []

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdMiddleware(dummy_app)
        scope: Any = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            if message["type"] == "http.response.start":
                response_headers.extend(message.get("headers", []))

        await middleware(scope, receive, send)

        # Check that x-request-id header was added
        header_dict = {k.decode(): v.decode() for k, v in response_headers}
        assert "x-request-id" in header_dict

    @pytest.mark.asyncio
    async def test_middleware_uses_existing_request_id(self) -> None:
        """Test that middleware extracts existing X-Request-ID from headers.

        Note: The library validates incoming IDs as UUID4 by default, so we
        must provide a valid UUID hex string.
        """
        received_ids: list[str] = []

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            corr_id = correlation_id.get()
            if corr_id is not None:
                received_ids.append(corr_id)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdMiddleware(dummy_app)
        # Valid UUID4 hex: 1b4a2d9e-7c3f-4a5b-8e6d-9f0a1b2c3d4e -> hex without dashes
        existing_id = "1b4a2d9e7c3f4a5b8e6d9f0a1b2c3d4e"
        scope: Any = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-request-id", existing_id.encode())],
        }

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            pass

        await middleware(scope, receive, send)

        # Should use the existing ID
        assert len(received_ids) == 1
        assert received_ids[0] == existing_id

    @pytest.mark.asyncio
    async def test_middleware_skips_non_http(self) -> None:
        """Test that middleware skips non-HTTP scopes."""
        called = False

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal called
            called = True
            await send({"type": "http.response.start", "status": 200, "headers": []})

        middleware = CorrelationIdMiddleware(dummy_app)
        scope: Any = {"type": "websocket", "path": "/ws", "headers": []}

        async def receive() -> Any:
            return {"type": "websocket.connect"}

        async def send(message: Any) -> None:
            pass

        await middleware(scope, receive, send)
        assert called is True

    def test_custom_header_name(self) -> None:
        """Test using a custom header name."""
        middleware = CorrelationIdMiddleware(
            lambda s, r, s2: None,
            header_name="X-Custom-Request-ID"
        )
        # Library keeps the header name as-is (not lowercased)
        assert middleware.header_name == "X-Custom-Request-ID"


class TestCorrelationIdBridgeMiddleware:
    """Tests for the bridge middleware connecting asgi-correlation-id to request context."""

    @pytest.mark.asyncio
    async def test_bridge_populates_request_context(self) -> None:
        """Test that bridge middleware sets correlation ID in request context.

        Middleware stack matches main.py order:
          app.add_middleware(CorrelationIdBridgeMiddleware)  # First = inner
          app.add_middleware(CorrelationIdMiddleware)         # Last = outer
        So CorrelationId runs first, then Bridge reads updated headers.
        """
        received_request_ids: list[str | None] = []

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            req_id = get_request_id()
            received_request_ids.append(req_id)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        # Stack matches main.py: CorrelationId is outer (runs first), Bridge is inner.
        bridge_middleware = CorrelationIdBridgeMiddleware(dummy_app)
        correlation_middleware = CorrelationIdMiddleware(bridge_middleware)

        scope: Any = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            pass

        await correlation_middleware(scope, receive, send)

        # Request ID should be populated in context
        assert len(received_request_ids) == 1
        assert received_request_ids[0] is not None

    @pytest.mark.asyncio
    async def test_bridge_clears_context_after_request(self) -> None:
        """Test that bridge middleware clears context after request completes."""
        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        bridge_middleware = CorrelationIdBridgeMiddleware(dummy_app)
        correlation_middleware = CorrelationIdMiddleware(bridge_middleware)

        scope: Any = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            pass

        await correlation_middleware(scope, receive, send)

        # Context should be cleared after request
        ctx = get_request_context()
        assert ctx.request_id is None

    @pytest.mark.asyncio
    async def test_bridge_clears_context_on_exception(self) -> None:
        """Test that bridge middleware clears context even when app raises."""
        async def failing_app(scope: Any, receive: Any, send: Any) -> None:
            raise ValueError("Test error")

        bridge_middleware = CorrelationIdBridgeMiddleware(failing_app)
        correlation_middleware = CorrelationIdMiddleware(bridge_middleware)

        scope: Any = {"type": "http", "method": "GET", "path": "/", "headers": []}

        async def receive() -> Any:
            return {"type": "http.request"}

        async def send(message: Any) -> None:
            pass

        with pytest.raises(ValueError, match="Test error"):
            await correlation_middleware(scope, receive, send)

        # Context should be cleared after exception
        ctx = get_request_context()
        assert ctx.request_id is None

    @pytest.mark.asyncio
    async def test_bridge_skips_non_http(self) -> None:
        """Test that bridge middleware skips non-HTTP scopes."""
        called = False

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal called
            called = True
            await send({"type": "http.response.start", "status": 200, "headers": []})

        bridge_middleware = CorrelationIdBridgeMiddleware(dummy_app)
        correlation_middleware = CorrelationIdMiddleware(bridge_middleware)

        scope: Any = {"type": "websocket", "path": "/ws", "headers": []}

        async def receive() -> Any:
            return {"type": "websocket.connect"}

        async def send(message: Any) -> None:
            pass

        await correlation_middleware(scope, receive, send)
        assert called is True
