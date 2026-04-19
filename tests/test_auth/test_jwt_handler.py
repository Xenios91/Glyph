"""Tests for JWT handler."""

import pytest
from datetime import datetime, timezone, timedelta
from authlib.jose.errors import InvalidTokenError

from app.auth.jwt_handler import JWTHandler


@pytest.fixture
def jwt_handler():
    """Create a JWT handler for testing."""
    return JWTHandler(secret_key="test_secret_key", algorithm="HS256")


class TestJWTHandler:
    """Test cases for JWTHandler."""

    def test_create_access_token(self, jwt_handler):
        """Test creating an access token."""
        token = jwt_handler.create_access_token("123")
        assert isinstance(token, str)
        assert len(token) > 0
        # Token should have three parts (header.payload.signature)
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_refresh_token(self, jwt_handler):
        """Test creating a refresh token."""
        token = jwt_handler.create_refresh_token("123")
        assert isinstance(token, str)
        assert len(token) > 0
        parts = token.split(".")
        assert len(parts) == 3

    def test_verify_access_token(self, jwt_handler):
        """Test verifying an access token."""
        token = jwt_handler.create_access_token("123")
        payload = jwt_handler.verify_access_token(token)
        
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_refresh_token(self, jwt_handler):
        """Test verifying a refresh token."""
        token = jwt_handler.create_refresh_token("123")
        payload = jwt_handler.verify_refresh_token(token)
        
        assert payload["sub"] == "123"
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_access_token_with_extra_claims(self, jwt_handler):
        """Test creating and verifying token with extra claims."""
        extra_claims = {"permissions": ["read", "write"], "role": "admin"}
        token = jwt_handler.create_access_token("123", extra_claims=extra_claims)
        payload = jwt_handler.verify_access_token(token)
        
        assert payload["sub"] == "123"
        assert payload["permissions"] == ["read", "write"]
        assert payload["role"] == "admin"

    def test_verify_wrong_token_type(self, jwt_handler):
        """Test that wrong token type is rejected."""
        # Try to verify refresh token as access token
        token = jwt_handler.create_refresh_token("123")
        with pytest.raises(InvalidTokenError):
            jwt_handler.verify_access_token(token)
        
        # Try to verify access token as refresh token
        token = jwt_handler.create_access_token("123")
        with pytest.raises(InvalidTokenError):
            jwt_handler.verify_refresh_token(token)

    def test_verify_invalid_token(self, jwt_handler):
        """Test that invalid tokens are rejected."""
        with pytest.raises(InvalidTokenError):
            jwt_handler.verify_access_token("invalid.token.here")

    def test_verify_expired_token(self, jwt_handler):
        """Test that expired tokens are rejected."""
        # Create a token with immediate expiration
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "123",
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=15),
            "type": "access"
        }
        header = {"alg": "HS256", "typ": "JWT"}
        token = jwt_handler.jwt.encode(header, payload, jwt_handler.secret_key).decode("utf-8")
        
        with pytest.raises(InvalidTokenError):
            jwt_handler.verify_access_token(token)

    def test_verify_token(self, jwt_handler):
        """Test the generic verify_token method."""
        # Should work for both access and refresh tokens
        access_token = jwt_handler.create_access_token("123")
        payload = jwt_handler.verify_token(access_token)
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        
        refresh_token = jwt_handler.create_refresh_token("456")
        payload = jwt_handler.verify_token(refresh_token)
        assert payload["sub"] == "456"
        assert payload["type"] == "refresh"
