from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.lifespan import lifespan
from app.core.csrf import CSRFMiddleware
from app.core.request_tracing import RequestIDMiddleware
from app.api.router import api_router
from app.web.endpoints.web import router as web_router
from app.auth.endpoints import router as auth_router
from app.utils.jinja_utils import configure_jinja2_templates
from app.utils.logging_config import setup_logging_from_config, get_logger

templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)

# Set up logging from config
setup_logging_from_config()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Glyph API",
        description="Binary analysis and powered by machine learning",
        version="0.0.2",
        lifespan=lifespan,
        strict_content_type=True,
    )

    # Add Request ID tracing middleware (must be first to capture all requests)
    app.add_middleware(RequestIDMiddleware)
    logger.info("✅ Request ID middleware added")

    # Add CSRF protection middleware
    app.add_middleware(CSRFMiddleware)
    logger.info("✅ CSRF middleware added")

    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted at /static")
    except Exception as e:
        logger.warning("Static files mount failed: %s", e)

    # Include auth router
    app.include_router(auth_router)
    logger.info("✅ Auth router registered at /auth")

    app.include_router(api_router, prefix="/api")
    logger.info("✅ API router registered at /api")

    app.include_router(web_router)
    logger.info("✅ Web router registered")

    return app


app = create_app()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse | RedirectResponse:
    """Handle HTTP exceptions with redirect to login for 401 on web requests.
    """
    accept = request.headers.get("Accept", "")
    
    # Redirect to login for 401 on web requests
    if exc.status_code == 401 and "text/html" in accept:
        redirect_url = "/login?redirect=" + request.url.path
        return RedirectResponse(url=redirect_url, status_code=303)
    
    if "text/html" in accept:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": f"Error {exc.status_code}: {exc.detail}"
            },
            status_code=exc.status_code,
        )
    # Return JSON for API requests
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail} if isinstance(exc.detail, str) else exc.detail
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """Handle unexpected exceptions with a nice error page for web requests.
    """
    logger.error("Unexpected error: %s", exc, exc_info=True)
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
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
