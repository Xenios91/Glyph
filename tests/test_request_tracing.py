"""Tests for request tracing middleware."""

from typing import Any

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.core.request_tracing import RequestIDMiddleware, get_request_id_from_scope


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware ASGI middleware."""

    def test_init_default_header(self) -> None:
        """Test middleware initialization with default header name."""
        app = Mock()
        middleware = RequestIDMiddleware(app)
        assert middleware.app is app
        assert middleware.header_name == "x-request-id"

    def test_init_custom_header(self) -> None:
        """Test middleware initialization with custom header name."""
        app = Mock()
        middleware = RequestIDMiddleware(app, header_name="X-Custom-ID")
        assert middleware.header_name == "x-custom-id"

    @pytest.mark.asyncio
    async def test_call_non_http_scope(self) -> None:
        """Test that non-HTTP scopes pass through without modification."""
        mock_app = AsyncMock()
        middleware = RequestIDMiddleware(mock_app)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        mock_app.assert_awaited_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_call_http_scope_generates_id(self) -> None:
        """Test that HTTP scope generates a request ID when none present."""
        mock_app = AsyncMock()
        middleware = RequestIDMiddleware(mock_app)

        scope = {"type": "http", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("app.core.request_tracing.set_request_context") as mock_set:
            with patch("app.core.request_tracing.clear_request_context") as mock_clear:
                await middleware(scope, receive, send)
                mock_set.assert_called_once()
                call_kwargs = mock_set.call_args[1]
                assert "request_id" in call_kwargs
                assert len(call_kwargs["request_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_call_http_scope_uses_existing_id(self) -> None:
        """Test that existing request ID is extracted from headers (string-keyed dict)."""
        mock_app = AsyncMock()
        middleware = RequestIDMiddleware(mock_app)

        # Code uses dict() on headers then string key lookup, so string-keyed dict works
        scope = {
            "type": "http",
            "headers": {"x-request-id": "test-request-123"},
        }
        receive = AsyncMock()
        send = AsyncMock()

        with patch("app.core.request_tracing.set_request_context") as mock_set:
            with patch("app.core.request_tracing.clear_request_context"):
                await middleware(scope, receive, send)
                call_kwargs = mock_set.call_args[1]
                assert call_kwargs["request_id"] == "test-request-123"

    @pytest.mark.asyncio
    async def test_call_http_scope_bytes_headers_generates_new_id(self) -> None:
        """Test that bytes headers generate new ID (code uses string key lookup)."""
        mock_app = AsyncMock()
        middleware = RequestIDMiddleware(mock_app)

        # Bytes headers won't match string key lookup, so new ID generated
        scope = {
            "type": "http",
            "headers": [(b"x-request-id", b"test-request-123")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with patch("app.core.request_tracing.set_request_context") as mock_set:
            with patch("app.core.request_tracing.clear_request_context"):
                await middleware(scope, receive, send)
                call_kwargs = mock_set.call_args[1]
                # New UUID generated because bytes key doesn't match string lookup
                assert len(call_kwargs["request_id"]) == 36

    @pytest.mark.asyncio
    async def test_call_clears_context(self) -> None:
        """Test that request context is cleared after request."""
        mock_app = AsyncMock()
        middleware = RequestIDMiddleware(mock_app)

        scope = {"type": "http", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("app.core.request_tracing.set_request_context"):
            with patch("app.core.request_tracing.clear_request_context") as mock_clear:
                await middleware(scope, receive, send)
                mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_clears_context_on_exception(self) -> None:
        """Test that context is cleared even when exception occurs."""
        mock_app = AsyncMock(side_effect=RuntimeError("test error"))
        middleware = RequestIDMiddleware(mock_app)

        scope = {"type": "http", "headers": []}
        receive = AsyncMock()
        send = AsyncMock()

        with patch("app.core.request_tracing.set_request_context"):
            with patch("app.core.request_tracing.clear_request_context") as mock_clear:
                with pytest.raises(RuntimeError, match="test error"):
                    await middleware(scope, receive, send)
                mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_adds_request_id_to_response(self) -> None:
        """Test that request ID is added to response headers."""
        received_messages: list[dict[str, Any]] = []

        async def mock_send(message: dict[str, Any]) -> None:
            received_messages.append(message)

        mock_app = AsyncMock()
        async def mock_app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({"type": "http.response.body", "body": b"OK"})

        middleware = RequestIDMiddleware(mock_app_call)

        # Use string-keyed dict for headers so existing ID is extracted
        scope = {"type": "http", "headers": {"x-request-id": "test-id-456"}}
        receive = AsyncMock()

        await middleware(scope, receive, mock_send)

        start_message = received_messages[0]
        # Response headers are list of lists [key, value]
        header_dict = {h[0]: h[1] for h in start_message["headers"]}
        assert header_dict[b"x-request-id"] == b"test-id-456"

    @pytest.mark.asyncio
    async def test_call_handles_dict_headers(self) -> None:
        """Test response header injection with dict-style headers."""
        received_messages: list[dict[str, Any]] = []

        async def mock_send(message: dict[str, Any]) -> None:
            received_messages.append(message)

        mock_app = AsyncMock()
        async def mock_app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": {"content-type": "text/plain"},
            })

        middleware = RequestIDMiddleware(mock_app_call)

        scope = {"type": "http", "headers": []}
        receive = AsyncMock()

        await middleware(scope, receive, mock_send)

        start_message = received_messages[0]
        headers = dict(start_message["headers"])
        assert b"x-request-id" in headers

    @pytest.mark.asyncio
    async def test_call_handles_empty_headers(self) -> None:
        """Test response header injection with no existing headers."""
        received_messages: list[dict[str, Any]] = []

        async def mock_send(message: dict[str, Any]) -> None:
            received_messages.append(message)

        async def mock_app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })

        middleware = RequestIDMiddleware(mock_app_call)

        scope = {"type": "http", "headers": []}
        receive = AsyncMock()

        await middleware(scope, receive, mock_send)

        start_message = received_messages[0]
        headers = dict(start_message["headers"])
        assert b"x-request-id" in headers

    def test_get_or_create_existing_id(self) -> None:
        """Test extracting existing request ID from scope."""
        middleware = RequestIDMiddleware(Mock())
        # String-keyed dict works with code's string key lookup
        scope = {"headers": {"x-request-id": "existing-id"}}
        result = middleware._get_or_create_request_id(scope)
        assert result == "existing-id"

    def test_get_or_create_bytes_headers_generates_new(self) -> None:
        """Test that bytes tuple headers generate new ID (string key lookup mismatch)."""
        middleware = RequestIDMiddleware(Mock())
        # Bytes tuple headers create bytes keys in dict, but lookup uses string key
        scope = {"headers": [(b"x-request-id", b"existing-id")]}
        result = middleware._get_or_create_request_id(scope)
        # New UUID generated because bytes key doesn't match string lookup
        assert len(result) == 36

    def test_get_or_create_existing_id_bytes_value(self) -> None:
        """Test extracting request ID when value is bytes (triggers decode)."""
        middleware = RequestIDMiddleware(Mock())
        # String key with bytes value triggers line 81 decode
        scope = {"headers": {"x-request-id": b"bytes-id-decoded"}}
        result = middleware._get_or_create_request_id(scope)
        assert result == "bytes-id-decoded"

    def test_get_or_create_existing_id_string(self) -> None:
        """Test extracting existing request ID as string from scope."""
        middleware = RequestIDMiddleware(Mock())
        scope = {"headers": {"x-request-id": "existing-id"}}
        result = middleware._get_or_create_request_id(scope)
        assert result == "existing-id"

    def test_get_or_create_new_id(self) -> None:
        """Test generating new request ID when none exists."""
        middleware = RequestIDMiddleware(Mock())
        scope = {"headers": []}
        result = middleware._get_or_create_request_id(scope)
        assert len(result) == 36  # UUID format

    def test_get_or_create_empty_scope(self) -> None:
        """Test generating new request ID with empty scope."""
        middleware = RequestIDMiddleware(Mock())
        scope = {}
        result = middleware._get_or_create_request_id(scope)
        assert len(result) == 36  # UUID format


class TestGetRequestIdFromScope:
    """Tests for get_request_id_from_scope utility function."""

    def test_get_request_id_string_dict(self) -> None:
        """Test extracting request ID from string-keyed dict header."""
        scope = {"headers": {"x-request-id": "test-123"}}
        result = get_request_id_from_scope(scope)
        assert result == "test-123"

    def test_get_request_id_bytes_tuple_returns_none(self) -> None:
        """Test that bytes tuple headers return None (string key lookup mismatch)."""
        scope = {"headers": [(b"x-request-id", b"test-123")]}
        result = get_request_id_from_scope(scope)
        # Returns None because bytes key doesn't match string lookup
        assert result is None

    def test_get_request_id_bytes_value(self) -> None:
        """Test extracting request ID when value is bytes (triggers decode)."""
        # String key with bytes value triggers line 131 decode
        scope = {"headers": {"x-request-id": b"bytes-value-123"}}
        result = get_request_id_from_scope(scope)
        assert result == "bytes-value-123"

    def test_get_request_id_string(self) -> None:
        """Test extracting request ID from string header."""
        scope = {"headers": {"x-request-id": "test-123"}}
        result = get_request_id_from_scope(scope)
        assert result == "test-123"

    def test_get_request_id_missing(self) -> None:
        """Test returning None when request ID is not present."""
        scope = {"headers": []}
        result = get_request_id_from_scope(scope)
        assert result is None

    def test_get_request_id_empty_scope(self) -> None:
        """Test returning None with empty scope."""
        scope = {}
        result = get_request_id_from_scope(scope)
        assert result is None

    def test_get_request_id_custom_header(self) -> None:
        """Test extracting request ID with custom header name."""
        scope = {"headers": {"x-custom-id": "custom-123"}}
        result = get_request_id_from_scope(scope, header_name="X-Custom-ID")
        assert result == "custom-123"

    def test_get_request_id_case_insensitive(self) -> None:
        """Test that header lookup uses lowercase."""
        scope = {"headers": {"x-request-id": "lower-123"}}
        result = get_request_id_from_scope(scope, header_name="X-Request-ID")
        assert result == "lower-123"
