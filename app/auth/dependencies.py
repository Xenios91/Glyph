"""Authentication dependencies for FastAPI."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_handler import JWTHandler
from app.auth.repository import UserRepository, APIKeyRepository
from app.config.settings import get_settings
from app.database.models import User
from app.database.session_handler import get_async_session, close_async_session
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


# Initialize OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_jwt_handler() -> JWTHandler:
    """Get the JWT handler instance.
    
    Returns:
        Configured JWTHandler instance
    """
    settings = get_settings()
    return JWTHandler(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for auth.
    
    Yields:
        AsyncSession for the auth database
    """
    session = await get_async_session("auth")
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error("Database session rolled back: %s", e, exc_info=True)
        raise
    finally:
        await close_async_session(session)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
) -> User:
    """Get the current authenticated user from JWT token or API key.
    
    Checks for authentication in the following order:
    1. Bearer token in Authorization header (JWT or API key)
    2. Access token cookie (for web UI)
    
    Args:
        request: FastAPI request object
        db: Database session
        jwt_handler: JWT handler instance
        
    Returns:
        Authenticated User instance
        
    Raises:
        HTTPException: If authentication fails
    """
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    
    # If no header, try cookie
    if not token:
        token = request.cookies.get("access_token_cookie")
    
    if not token:
        logger.warning("Authentication failed: no token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Try to verify as JWT token first
    user_id = None
    try:
        payload = jwt_handler.verify_access_token(token)
        user_id = payload.get("sub")
        if user_id:
            user_id = int(user_id)
            logger.info("JWT token verified for user_id=%s", user_id)
    except Exception as jwt_error:
        logger.debug("JWT verification failed, trying API key: %s", jwt_error)
        # If JWT verification fails, try API key
        api_key_repo = APIKeyRepository(db)
        api_key_record = await api_key_repo.verify_and_get(token)
        
        if api_key_record:
            logger.info("API key verified for user_id=%s", api_key_record.user_id)
            user = await db.get(User, api_key_record.user_id)
            if not user or not user.is_active:
                logger.warning("Authentication failed: user_id=%s not found or inactive (API key)", api_key_record.user_id)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user
        else:
            logger.warning("Authentication failed: invalid API key")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Get user from database
    if not user_id:
        logger.warning("Authentication failed: invalid token payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        logger.warning("Authentication failed: user_id=%s not found or inactive", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info("User authenticated successfully: user_id=%s, username=%s", user.id, user.username)
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current active user.
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Active User instance
        
    Raises:
        HTTPException: If user is not active
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
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
) -> User | None:
    """Get the current user if authenticated, otherwise return None.
    
    Args:
        request: FastAPI request object
        db: Database session
        jwt_handler: JWT handler instance
        
    Returns:
        User instance if authenticated, None otherwise
    """
    # Try Authorization header first
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    
    # If no header, try cookie
    if not token:
        token = request.cookies.get("access_token_cookie")
    
    if not token:
        return None
    
    # Try to verify as JWT token first
    user_id = None
    try:
        payload = jwt_handler.verify_access_token(token)
        user_id = payload.get("sub")
        if user_id:
            user_id = int(user_id)
    except Exception:
        # If JWT verification fails, try API key
        api_key_repo = APIKeyRepository(db)
        api_key_record = await api_key_repo.verify_and_get(token)
        
        if api_key_record:
            user = await db.get(User, api_key_record.user_id)
            if user and user.is_active:
                return user
        return None
    
    # Get user from database
    if not user_id:
        return None
    
    user = await db.get(User, user_id)
    if user and user.is_active:
        return user
    
    return None


async def require_write_permission(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Require write permission for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User instance if they have write permission
        
    Raises:
        HTTPException: If user lacks write permission
    """
    import json
    
    permissions = json.loads(current_user.permissions or "[]")
    if "write" not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write permission required"
        )
    return current_user


async def require_admin_permission(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Require admin permission for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User instance if they have admin permission
        
    Raises:
        HTTPException: If user lacks admin permission
    """
    import json
    
    permissions = json.loads(current_user.permissions or "[]")
    if "admin" not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required"
        )
    return current_user


async def get_user_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    """Get the user repository instance.
    
    Args:
        db: Database session
        
    Returns:
        UserRepository instance
    """
    return UserRepository(db)


async def get_api_key_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> APIKeyRepository:
    """Get the API key repository instance.
    
    Args:
        db: Database session
        
    Returns:
        APIKeyRepository instance
    """
    return APIKeyRepository(db)
