"""JWT handler using authlib for token generation and verification."""

from datetime import datetime, timedelta, timezone
from typing import Any

from authlib.jose import JsonWebToken
from authlib.jose.errors import DecodeError, InvalidTokenError, BadSignatureError


class JWTHandler:
    """Handler for JWT token operations using authlib.
    
    Provides methods for creating and verifying access and refresh tokens.
    Uses JsonWebToken from authlib.jose (v1.7.0+).
    """
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize the JWT handler.
        
        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm to use (default: HS256)
        """
        self.jwt = JsonWebToken([algorithm])
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(
        self, 
        subject: str, 
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate an access token using authlib.
        
        Args:
            subject: The subject of the token (typically user ID)
            extra_claims: Additional claims to include in the token
            
        Returns:
            Signed JWT access token string
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=15),  # Default 15 minutes
            "type": "access"
        }
        
        if extra_claims:
            payload.update(extra_claims)
        
        header = {"alg": self.algorithm, "typ": "JWT"}
        token_bytes = self.jwt.encode(header, payload, self.secret_key)
        return token_bytes.decode("utf-8")
    
    def create_refresh_token(
        self, 
        subject: str, 
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate a refresh token using authlib.
        
        Args:
            subject: The subject of the token (typically user ID)
            extra_claims: Additional claims to include in the token
            
        Returns:
            Signed JWT refresh token string
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(days=7),  # Default 7 days
            "type": "refresh"
        }
        
        if extra_claims:
            payload.update(extra_claims)
        
        header = {"alg": self.algorithm, "typ": "JWT"}
        token_bytes = self.jwt.encode(header, payload, self.secret_key)
        return token_bytes.decode("utf-8")
    
    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify and decode an access token.
        
        Args:
            token: The JWT access token to verify
            
        Returns:
            Decoded token payload as a dictionary
            
        Raises:
            InvalidTokenError: If the token is invalid or expired
            DecodeError: If the token cannot be decoded
        """
        try:
            decoded = self.jwt.decode(token, self.secret_key)
            
            # Verify token type
            if decoded.get("type") != "access":
                raise InvalidTokenError("Token is not an access token")
            
            return dict(decoded)
        except (DecodeError, InvalidTokenError, BadSignatureError):
            raise
        except Exception as e:
            raise InvalidTokenError(f"Failed to verify token: {e}")
    
    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        """Verify and decode a refresh token.
        
        Args:
            token: The JWT refresh token to verify
            
        Returns:
            Decoded token payload as a dictionary
            
        Raises:
            InvalidTokenError: If the token is invalid or expired
            DecodeError: If the token cannot be decoded
        """
        try:
            decoded = self.jwt.decode(token, self.secret_key)
            
            # Verify token type
            if decoded.get("type") != "refresh":
                raise InvalidTokenError("Token is not a refresh token")
            
            return dict(decoded)
        except (DecodeError, InvalidTokenError, BadSignatureError):
            raise
        except Exception as e:
            raise InvalidTokenError(f"Failed to verify token: {e}")
    
    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode any token (access or refresh).
        
        Args:
            token: The JWT token to verify
            
        Returns:
            Decoded token payload as a dictionary
            
        Raises:
            InvalidTokenError: If the token is invalid or expired
            DecodeError: If the token cannot be decoded
        """
        try:
            decoded = self.jwt.decode(token, self.secret_key)
            return dict(decoded)
        except (DecodeError, InvalidTokenError, BadSignatureError):
            raise
        except Exception as e:
            raise InvalidTokenError(f"Failed to verify token: {e}")
