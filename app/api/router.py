"""API router configuration for Glyph application.

Provides a centralized API router with versioning support.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import binaries, config, models, predictions, status

# Create API v1 router
api_v1_router = APIRouter(prefix="/v1", tags=["api-v1"])

# Include all v1 endpoints
api_v1_router.include_router(binaries.router, prefix="/binaries", tags=["binaries"])
api_v1_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_v1_router.include_router(models.router, prefix="/models", tags=["models"])
api_v1_router.include_router(status.router, prefix="/status", tags=["status"])
api_v1_router.include_router(config.router, prefix="/config", tags=["config"])

# Main API router (can include multiple versions)
api_router = APIRouter()
api_router.include_router(api_v1_router)

__all__ = ["api_router", "api_v1_router"]
