"""JWT handler using joserfc for token generation and verification."""

import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry
from joserfc.errors import (
    JoseError,
    InvalidTokenError as JoserfcInvalidTokenError,
    DecodeError as JoserfcDecodeError,
    BadSignatureError as JoserfcBadSignatureError,
    ClaimError as JoserfcClaimError)

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
    """Handler for JWT token operations using joserfc."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
    ) -> None:
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        secret_b64 = base64.urlsafe_b64encode(secret_key.encode("utf-8")).decode("utf-8")
        self._key = OctKey.import_key({"k": secret_b64, "kty": "oct"})

    def create_access_token(
        self,
        subject: str,
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate an access token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=self.access_token_expire_minutes),
            "type": "access"
        }
        
        if extra_claims:
            _protected_claims = {"sub", "iat", "exp", "type"}
            overlap = set(extra_claims.keys()) & _protected_claims
            if overlap:
                raise ValueError(f"Cannot override protected claims: {overlap}")
            payload.update(extra_claims)
        
        token = jwt.encode({"alg": self.algorithm}, payload, self._key)
        logger.debug("Access token created for subject {}", subject)
        return token
    
    def create_refresh_token(
        self,
        subject: str,
        extra_claims: dict[str, Any] | None = None
    ) -> str:
        """Generate a refresh token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(days=self.refresh_token_expire_days),
            "type": "refresh"
        }
        
        if extra_claims:
            _protected_claims = {"sub", "iat", "exp", "type"}
            overlap = set(extra_claims.keys()) & _protected_claims
            if overlap:
                raise ValueError(f"Cannot override protected claims: {overlap}")
            payload.update(extra_claims)
        
        token = jwt.encode({"alg": self.algorithm}, payload, self._key)
        logger.debug("Refresh token created for subject {}", subject)
        return token
    
    def _validate_claims(self, claims: dict[str, Any]) -> None:
        """Validate JWT claims using JWTClaimsRegistry."""
        registry = JWTClaimsRegistry()
        try:
            registry.validate(claims)
        except JoserfcClaimError as e:
            raise InvalidTokenError(str(e)) from e

    def verify_access_token(self, token: str) -> dict[str, Any]:
        """Verify and decode an access token."""
        try:
            decoded = jwt.decode(token, self._key, algorithms=[self.algorithm])

            if decoded.claims.get("type") != "access":
                raise InvalidTokenError("Token is not an access token")

            self._validate_claims(dict(decoded.claims))

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
        """Verify and decode a refresh token."""
        try:
            decoded = jwt.decode(token, self._key, algorithms=[self.algorithm])

            if decoded.claims.get("type") != "refresh":
                raise InvalidTokenError("Token is not a refresh token")

            self._validate_claims(dict(decoded.claims))

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
            token: The JWT token to verify.

        Returns:
            Decoded token payload as a dictionary.

        Raises:
            InvalidTokenError: If the token is invalid or expired.
            DecodeError: If the token cannot be decoded.
        """
        try:
            decoded = jwt.decode(token, self._key, algorithms=[self.algorithm])

            self._validate_claims(dict(decoded.claims))

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
