"""Authentication endpoints for Glyph."""

from typing import Annotated

from authlib.jose.errors import DecodeError
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_active_user,
    get_db,
    get_jwt_handler,
)
from app.auth.jwt_handler import JWTHandler
from app.auth.repository import APIKeyRepository, UserRepository
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
from app.config.settings import get_settings
from app.database.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Created user information
        
    Raises:
        HTTPException: If username or email already exists
    """
    user_repo = UserRepository(db)
    
    # Check if username exists
    existing_user = await user_repo.get_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    existing_email = await user_repo.get_by_email(user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with default permissions
    user = await user_repo.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        permissions=["read"]
    )
    
    return UserResponse.model_validate(user)


@router.post("/token")
async def login(
    request: Request,
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
) -> Response:
    """Authenticate user and return tokens.
    
    Args:
        request: FastAPI request object
        credentials: Login credentials
        db: Database session
        jwt_handler: JWT handler instance
        
    Returns:
        Response with access and refresh tokens and cookies
        
    Raises:
        HTTPException: If credentials are invalid
    """
    user_repo = UserRepository(db)
    user = await user_repo.verify_credentials(credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Generate tokens
    access_token = jwt_handler.create_access_token(str(user.id))
    refresh_token = jwt_handler.create_refresh_token(str(user.id))
    
    # Create response with cookies
    settings = get_settings()
    response = Response(
        content=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        ).model_dump_json(),
        media_type="application/json"
    )
    
    response.set_cookie(
        key="access_token_cookie",
        value=access_token,
        httponly=True,
        secure=settings.oauth2_enabled,
        samesite="strict",
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token_cookie",
        value=refresh_token,
        httponly=True,
        secure=settings.oauth2_enabled,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )
    
    return response


@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    jwt_handler: Annotated[JWTHandler, Depends(get_jwt_handler)],
) -> Response:
    """Refresh access token using refresh token.
    
    Args:
        request: Refresh token request
        db: Database session
        jwt_handler: JWT handler instance
        
    Returns:
        New access and refresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        payload = jwt_handler.verify_refresh_token(request.refresh_token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        user_id = int(user_id)
    except (ValueError, TypeError, DecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Generate new tokens
    new_access_token = jwt_handler.create_access_token(str(user.id))
    new_refresh_token = jwt_handler.create_refresh_token(str(user.id))
    
    return Response(
        content=TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        ).model_dump_json(),
        media_type="application/json"
    )


@router.post("/logout")
@router.get("/logout")
async def logout(request: Request) -> Response:
    """Logout user by clearing cookies.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Redirect to home for web requests, JSON for API requests
    """
    response = Response()
    response.delete_cookie("access_token_cookie")
    response.delete_cookie("refresh_token_cookie")
    
    # Check if this is a web request (HTML) or API request
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        # Redirect to home page for web requests
        from fastapi.responses import RedirectResponse
        redirect = RedirectResponse(url="/", status_code=303)
        redirect.delete_cookie("access_token_cookie")
        redirect.delete_cookie("refresh_token_cookie")
        return redirect
    
    # Return JSON for API requests
    return Response(
        content='{"message": "Logged out successfully"}',
        media_type="application/json"
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user information
    """
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    password_data: ChangePassword,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Change user password.
    
    Args:
        password_data: Password change data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If current password is incorrect
    """
    user_repo = UserRepository(db)
    
    # Verify current password
    if not user_repo.password_hasher.verify_password(
        password_data.current_password,
        current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Change password
    await user_repo.change_password(current_user.id, password_data.new_password)
    
    return {"message": "Password changed successfully"}


@router.post("/update-profile", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Update user profile.
    
    Args:
        update_data: Profile update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated user information
    """
    user_repo = UserRepository(db)
    user = await user_repo.update_user(
        current_user.id,
        full_name=update_data.full_name,
        email=update_data.email
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[APIKeyResponse]:
    """List all API keys for current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of API keys
    """
    api_key_repo = APIKeyRepository(db)
    keys = await api_key_repo.get_user_api_keys(current_user.id)
    
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.post("/api-keys", response_model=APIKeyWithSecret, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> APIKeyWithSecret:
    """Create a new API key.
    
    Args:
        key_data: API key creation data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created API key with secret (only shown once)
    """
    api_key_repo = APIKeyRepository(db)
    api_key_record, secret = await api_key_repo.create_api_key(
        user_id=current_user.id,
        name=key_data.name,
        permissions=key_data.permissions,
        expires_days=key_data.expires_days
    )
    
    return APIKeyWithSecret(
        **APIKeyResponse.model_validate(api_key_record).model_dump(),
        secret=secret
    )


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """Delete an API key.
    
    Args:
        key_id: API key ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If API key not found or doesn't belong to user
    """
    api_key_repo = APIKeyRepository(db)
    api_key_record = await api_key_repo.get_by_id(key_id)
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    if api_key_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this API key"
        )
    
    await api_key_repo.delete_api_key(key_id)
    
    return {"message": "API key deleted successfully"}
