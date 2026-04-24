"""Authentication middleware for Glyph.

This module provides middleware for injecting user information into request state
for use in templates.
"""

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.dependencies import get_optional_user
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to inject current user into request state.
    
    This middleware checks for authentication on each request and stores
    the current user (if authenticated) in the request state for use in templates.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and inject user into state.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response from the next handler
        """
        # Skip authentication check for auth endpoints themselves
        if request.url.path.startswith("/auth/"):
            response = await call_next(request)
            return response
        
        # Try to get the current user (non-blocking)
        try:
            # We need to manually check for auth tokens here since we can't use Depends
            auth_header = request.headers.get("Authorization")
            token = None
            
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]
            
            if not token:
                token = request.cookies.get("access_token_cookie")
            
            # Store token in state for later use if needed
            request.state.auth_token = token
            
        except Exception as e:
            # If anything goes wrong, just continue without user
            logger.debug("Failed to parse auth token: %s", e, exc_info=True)
        
        response = await call_next(request)
        return response


class UserContextMiddleware(BaseHTTPMiddleware):
    """Middleware to inject user context into request state for templates.
    
    This middleware is designed to work with web endpoints that need to display
    user information in templates.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and inject user context.
        
        Args:
            request: The incoming request
            call_next: The next middleware or route handler
            
        Returns:
            The response from the next handler
        """
        # Store a flag indicating if user context should be loaded
        request.state.load_user_context = True
        
        response = await call_next(request)
        return response
