"""Request tracing middleware for Glyph application.

This module provides request ID generation and propagation across
the application for better logging and debugging.
"""

import uuid
from typing import Any, Callable, Dict, List, cast

from starlette.types import Receive, Send, Scope, Message

from loguru import logger

from app.utils.request_context import set_request_context, clear_request_context


class RequestIDMiddleware:
    """ASGI middleware for request ID tracing.
    
    This middleware:
    - Extracts request ID from incoming request headers
    - Generates a new request ID if not present
    - Stores the request ID in request context
    - Adds the request ID to response headers
    - Clears the request context after the request is complete
    
    Usage:
        app.add_middleware(RequestIDMiddleware)
    """

    def __init__(self, app: Callable[[Scope, Receive, Send], Any], header_name: str = "X-Request-ID") -> None:
        """Initialize the middleware.
        
        Args:
            app: The ASGI application.
            header_name: The header name to use for request ID.
        """
        self.app = app
        self.header_name = header_name.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request.

        Args:
            scope: The ASGI scope dictionary.
            receive: Awaitable callable for receiving events.
            send: Awaitable callable for sending events.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        request_id = self._get_or_create_request_id(scope)

        # Set request context - clear any leftover state from previous request
        set_request_context(request_id=request_id, clear_unset=True)

        try:
            # Wrap send to add request ID to response headers
            wrapped_send = self._create_wrapped_send(send, request_id)
            await self.app(scope, receive, wrapped_send)
        except Exception:
            logger.exception(
                "Request tracing middleware error for request_id={}", request_id)
            raise
        finally:
            # Clear request context after request is complete
            clear_request_context()

    def _get_or_create_request_id(self, scope: Scope) -> str:
        """Get request ID from headers or create a new one.
        
        Args:
            scope: The ASGI scope dictionary.
            
        Returns:
            The request ID string.
        """
        headers = dict(scope.get("headers", []))
        
        # Try to get request ID from headers
        request_id = headers.get(self.header_name)
        
        if request_id:
            # Decode bytes to string if necessary
            if isinstance(request_id, bytes):
                request_id = request_id.decode("utf-8")
            return request_id
        
        # Generate new request ID
        return str(uuid.uuid4())

    def _create_wrapped_send(
        self,
        send: Send,
        request_id: str,
    ) -> Send:
        """Create a wrapped send function that adds request ID to response headers.
        
        Args:
            send: The original send callable.
            request_id: The request ID to add to response headers.
            
        Returns:
            Wrapped send callable.
        """
        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Add request ID to response headers
                raw_headers = message.get("headers", [])
                # Convert to list of lists if needed
                if isinstance(raw_headers, dict):
                    headers_dict: Dict[str, Any] = cast(Dict[str, Any], raw_headers)
                    headers: List[List[Any]] = [[k, v] for k, v in headers_dict.items()]
                else:
                    headers = list(raw_headers) if raw_headers else []
                
                # Add request ID header
                headers.append([self.header_name.encode(), request_id.encode()])
                message["headers"] = headers
            
            await send(message)
        
        return wrapped_send


def get_request_id_from_scope(scope: dict[str, Any], header_name: str = "X-Request-ID") -> str | None:
    """Get request ID from ASGI scope.
    
    Args:
        scope: The ASGI scope dictionary.
        header_name: The header name to use for request ID.
        
    Returns:
        The request ID if present, None otherwise.
    """
    headers = dict(scope.get("headers", []))
    request_id = headers.get(header_name.lower())
    
    if request_id:
        if isinstance(request_id, bytes):
            return request_id.decode("utf-8")
        if isinstance(request_id, str):
            return request_id
    
    return None
