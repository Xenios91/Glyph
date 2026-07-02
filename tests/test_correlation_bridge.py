"""Tests for the CorrelationIdBridgeMiddleware."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from app.core.correlation_bridge import CorrelationIdBridgeMiddleware
from app.utils.request_context import (
    clear_request_context,
    get_request_context,
)
from starlette.types import Receive, Scope, Send


async def _noop_send(_: dict[str, Any]) -> None:
    """No-op send callback for tests that do not inspect messages."""
    pass


class _MockResponse:
    """Minimal ASGI response that captures sends."""

    def __init__(self, status_code: int = 200, body: bytes = b"ok") -> None:
        self.status_code = status_code
        self.body = body
        self.started = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.started:
            await send(
                {
                    "type": "http.response.start",
                    "status": self.status_code,
                    "headers": [[b"content-type", b"text/plain"]],
                }
            )
            self.started = True
        await send({"type": "http.response.body", "body": self.body})


# -- fixtures --


@pytest.fixture
def _clean_context() -> Any:
    """Ensure request context is clean before and after each test."""
    clear_request_context()
    yield
    clear_request_context()


# -- tests: non-HTTP scope passthrough --


class TestNonHttpScope:
    """Middleware should pass through non-HTTP scopes untouched."""

    async def test_websocket_scope_passthrough(self, _clean_context: None) -> None:
        scope: Scope = {"type": "websocket", "headers": []}
        send_called = False

        async def app(_: Scope, __: Receive, ___: Send) -> None:
            nonlocal send_called
            send_called = True

        middleware = CorrelationIdBridgeMiddleware(app)
        await middleware(scope, lambda: None, _noop_send)

        assert send_called is True
        # Context must NOT be set for non-HTTP scopes
        ctx = get_request_context()
        assert ctx.request_id is None


# -- tests: correlation ID extraction --


class TestCorrelationIdExtraction:
    """Tests for _get_correlation_id_from_scope."""

    def test_extract_from_bytes_headers(self) -> None:
        middleware = CorrelationIdBridgeMiddleware(lambda *a: None)
        scope: Scope = {
            "type": "http",
            "headers": [
                [b"host", b"localhost"],
                [b"x-request-id", b"abc-123"],
            ],
        }
        assert middleware._get_correlation_id_from_scope(scope) == "abc-123"

    def test_missing_header_returns_none(self) -> None:
        middleware = CorrelationIdBridgeMiddleware(lambda *a: None)
        scope: Scope = {
            "type": "http",
            "headers": [[b"host", b"localhost"]],
        }
        assert middleware._get_correlation_id_from_scope(scope) is None

    def test_empty_headers_returns_none(self) -> None:
        middleware = CorrelationIdBridgeMiddleware(lambda *a: None)
        scope: Scope = {"type": "http", "headers": []}
        assert middleware._get_correlation_id_from_scope(scope) is None

    def test_missing_headers_key_returns_none(self) -> None:
        middleware = CorrelationIdBridgeMiddleware(lambda *a: None)
        scope: Scope = {"type": "http"}
        assert middleware._get_correlation_id_from_scope(scope) is None

    def test_first_matching_header_wins(self) -> None:
        middleware = CorrelationIdBridgeMiddleware(lambda *a: None)
        scope: Scope = {
            "type": "http",
            "headers": [
                [b"x-request-id", b"first-id"],
                [b"x-request-id", b"second-id"],
            ],
        }
        assert middleware._get_correlation_id_from_scope(scope) == "first-id"


# -- tests: full middleware lifecycle --


class TestMiddlewareLifecycle:
    """Tests for the full ASGI middleware call lifecycle."""

    async def test_sets_request_context_with_correlation_id(self) -> None:
        captured_request_id: str | None = None

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal captured_request_id
            ctx = get_request_context()
            captured_request_id = ctx.request_id
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdBridgeMiddleware(app)
        scope: Scope = {
            "type": "http",
            "headers": [[b"x-request-id", b"req-42"]],
        }
        await middleware(scope, lambda: None, _noop_send)

        assert captured_request_id == "req-42"

    async def test_clears_context_after_response(self) -> None:
        async def app(_: Scope, __: Receive, ___: Send) -> None:
            await ___({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdBridgeMiddleware(app)
        scope: Scope = {
            "type": "http",
            "headers": [[b"x-request-id", b"req-99"]],
        }
        await middleware(scope, lambda: None, _noop_send)

        # Context must be cleared after middleware finishes
        ctx = get_request_context()
        assert ctx.request_id is None

    async def test_clears_context_even_on_app_error(self) -> None:
        async def app(_: Scope, __: Receive, ___: Send) -> None:
            raise RuntimeError("boom")

        middleware = CorrelationIdBridgeMiddleware(app)
        scope: Scope = {
            "type": "http",
            "headers": [[b"x-request-id", b"req-fail"]],
        }

        with pytest.raises(RuntimeError, match="boom"):
            await middleware(scope, lambda: None, _noop_send)

        # Context must still be cleared via finally
        ctx = get_request_context()
        assert ctx.request_id is None

    async def test_no_context_when_header_missing(self) -> None:
        context_set = False

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal context_set
            ctx = get_request_context()
            context_set = ctx.request_id is not None
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = CorrelationIdBridgeMiddleware(app)
        scope: Scope = {
            "type": "http",
            "headers": [[b"host", b"localhost"]],
        }
        await middleware(scope, lambda: None, _noop_send)

        assert context_set is False

    async def test_calls_downstream_app(self) -> None:
        response = _MockResponse(status_code=201, body=b"created")
        middleware = CorrelationIdBridgeMiddleware(response)

        sent_messages: list[dict[str, Any]] = []

        async def mock_send(msg: dict[str, Any]) -> None:
            sent_messages.append(msg)

        scope: Scope = {
            "type": "http",
            "headers": [[b"x-request-id", b"req-ok"]],
        }
        await middleware(scope, lambda: None, mock_send)

        assert len(sent_messages) == 2
        assert sent_messages[0]["status"] == 201
        assert sent_messages[1]["body"] == b"created"
