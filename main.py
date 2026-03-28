import logging
import sys
from fastapi.staticfiles import StaticFiles

from fastapi import FastAPI

from app.core.lifespan import lifespan
from app.api.v1.endpoints import binaries, config, models, predictions, status
from app.web.endpoints.web import router as web_router

# --- Configure logging early (before importing anything that might log) ---
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
    )

    # Mount static files (only after logging/db/config are prepped)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("✅ Static files mounted at /static")
    except Exception as e:
        logger.warning("Static files mount failed: %s", e)

    # Include routers
    app.include_router(web_router)
    app.include_router(binaries.router, prefix="/binaries")
    app.include_router(predictions.router, prefix="/predictions")
    app.include_router(models.router, prefix="/models")
    app.include_router(status.router, prefix="/status")
    app.include_router(config.router, prefix="/config")

    logger.info("✅ All routers registered.")
    return app


app = create_app()