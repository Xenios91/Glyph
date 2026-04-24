"""Authentication module for Glyph.

This module provides authentication functionality using authlib for JWT tokens
and Argon2id for password hashing.

Components:
- jwt_handler: JWT token generation and verification
- repository: User and API key database operations
- dependencies: FastAPI dependency injection for authentication
- endpoints: Authentication API endpoints
- schemas: Pydantic schemas for authentication data
- middleware: Authentication middleware
- security_logger: Security event logging utilities
"""

from app.auth.dependencies import (
    get_api_key_repository,
    get_current_active_user,
    get_current_user,
    get_db,
    get_jwt_handler,
    get_optional_user,
    get_user_repository,
    oauth2_scheme,
    require_admin_permission,
    require_write_permission,
)
from app.auth.endpoints import router as auth_router
from app.auth.jwt_handler import JWTHandler
from app.auth.middleware import AuthMiddleware
from app.auth.repository import APIKeyRepository, PasswordHasherService, UserRepository
from app.auth.schemas import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
    ChangePassword,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.auth.security_logger import (
    log_login_attempt,
    log_login_success,
    log_login_failure,
    log_logout,
    log_token_refresh,
    log_api_key_usage,
    log_permission_denied,
    log_suspicious_activity,
    log_password_change,
    log_account_lockout,
    log_account_unlock,
    log_user_registration,
    log_api_key_created,
    log_api_key_deleted,
    log_csrf_failure,
)

__all__ = [
    # Dependencies
    "get_api_key_repository",
    "get_current_active_user",
    "get_current_user",
    "get_db",
    "get_jwt_handler",
    "get_optional_user",
    "get_user_repository",
    "oauth2_scheme",
    "require_admin_permission",
    "require_write_permission",
    # Router
    "auth_router",
    # Middleware
    "AuthMiddleware",
    # Classes
    "JWTHandler",
    "APIKeyRepository",
    "PasswordHasherService",
    "UserRepository",
    # Schemas
    "APIKeyCreate",
    "APIKeyResponse",
    "APIKeyWithSecret",
    "ChangePassword",
    "RefreshTokenRequest",
    "TokenResponse",
    "UserLogin",
    "UserRegister",
    "UserResponse",
    "UserUpdate",
    # Security logging
    "log_login_attempt",
    "log_login_success",
    "log_login_failure",
    "log_logout",
    "log_token_refresh",
    "log_api_key_usage",
    "log_permission_denied",
    "log_suspicious_activity",
    "log_password_change",
    "log_account_lockout",
    "log_account_unlock",
    "log_user_registration",
    "log_api_key_created",
    "log_api_key_deleted",
    "log_csrf_failure",
]
