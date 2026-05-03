from typing import Any, Awaitable, Callable


from loguru import logger

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from markupsafe import escape

from app.core.lifespan import lifespan
from app.core.csrf import CSRFMiddleware
from app.core.request_tracing import RequestIDMiddleware
from app.api.router import api_router
from app.web.endpoints.web import router as web_router
from app.auth.endpoints import router as auth_router
from app.utils.jinja_utils import configure_jinja2_templates
from app.utils.logging_config import setup_logging_from_config

templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)

# Set up logging from config
setup_logging_from_config()


# --- Content Security Policy Middleware (pure ASGI) ---
class CSPMiddleware:
    """Middleware to add Content-Security-Policy headers to responses.

    Uses pure ASGI interface to avoid threading issues with Starlette's
    app.middleware("http") decorator that runs call_next in a thread pool,
    which blocks responses when background tasks are used.
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

    SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"geolocation=(), camera=(), microphone=()"),
    ]

    def __init__(
        self,
        app: Callable[[Any, Any, Any], Awaitable[None]],
    ) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((b"content-security-policy", self.CSP_HEADER.encode("utf-8")))
                headers.extend(self.SECURITY_HEADERS)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# --- Create Application ---
def create_app() -> FastAPI:
    app = FastAPI(
        title="Glyph API",
        description="Binary analysis powered by machine learning",
        version="0.1.0",
        lifespan=lifespan,
        strict_content_type=True,
    )

    # Add Request ID tracing middleware (must be first to capture all requests)
    # Respect the request_tracing.enabled config option
    from app.config.settings import get_settings
    settings = get_settings()
    if settings.logging.request_tracing.enabled:
        app.add_middleware(RequestIDMiddleware)
        logger.info("Middleware registered: RequestIDMiddleware")
    else:
        logger.info("RequestIDMiddleware disabled via config")

    # Add CSRF protection middleware
    app.add_middleware(CSRFMiddleware)
    logger.info("Middleware registered: CSRFMiddleware")

    # Add Content Security Policy headers (pure ASGI, no threading)
    app.add_middleware(CSPMiddleware)
    logger.info("Middleware registered: CSPMiddleware")

    # Add CORS middleware (Starlette's built-in CORSMiddleware)
    # Security-sensitive configuration kept explicit to prevent misconfiguration.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
        allow_credentials=False,
        max_age=86400,
    )
    logger.info("Middleware registered: CORSMiddleware")

    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("Static files mounted at /static")
    except Exception as e:
        logger.warning("Static files mount failed: {}", e)

    # Include auth router
    app.include_router(auth_router)
    logger.info("Router registered: auth at /auth")

    app.include_router(api_router, prefix="/api")
    logger.info("Router registered: api at /api")

    app.include_router(web_router)
    logger.info("Router registered: web")

    return app


app = create_app()


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    """Serve the favicon at root level."""
    return FileResponse("static/favicon.ico")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse | RedirectResponse:
    """Handle HTTP exceptions with redirect to login for 401 on web requests.
    """
    # Log 5xx at WARNING, 4xx at DEBUG for visibility
    level = "WARNING" if exc.status_code >= 500 else "DEBUG"
    logger.log(
        level,
        "HTTP error {}: {}", exc.status_code, exc.detail,
    )

    accept = request.headers.get("Accept", "")
    
    # Redirect to login for 401 on web requests
    if exc.status_code == 401 and "text/html" in accept:
        # Sanitize redirect path to prevent open redirect attacks
        # Only allow relative paths starting with /
        redirect_path = request.url.path
        if not redirect_path.startswith("/"):
            redirect_path = "/"
        # Remove any double-dot segments to prevent path traversal
        redirect_path = "/".join(segment for segment in redirect_path.split("/") if segment and segment != "..")
        if not redirect_path.startswith("/"):
            redirect_path = "/"
        redirect_url = f"/login?redirect={redirect_path}"
        return RedirectResponse(url=redirect_url, status_code=303)
    
    if "text/html" in accept:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "message": f"Error {exc.status_code}: {escape(str(exc.detail))}"
            },
            status_code=exc.status_code,
        )
    # Return JSON for API requests
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Handle unexpected exceptions with a nice error page for web requests.
    """
    logger.exception("Unexpected error")
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "message": "An unexpected error occurred. Please try again later."
            },
            status_code=500,
        )
    # Return JSON for API requests
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
