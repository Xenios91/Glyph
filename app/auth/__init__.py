"""Authentication module for Glyph.

This module provides authentication functionality using authlib for JWT tokens
and Argon2id for password hashing.

Components:
- jwt_handler: JWT token generation and verification
- repository: User and API key database operations
- dependencies: FastAPI dependency injection for authentication
- endpoints: Authentication API endpoints
- schemas: Pydantic schemas for authentication data
"""

from app.auth.dependencies import (
    get_current_active_user,
    get_current_user,
    get_db,
    get_jwt_handler,
    get_optional_user,
    oauth2_scheme,
)
from app.auth.endpoints import router as auth_router
from app.auth.jwt_handler import JWTHandler
from app.auth.schemas import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
    ChangePassword,
    RefreshTokenRequest,
    TokenResponse,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.auth.security_logger import is_blocked
from app.database.repository import APIKeyRepository, PasswordHasherService, UserRepository

__all__ = [
    # Schemas
    "APIKeyCreate",
    "APIKeyRepository",
    "APIKeyResponse",
    "APIKeyWithSecret",
    "ChangePassword",
    # Classes
    "JWTHandler",
    "PasswordHasherService",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserRegister",
    "UserRepository",
    "UserResponse",
    "UserUpdate",
    # Router
    "auth_router",
    # Dependencies
    "get_current_active_user",
    "get_current_user",
    "get_db",
    "get_jwt_handler",
    "get_optional_user",
    # Security
    "is_blocked",
    "oauth2_scheme",
]
