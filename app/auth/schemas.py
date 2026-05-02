"""Pydantic schemas for authentication."""

import re
from datetime import datetime
import json
from typing import Any, cast

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_password_complexity(password: str) -> str:
    """Validate password meets complexity requirements.
    
    Requires at least 3 of 4 character classes: uppercase, lowercase, digits, special.
    
    Args:
        password: The password to validate.
        
    Returns:
        The validated password.
        
    Raises:
        ValueError: If password does not meet complexity requirements.
    """
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'[0-9]', password))
    has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password))
    classes = sum([has_upper, has_lower, has_digit, has_special])
    if classes < 3:
        raise ValueError(
            "Password must contain at least 3 of 4 character types: "
            "uppercase, lowercase, digits, special characters"
        )
    return password


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    
    username: str = Field(..., min_length=3, max_length=64, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    full_name: str | None = Field(None, max_length=128, description="Full name")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class UserRegister(BaseModel):
    """Schema for user registration."""
    
    username: str = Field(..., min_length=3, max_length=64, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    full_name: str | None = Field(None, max_length=128, description="Full name")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class UserLogin(BaseModel):
    """Schema for user login."""
    
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Schema for token response."""
    
    access_token: str = Field(..., description="Access token")
    refresh_token: str = Field(..., description="Refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """Schema for user response."""
    
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: str | None = Field(None, description="Full name")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    
    full_name: str | None = Field(None, max_length=128, description="Full name")
    email: EmailStr | None = Field(None, description="Email address")


class ChangePassword(BaseModel):
    """Schema for changing password."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)


class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    
    name: str = Field(..., min_length=1, max_length=128, description="API key name")
    permissions: list[str] = Field(default=["read"], description="List of permissions")
    expires_days: int | None = Field(None, ge=1, le=365, description="Expiration in days")


class APIKeyResponse(BaseModel):
    """Schema for API key response."""
    
    id: int = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key_prefix: str = Field(..., description="First 8 characters of the key")
    permissions: list[str] = Field(..., description="List of permissions")
    expires_at: datetime | None = Field(None, description="Expiration timestamp")
    is_active: bool = Field(..., description="Whether key is active")
    last_used_at: datetime | None = Field(None, description="Last used timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    @field_validator("permissions", mode="before")
    @classmethod
    def parse_permissions(cls, v: Any) -> list[str]:
        """Parse permissions from JSON string to list."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in cast(list[Any], parsed)]
                return []
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return [str(item) for item in cast(list[Any], v)]
        return []
    
    model_config = {"from_attributes": True}


class APIKeyWithSecret(APIKeyResponse):
    """Schema for API key response with the actual secret (only shown once)."""
    
    secret: str = Field(..., description="The actual API key secret")


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""
    
    refresh_token: str = Field(..., description="Refresh token")
