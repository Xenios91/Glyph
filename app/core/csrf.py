"""CSRF Protection for FastAPI application using Starlette middleware.

This module provides CSRF token generation and validation for state-changing requests.
Uses session-based CSRF tokens with SameSite cookie policy.
"""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_403_FORBIDDEN


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware to protect against Cross-Site Request Forgery (CSRF) attacks.

    Generates a CSRF token on first request and validates it on state-changing requests
    (POST, PUT, DELETE, PATCH). The token is stored in a secure, HttpOnly cookie.
    """

    # HTTP methods that require CSRF validation
    UNSAFE_METHODS: set[str] = {"POST", "PUT", "DELETE", "PATCH"}

    # Cookie name for CSRF token
    CSRF_COOKIE_NAME: str = "csrf_token"

    # Header name for CSRF token
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip CSRF validation for static files and API documentation
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        # Generate or retrieve CSRF token
        csrf_token = self._get_or_create_token(request)

        # For unsafe methods, validate the CSRF token
        if request.method in self.UNSAFE_METHODS:
            if not await self._validate_csrf_token(request, csrf_token):
                # Return 403 Forbidden for invalid CSRF tokens
                return Response(
                    content='{"detail": "CSRF token missing or invalid"}',
                    status_code=HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )

        # Process the request
        response = await call_next(request)

        # Set the CSRF token cookie in the response
        self._set_csrf_cookie(response, csrf_token)

        return response

    def _is_excluded_path(self, path: str) -> bool:
        """Check if the path should be excluded from CSRF validation.

        Args:
            path: The request path to check.

        Returns:
            True if the path should be excluded, False otherwise.
        """
        excluded_paths: set[str] = {
            "/static",
            "/docs",
            "/redoc",
            "/openapi.json",
        }
        return any(path.startswith(excluded) for excluded in excluded_paths)

    def _get_or_create_token(self, request: Request) -> str:
        """Get existing CSRF token from cookie or generate a new one.

        Args:
            request: The incoming request.

        Returns:
            The CSRF token string.
        """
        token = request.cookies.get(self.CSRF_COOKIE_NAME)

        if not token or not self._validate_token_format(token):
            token = self._generate_token()

        return token

    def _generate_token(self) -> str:
        """Generate a new cryptographically secure CSRF token.

        Returns:
            A new CSRF token string.
        """
        return secrets.token_urlsafe(32)

    def _validate_token_format(self, token: str) -> bool:
        """Validate that a token has the expected format.

        Args:
            token: The token to validate.

        Returns:
            True if the token format is valid, False otherwise.
        """
        return isinstance(token, str) and len(token) >= 32

    async def _validate_csrf_token(self, request: Request, expected_token: str) -> bool:
        """Validate the CSRF token from the request.

        The token can be sent either in a header or as a form field.

        Args:
            request: The incoming request.
            expected_token: The expected CSRF token from the cookie.

        Returns:
            True if the token is valid, False otherwise.
        """
        # Check header first
        token_from_header = request.headers.get(self.CSRF_HEADER_NAME)
        if token_from_header and self._secure_compare(
            token_from_header, expected_token
        ):
            return True

        # Check form data for POST requests with form content type
        content_type = request.headers.get("content-type", "")
        if (
            "application/x-www-form-urlencoded" in content_type
            or "multipart/form-data" in content_type
        ):
            try:
                form_data = await request.form()
                token_from_form = form_data.get(self.CSRF_COOKIE_NAME)
                # Ensure token_from_form is a string before comparing
                if isinstance(token_from_form, str) and self._secure_compare(
                    token_from_form, expected_token
                ):
                    return True
            except Exception:
                # If we can't parse form data, fall through to return False
                pass

        return False

    def _secure_compare(self, token1: str, token2: str) -> bool:
        """Perform a timing-safe comparison of two tokens.

        Args:
            token1: First token to compare.
            token2: Second token to compare.

        Returns:
            True if tokens match, False otherwise.
        """
        return secrets.compare_digest(token1.encode(), token2.encode())

    def _set_csrf_cookie(self, response: Response, token: str) -> None:
        """Set the CSRF token cookie in the response.

        Args:
            response: The response to add the cookie to.
            token: The CSRF token to set.
        """
        response.set_cookie(
            key=self.CSRF_COOKIE_NAME,
            value=token,
            httponly=False,
            samesite="strict",  # Prevent cross-site requests
            secure=False,  # TODO with TLS
            max_age=86400,  # 24 hours
        )


def get_csrf_token_from_cookie(request: Request) -> str | None:
    """Get the CSRF token from the request cookie.

    This helper function can be used in endpoints to expose the token
    to JavaScript clients for AJAX requests.

    Args:
        request: The incoming request.

    Returns:
        The CSRF token if present, None otherwise.
    """
    return request.cookies.get(CSRFMiddleware.CSRF_COOKIE_NAME)
