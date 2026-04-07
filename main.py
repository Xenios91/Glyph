import logging
import sys

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.lifespan import lifespan
from app.core.csrf import CSRFMiddleware
from app.api.router import api_router
from app.web.endpoints.web import router as web_router

templates = Jinja2Templates(directory="templates")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("glyph_log.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Glyph API",
        description="Binary analysis and powered by machine learning",
        version="0.0.2",
        lifespan=lifespan,
        strict_content_type=True,
    )

    # Add CSRF protection middleware
    app.add_middleware(CSRFMiddleware)
    logger.info("✅ CSRF middleware added")

    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted at /static")
    except Exception as e:
        logger.warning("Static files mount failed: %s", e)

    app.include_router(api_router, prefix="/api")
    logger.info("✅ API router registered at /api")

    app.include_router(web_router)
    logger.info("✅ Web router registered")

    return app


app = create_app()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse:
    """Handle HTTP exceptions with a nice error page for web requests.
    """
    accept = request.headers.get("Accept", "")
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
    logging.error("Unexpected error: %s", exc, exc_info=True)
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
