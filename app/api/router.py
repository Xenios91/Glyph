"""API router configuration for Glyph application."""

from fastapi import APIRouter

from app.api.v1.endpoints import binaries, config, models, predictions, status

api_v1_router = APIRouter(prefix="/v1", tags=["api-v1"])

api_v1_router.include_router(binaries.router, prefix="/binaries", tags=["binaries"])
api_v1_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_v1_router.include_router(models.router, prefix="/models", tags=["models"])
api_v1_router.include_router(status.router, prefix="/status", tags=["status"])
api_v1_router.include_router(config.router, prefix="/config", tags=["config"])

api_router = APIRouter()
api_router.include_router(api_v1_router)

__all__ = ["api_router", "api_v1_router"]
