"""Custom ASGI middleware and static-file helpers for Glyph.

This module houses the middleware classes registered by the application
factory in ``main.py``:

- ``CSPMiddleware``: Content Security Policy and security-header injection.
- ``RequestSizeMiddleware``: request body size limiting (DoS protection).
- ``CachedStaticFiles``: static file server with long-term caching headers.
"""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


class CSPMiddleware:
    """ASGI middleware that injects Content Security Policy and security headers.

    Applies strict CSP policies to all HTTP responses, with a relaxed policy
    for documentation routes (/docs, /redoc, /openapi.json) to allow external
    CDN resources needed for API documentation rendering.

    Security headers applied:
        - Content-Security-Policy: Restricts resource loading sources.
        - X-Content-Type-Options: Prevents MIME-type sniffing.
        - X-Frame-Options: Prevents clickjacking via iframes.
        - Referrer-Policy: Controls referrer information.
        - Permissions-Policy: Restricts browser features.
    """

    CSP_HEADER = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    CSP_HEADER_DOCS = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    _SECURITY_HEADERS_NO_HSTS: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
    ]

    _HSTS_HEADER: tuple[bytes, bytes] = (
        b"strict-transport-security",
        b"max-age=31536000; includeSubDomains; preload",
    )

    def __init__(
        self,
        app: Callable[[Any, Any, Any], Awaitable[None]],
        use_https: bool = False,
    ) -> None:
        """Initialize the CSP middleware.

        Args:
            app: The downstream ASGI application.
            use_https: Whether HTTPS is enabled. HSTS header is only included
                when True to avoid breaking development environments.

        """
        self.app = app
        self._security_headers: list[tuple[bytes, bytes]] = (
            [*[self._HSTS_HEADER], *self._SECURITY_HEADERS_NO_HSTS]
            if use_https
            else list(self._SECURITY_HEADERS_NO_HSTS)
        )

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process the ASGI request, injecting security headers into the response.

        Args:
            scope: The ASGI connection scope.
            receive: Awaitable callable for receiving events.
            send: Awaitable callable for sending events.

        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        is_docs_route = path.startswith(("/docs", "/redoc", "/openapi.json"))
        csp_header = self.CSP_HEADER_DOCS if is_docs_route else self.CSP_HEADER

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((b"content-security-policy", csp_header.encode("utf-8")))
                headers.extend(self._security_headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestBodyTooLarge(Exception):
    """Custom exception for request body size limit violations.

    Using a dedicated exception class prevents accidentally catching
    unrelated ValueError exceptions from downstream code.
    """

    pass


class RequestSizeMiddleware:
    """ASGI middleware that enforces a maximum request body size.

    Prevents denial-of-service attacks via extremely large request bodies
    by rejecting requests that exceed the configured maximum size.
    """

    def __init__(
        self,
        app: Callable[[Any, Any, Any], Awaitable[None]],
        max_size: int = 100 * 1024 * 1024,  # 100 MB default
    ) -> None:
        """Initialize the request size middleware.

        Args:
            app: The downstream ASGI application.
            max_size: Maximum allowed request body size in bytes.

        """
        self.app = app
        self.max_size = max_size

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process the ASGI request, enforcing body size limits.

        Args:
            scope: The ASGI connection scope.
            receive: Awaitable callable for receiving events.
            send: Awaitable callable for sending events.

        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        total_size: int = 0

        async def receive_wrapper() -> dict[str, Any]:
            nonlocal total_size
            message = await receive()
            if message["type"] == "http.request" and message.get("body"):
                body_size = len(message["body"])
                total_size += body_size
                if total_size > self.max_size:
                    raise RequestBodyTooLarge(
                        f"Request body size ({total_size} bytes) exceeds maximum allowed size ({self.max_size} bytes)",
                    )
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except RequestBodyTooLarge:
            response = {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            }
            await send(response)
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"detail": "Request body too large"}',
                },
            )


class CachedStaticFiles(StaticFiles):
    """Static file server with long-term caching headers.

    Extends FastAPI's StaticFiles to add Cache-Control and Immutable headers
    for optimized browser caching of static assets.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cached static files server.

        Args:
            *args: Positional arguments passed to StaticFiles.
            **kwargs: Keyword arguments passed to StaticFiles.

        """
        super().__init__(*args, **kwargs)
        self.cache_control_max_age = 86400

    async def get_response(self, path: str, scope: Any) -> Response:
        """Generate a response for the given path with caching headers.

        Args:
            path: The requested file path.
            scope: The ASGI scope.

        Returns:
            The response with caching headers applied.

        """
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            response.headers["Cache-Control"] = f"public, max-age={self.cache_control_max_age}"
            response.headers["Immutable"] = "true"
        return cast(Response, response)
