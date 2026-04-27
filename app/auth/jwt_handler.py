"""JWT handler using joserfc for token generation and verification.

Uses joserfc library (recommended replacement for deprecated authlib.jose).
"""

import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.errors import (
    JoseError,
    InvalidTokenError as JoserfcInvalidTokenError,
    DecodeError as JoserfcDecodeError,
    BadSignatureError as JoserfcBadSignatureError)

from loguru import logger



class InvalidTokenError(Exception):
    """Raised when a token is invalid."""
    pass


class DecodeError(Exception):
    """Raised when a token cannot be decoded."""
    pass


class BadSignatureError(Exception):
    """Raised when a token signature is invalid."""
    pass


class JWTHandler:
    """Handler for JWT token operations using joserfc.
    
    Provides methods for creating and verifying access and refresh tokens.
    Uses joserfc library (recommended replacement for deprecated authlib.jose).
    """
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize the JWT handler.
        
        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm to use (default: HS256)
        """
        self.algorithm = algorithm
        # Convert secret key to base64url encoded string for OctKey
        secret_b64 = base64.urlsafe_b64encode(secret_key.encode("utf-8")).decode("utf-8")
        self._key = OctKey.import_key({"k": secret_b64, "kty": "oct"})
    
    def create_access_token(
        self,
        subject: str,
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate an access token using joserfc.
        
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
        
        token = jwt.encode({"alg": self.algorithm}, payload, self._key)
        logger.debug("Access token created for subject {}", subject)
        return token
    
    def create_refresh_token(
        self,
        subject: str,
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate a refresh token using joserfc.
        
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
        
        token = jwt.encode({"alg": self.algorithm}, payload, self._key)
        logger.debug("Refresh token created for subject {}", subject)
        return token
    
    def _check_expiration(self, claims: dict[str, Any]) -> None:
        """Check if the token has expired.
        
        Args:
            claims: The token claims
            
        Raises:
            InvalidTokenError: If the token has expired
        """
        exp = claims.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            raise InvalidTokenError("Token has expired")
    
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
            decoded = jwt.decode(token, self._key)
            
            # Verify token type
            if decoded.claims.get("type") != "access":
                raise InvalidTokenError("Token is not an access token")
            
            # Check expiration
            self._check_expiration(dict(decoded.claims))
            
            logger.debug("Access token verified for subject {}", decoded.claims.get("sub"))
            return dict(decoded.claims)
        except (JoserfcBadSignatureError, JoserfcInvalidTokenError, JoserfcDecodeError, JoseError) as e:
            logger.warning("Access token verification failed: {}", type(e).__name__)
            if isinstance(e, JoserfcBadSignatureError):
                raise BadSignatureError(f"Invalid signature: {e}") from e
            raise InvalidTokenError(f"Invalid token: {e}") from e
        except Exception as e:
            logger.warning("Access token verification error: {}", type(e).__name__)
            raise InvalidTokenError(f"Failed to verify token: {e}") from e
    
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
            decoded = jwt.decode(token, self._key)
            
            # Verify token type
            if decoded.claims.get("type") != "refresh":
                raise InvalidTokenError("Token is not a refresh token")
            
            # Check expiration
            self._check_expiration(dict(decoded.claims))
            
            logger.debug("Refresh token verified for subject {}", decoded.claims.get("sub"))
            return dict(decoded.claims)
        except (JoserfcBadSignatureError, JoserfcInvalidTokenError, JoserfcDecodeError, JoseError) as e:
            logger.warning("Refresh token verification failed: {}", type(e).__name__)
            if isinstance(e, JoserfcBadSignatureError):
                raise BadSignatureError(f"Invalid signature: {e}") from e
            raise InvalidTokenError(f"Invalid token: {e}") from e
        except Exception as e:
            logger.warning("Refresh token verification error: {}", type(e).__name__)
            raise InvalidTokenError(f"Failed to verify token: {e}") from e
    
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
            decoded = jwt.decode(token, self._key)
            
            # Check expiration
            self._check_expiration(dict(decoded.claims))
            
            logger.debug("Token verified for subject {} type {}", decoded.claims.get("sub"), decoded.claims.get("type"))
            return dict(decoded.claims)
        except (JoserfcBadSignatureError, JoserfcInvalidTokenError, JoserfcDecodeError, JoseError) as e:
            logger.warning("Token verification failed: {}", type(e).__name__)
            if isinstance(e, JoserfcBadSignatureError):
                raise BadSignatureError(f"Invalid signature: {e}") from e
            raise InvalidTokenError(f"Invalid token: {e}") from e
        except Exception as e:
            logger.warning("Token verification error: {}", type(e).__name__)
            raise InvalidTokenError(f"Failed to verify token: {e}") from e
