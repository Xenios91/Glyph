"""Authentication dependencies for FastAPI."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import JWTHandler
from app.database.repository import APIKeyRepository
from app.auth.security_logger import log_api_key_usage
from app.config.settings import get_settings
from app.database.models import User
from app.database.session_handler import get_async_session, close_async_session
from loguru import logger
from app.utils.request_context import set_request_context



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_jwt_handler() -> JWTHandler:
    """Create a JWTHandler instance from application settings.

    FastAPI dependency that provides a configured JWT handler for
    token generation and verification.

    Returns:
        Configured JWTHandler instance.
    """
    settings = get_settings()
    return JWTHandler(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for auth, committing on success."""
    session = await get_async_session("auth")
    try:
        yield session
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        logger.exception("Database session error, rolling back")
        raise
    finally:
        await close_async_session(session)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)]) -> User:
    """Get the current authenticated user from JWT token or API key."""
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        token = request.cookies.get("access_token_cookie")

    if not token:
        logger.warning("Authentication failed: missing token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"})

    user_id = None
    try:
        payload = jwt_handler.verify_access_token(token)
        user_id = payload.get("sub")
        if user_id:
            user_id = int(user_id)
            logger.bind(user_id=user_id).debug("JWT token verified")
    except Exception:
        logger.debug("JWT verification failed, trying API key lookup")
        api_key_repo = APIKeyRepository(db)
        api_key_record = await api_key_repo.verify_and_get(token)

        if api_key_record:
            logger.bind(user_id=api_key_record.user_id).debug("API key verified")
            ip_address = request.client.host if request.client else None
            log_api_key_usage(
                user_id=api_key_record.user_id,
                api_key_prefix=api_key_record.key_prefix,
                endpoint=request.url.path,
                ip_address=ip_address)
            user = await db.get(User, api_key_record.user_id)
            if not user or not user.is_active:
                logger.bind(user_id=api_key_record.user_id).warning("Authentication failed: user not found or inactive")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                    headers={"WWW-Authenticate": "Bearer"})
            set_request_context(user_id=user.id, username=user.username, clear_unset=False)
            return user
        else:
            logger.warning("Authentication failed: invalid credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"})

    if not user_id:
        logger.warning("Authentication failed: empty token subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"})

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        logger.bind(user_id=user_id).warning("Authentication failed: user not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"})

    set_request_context(user_id=user.id, username=user.username, clear_unset=False)
    logger.bind(user_id=user.id).debug("User authenticated")
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Get the current authenticated user, ensuring they are active.

    Dependency that wraps get_current_user and additionally checks
    that the user account is not disabled.

    Returns:
        The active User object.

    Raises:
        HTTPException: 403 if the user account is disabled.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    return current_user


async def get_optional_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)]) -> User | None:
    """Get the current user if authenticated, otherwise return None.

    Unlike get_current_user, this dependency does not raise an exception
    when no valid credentials are present, making it suitable for optional
    authentication on endpoints that support both authenticated and
    anonymous access.

    Args:
        request: The FastAPI request object.
        db: Database session.
        jwt_handler: JWT handler instance.

    Returns:
        The User object if authenticated, None otherwise.
    """
    auth_header = request.headers.get("Authorization")
    token = None

    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        token = request.cookies.get("access_token_cookie")

    if not token:
        return None

    user_id = None
    try:
        payload = jwt_handler.verify_access_token(token)
        user_id = payload.get("sub")
        if user_id:
            user_id = int(user_id)
    except Exception:
        logger.debug("JWT verification failed, trying API key lookup")
        api_key_repo = APIKeyRepository(db)
        api_key_record = await api_key_repo.verify_and_get(token)

        if api_key_record:
            user = await db.get(User, api_key_record.user_id)
            if user and user.is_active:
                set_request_context(user_id=user.id, username=user.username, clear_unset=False)
                return user
        return None

    if not user_id:
        return None

    user = await db.get(User, user_id)
    if user and user.is_active:
        set_request_context(user_id=user.id, username=user.username, clear_unset=False)
        return user

    return None


