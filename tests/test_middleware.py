"""Unit tests for the ASGI middleware in ``app.core.middleware``.

These tests drive the middleware classes directly with raw ASGI
scope/receive/send callables (no TestClient), so they exercise the exact
header-injection and body-limiting logic that ships in production.
"""

from typing import Any

import pytest
from app.core.middleware import CachedStaticFiles, CSPMiddleware, RequestSizeMiddleware
from fastapi import HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from starlette.middleware.exceptions import ExceptionMiddleware


async def _run_asgi(
    app: Any,
    scope: dict[str, Any],
    body: bytes = b"",
) -> tuple[int | None, dict[str, str], bytes]:
    """Drive an ASGI app with a minimal HTTP scope.

    Returns:
        Tuple of (status, headers-as-str-dict, response body).

    """
    sent: list[dict[str, Any]] = []
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(scope, receive, send)

    status: int | None = None
    headers: dict[str, str] = {}
    out_body = b""
    for message in sent:
        if message["type"] == "http.response.start":
            status = message["status"]
            headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in message.get("headers", [])}
        elif message["type"] == "http.response.body":
            out_body += message.get("body", b"")
    return status, headers, out_body


async def _dummy_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await receive()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


class TestCSPMiddleware:
    """CSPMiddleware header injection behavior."""

    @pytest.mark.asyncio
    async def test_csp_header_present_on_response(self) -> None:
        """Every HTTP response must carry the strict CSP header."""
        mw = CSPMiddleware(_dummy_app)
        _, headers, _ = await _run_asgi(mw, {"type": "http", "method": "GET", "path": "/"})
        assert headers.get("content-security-policy") == CSPMiddleware.CSP_HEADER
        # Base security headers ride along on every response.
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("use_https", [False, True])
    async def test_hsts_only_when_use_https(self, use_https: bool) -> None:
        """HSTS must be present exactly when use_https is True."""
        mw = CSPMiddleware(_dummy_app, use_https=use_https)
        _, headers, _ = await _run_asgi(mw, {"type": "http", "method": "GET", "path": "/"})
        if use_https:
            assert headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains; preload"
        else:
            assert "strict-transport-security" not in headers

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    async def test_docs_route_gets_docs_csp(self, path: str) -> None:
        """Documentation routes must get the relaxed docs CSP."""
        mw = CSPMiddleware(_dummy_app)
        _, headers, _ = await _run_asgi(mw, {"type": "http", "method": "GET", "path": path})
        assert headers.get("content-security-policy") == CSPMiddleware.CSP_HEADER_DOCS

    @pytest.mark.asyncio
    async def test_non_docs_route_does_not_get_docs_csp(self) -> None:
        """Non-docs routes must keep the strict CSP (no jsdelivr)."""
        mw = CSPMiddleware(_dummy_app)
        _, headers, _ = await _run_asgi(mw, {"type": "http", "method": "GET", "path": "/binary-library"})
        assert "cdn.jsdelivr.net" not in headers.get("content-security-policy", "")

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self) -> None:
        """Non-HTTP scopes (e.g. websocket) bypass the middleware untouched."""
        calls: dict[str, Any] = {}

        async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            calls["send"] = send
            await send({"type": "websocket.accept"})

        async def receive() -> dict[str, Any]:
            return {"type": "websocket.connect"}

        async def send(message: dict[str, Any]) -> None:
            calls["message"] = message

        mw = CSPMiddleware(app)
        await mw({"type": "websocket", "path": "/ws"}, receive, send)
        # The downstream app must receive the *original* send, un-wrapped.
        assert calls["send"] is send
        assert calls["message"]["type"] == "websocket.accept"


class TestRequestSizeMiddleware:
    """RequestSizeMiddleware body-limit behavior."""

    @pytest.mark.asyncio
    async def test_request_under_limit_passes(self) -> None:
        """Bodies within max_size reach the app and produce a normal response."""
        mw = RequestSizeMiddleware(_dummy_app, max_size=100)
        status, _, body = await _run_asgi(
            mw,
            {"type": "http", "method": "POST", "path": "/api/v1/binaries/uploadBinary"},
            body=b"x" * 100,
        )
        assert status == 200
        assert body == b"ok"

    @pytest.mark.asyncio
    async def test_request_size_middleware_413(self) -> None:
        """Bodies exceeding max_size must be rejected with a 413 JSON body.

        ``RequestBodyTooLarge`` is an ``HTTPException`` that production converts
        to a 413 via Starlette's ``ExceptionMiddleware`` (see ``main.py``), so
        the harness wraps the size middleware in that middleware to mirror the
        real stack.
        """
        mw = ExceptionMiddleware(
            RequestSizeMiddleware(_dummy_app, max_size=10),
            handlers={HTTPException: http_exception_handler},
        )
        status, headers, body = await _run_asgi(
            mw,
            {"type": "http", "method": "POST", "path": "/api/v1/binaries/uploadBinary"},
            body=b"x" * 11,
        )
        assert status == 413
        assert headers.get("content-type") == "application/json"
        assert b"Request body too large" in body

    @pytest.mark.asyncio
    async def test_non_http_scope_passthrough(self) -> None:
        """Non-HTTP scopes bypass the size middleware untouched."""
        calls: dict[str, Any] = {}

        async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
            calls["send"] = send
            await send({"type": "websocket.accept"})

        async def receive() -> dict[str, Any]:
            return {"type": "websocket.connect"}

        async def send(message: dict[str, Any]) -> None:
            calls["message"] = message

        mw = RequestSizeMiddleware(app, max_size=10)
        await mw({"type": "websocket", "path": "/ws"}, receive, send)
        assert calls["send"] is send


class TestCachedStaticFiles:
    """CachedStaticFiles long-term caching headers."""

    @pytest.mark.asyncio
    async def test_cached_static_files_immutable_header(self, tmp_path: Any) -> None:
        """Served files must carry Cache-Control + Immutable headers."""
        (tmp_path / "hello.txt").write_text("hello")
        static = CachedStaticFiles(directory=str(tmp_path))
        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "path": "/hello.txt",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
        response = await static.get_response("hello.txt", scope)
        assert isinstance(response, FileResponse)
        assert response.headers["Cache-Control"] == "public, max-age=86400"
        assert response.headers["Immutable"] == "true"
