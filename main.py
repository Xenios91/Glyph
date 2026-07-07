"""Main application entry point for Glyph.

This module creates and configures the FastAPI application instance,
registering middleware, routers, and exception handlers. It serves as
the central bootstrap for the entire Glyph binary analysis service.

Components:
    CSPMiddleware: Content Security Policy middleware for HTTP responses.
    CachedStaticFiles: Static file server with caching headers.
    create_app: Factory function that builds the FastAPI application.
"""

from collections.abc import Awaitable, Callable
from typing import Any, cast
from urllib.parse import quote

from app.api.router import api_router
from app.auth.endpoints import router as auth_router
from app.core.lifespan import lifespan
from app.core.rate_limiter import limiter
from app.templates import templates
from app.utils.helpers import ACCEPT_TYPE
from app.utils.logging_config import setup_logging_from_config
from app.web.endpoints.web import router as web_router
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

setup_logging_from_config()


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
        is_docs_route = path.startswith("/docs")
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


def create_app() -> FastAPI:
    """Factory function that creates and configures the FastAPI application.

    Registers middleware (GZip, CORS, CSP, rate limiting, correlation ID),
    mounts static files, and includes all API and web routers.

    Returns:
        Configured FastAPI application instance.

    """
    app = FastAPI(
        title="Glyph API",
        description="Binary analysis powered by machine learning",
        version="0.1.0",
        lifespan=lifespan,
        strict_content_type=True,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    logger.info("Middleware registered: GZipMiddleware")

    from app.config.settings import get_settings

    settings = get_settings()

    # Request size limit middleware
    max_body_size = settings.max_file_size_mb * 1024 * 1024
    app.add_middleware(RequestSizeMiddleware, max_size=max_body_size)
    logger.info("Middleware registered: RequestSizeMiddleware (max_size=%d MB)", settings.max_file_size_mb)

    if settings.logging.request_tracing.enabled:
        from app.core.correlation_bridge import CorrelationIdBridgeMiddleware

        app.add_middleware(CorrelationIdBridgeMiddleware)
        app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
        logger.info("Middleware registered: CorrelationIdMiddleware (asgi-correlation-id)")
        logger.info("Middleware registered: CorrelationIdBridgeMiddleware")
    else:
        logger.info("CorrelationIdMiddleware disabled via config")

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiter registered: slowapi")

    app.add_middleware(CSPMiddleware, use_https=settings.use_https)
    logger.info("Middleware registered: CSPMiddleware")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        allow_credentials=False,
        max_age=86400,
        expose_headers=["X-Request-ID"],
    )
    logger.info("Middleware registered: CORSMiddleware")

    try:
        app.mount("/static", CachedStaticFiles(directory="static"), name="static")
        logger.info("Static files mounted at /static with caching headers")
    except Exception as e:
        logger.warning("Static files mount failed: {}", e)

    app.include_router(auth_router)
    logger.info("Router registered: auth at /auth")

    app.include_router(api_router, prefix="/api")
    logger.info("Router registered: api at /api")

    app.include_router(web_router)
    logger.info("Router registered: web")

    # Health check endpoints
    @app.get("/health", tags=["Health"])
    async def health_check() -> JSONResponse:
        """Liveness probe for Kubernetes and other orchestrators.

        Returns:
            JSON response with status "ok".

        """
        return JSONResponse({"status": "ok"})

    @app.get("/ready", tags=["Health"])
    async def readiness_check() -> JSONResponse:
        """Readiness probe to verify application dependencies are available.

        Checks database connectivity and returns overall readiness status.

        Returns:
            JSON response with readiness status and component health.

        """
        from app.database.session_handler import get_async_session

        component_status: dict[str, str] = {}

        # Check database connectivity
        try:
            async with await get_async_session() as session:
                await session.execute("SELECT 1")
            component_status["database"] = "ok"
        except Exception as e:
            logger.warning("Database readiness check failed: {}", e)
            component_status["database"] = f"error: {e}"

        overall = "ok" if all(v == "ok" for v in component_status.values()) else "degraded"
        return JSONResponse(
            {
                "status": overall,
                "components": component_status,
            },
        )

    return app


app = create_app()


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    """Serve the site favicon.

    Returns:
        FileResponse pointing to the favicon file.

    """
    return FileResponse("static/favicon.ico")


# Mapping of HTTP status codes to machine-readable error codes.
_STATUS_ERROR_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
    507: "INSUFFICIENT_STORAGE",
}


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException,
) -> HTMLResponse | JSONResponse | RedirectResponse:
    """Handle HTTP exceptions with appropriate response format.

    Routes 401 errors to the login page for HTML requests, returns styled
    error pages for HTML clients, and JSON error responses for API clients.

    Args:
        request: The incoming FastAPI request.
        exc: The HTTPException raised by the application.

    Returns:
        HTML error page, JSON error response, or redirect to login.

    """
    level = "WARNING" if exc.status_code >= 500 else "DEBUG"
    logger.log(level, "HTTP error {}: {}", exc.status_code, exc.detail)

    accept = request.headers.get("Accept", "")

    if exc.status_code == 401 and ACCEPT_TYPE in accept:
        redirect_path = request.url.path
        if not redirect_path.startswith("/"):
            redirect_path = "/"
        redirect_path = "/".join(segment for segment in redirect_path.split("/") if segment and segment != "..")
        if not redirect_path.startswith("/"):
            redirect_path = "/"
        redirect_url = f"/login?redirect={quote(redirect_path, safe='/')}"
        return RedirectResponse(url=redirect_url, status_code=303)

    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": f"Error {exc.status_code}: {exc.detail}"},
            status_code=exc.status_code,
        )

    from app.utils.responses import create_error_response

    error_code = _STATUS_ERROR_CODE.get(exc.status_code, "HTTP_ERROR")
    error_response = create_error_response(
        error_code=error_code,
        error_message=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Handle unexpected exceptions with appropriate response format.

    Catches any unhandled exceptions and returns a generic error response
    to prevent leaking internal details to clients.

    Args:
        request: The incoming FastAPI request.
        exc: The unexpected exception.

    Returns:
        HTML error page for browser clients or JSON error for API clients.

    """
    logger.exception("Unexpected error")
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE in accept:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "An unexpected error occurred. Please try again later."},
            status_code=500,
        )

    from app.utils.responses import create_error_response

    error_response = create_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        error_message="An unexpected error occurred. Please try again later.",
    )
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
