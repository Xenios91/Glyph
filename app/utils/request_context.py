"""Request context management for Glyph application.

This module provides thread-local storage for request-specific data
that can be accessed throughout the request lifecycle.
"""

import threading
from contextvars import ContextVar
from typing import Any


# Thread-local storage for request context
_request_context = threading.local()

# Async-compatible context variables
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
_username_var: ContextVar[str | None] = ContextVar("username", default=None)


class RequestContext:
    """Request context for storing request-specific data.
    
    This class provides a unified interface for accessing request context
    data in both synchronous and asynchronous contexts.
    """
    
    def __init__(self):
        self._request_id: str | None = None
        self._user_id: int | None = None
        self._username: str | None = None
    
    @property
    def request_id(self) -> str | None:
        """Get the request ID.
        
        Returns:
            The request ID if set, None otherwise.
        """
        # Try context var first (async)
        try:
            value = _request_id_var.get()
            if value is not None:
                return value
        except LookupError:
            pass
        
        # Fall back to thread-local (sync)
        if hasattr(_request_context, 'context'):
            return _request_context.context._request_id
        
        return self._request_id
    
    @request_id.setter
    def request_id(self, value: str | None) -> None:
        """Set the request ID.
        
        Args:
            value: The request ID to set.
        """
        self._request_id = value
        _request_id_var.set(value)
        if hasattr(_request_context, 'context'):
            _request_context.context._request_id = value
    
    @property
    def user_id(self) -> int | None:
        """Get the user ID.
        
        Returns:
            The user ID if set, None otherwise.
        """
        # Try context var first (async)
        try:
            value = _user_id_var.get()
            if value is not None:
                return value
        except LookupError:
            pass
        
        # Fall back to thread-local (sync)
        if hasattr(_request_context, 'context'):
            return _request_context.context._user_id
        
        return self._user_id
    
    @user_id.setter
    def user_id(self, value: int | None) -> None:
        """Set the user ID.
        
        Args:
            value: The user ID to set.
        """
        self._user_id = value
        _user_id_var.set(value)
        if hasattr(_request_context, 'context'):
            _request_context.context._user_id = value
    
    @property
    def username(self) -> str | None:
        """Get the username.
        
        Returns:
            The username if set, None otherwise.
        """
        # Try context var first (async)
        try:
            value = _username_var.get()
            if value is not None:
                return value
        except LookupError:
            pass
        
        # Fall back to thread-local (sync)
        if hasattr(_request_context, 'context'):
            return _request_context.context._username
        
        return self._username
    
    @username.setter
    def username(self, value: str | None) -> None:
        """Set the username.
        
        Args:
            value: The username to set.
        """
        self._username = value
        _username_var.set(value)
        if hasattr(_request_context, 'context'):
            _request_context.context._username = value
    
    def get_all(self) -> dict[str, Any]:
        """Get all context data.
        
        Returns:
            Dictionary containing all context data.
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "username": self.username,
        }
    
    def clear(self) -> None:
        """Clear all context data."""
        self._request_id = None
        self._user_id = None
        self._username = None
        _request_id_var.set(None)
        _user_id_var.set(None)
        _username_var.set(None)
        if hasattr(_request_context, 'context'):
            _request_context.context._request_id = None
            _request_context.context._user_id = None
            _request_context.context._username = None


# Global request context instance
_context_instance: RequestContext | None = None


def get_request_context() -> RequestContext:
    """Get the current request context.
    
    Returns:
        RequestContext: The current request context instance.
    """
    global _context_instance
    
    # Try thread-local first
    if hasattr(_request_context, 'context'):
        return _request_context.context
    
    # Fall back to global instance
    if _context_instance is None:
        _context_instance = RequestContext()
    
    return _context_instance


def set_request_context(request_id: str | None = None,
                        user_id: int | None = None,
                        username: str | None = None) -> None:
    """Set the current request context.
    
    Args:
        request_id: Unique request identifier.
        user_id: User ID if authenticated.
        username: Username if authenticated.
    """
    ctx = get_request_context()
    
    if request_id is not None:
        ctx.request_id = request_id
    if user_id is not None:
        ctx.user_id = user_id
    if username is not None:
        ctx.username = username


def clear_request_context() -> None:
    """Clear the current request context."""
    ctx = get_request_context()
    ctx.clear()


def get_request_id() -> str | None:
    """Get the current request ID.
    
    Returns:
        The request ID if set, None otherwise.
    """
    return get_request_context().request_id


def get_user_id() -> int | None:
    """Get the current user ID.
    
    Returns:
        The user ID if set, None otherwise.
    """
    return get_request_context().user_id


def get_username() -> str | None:
    """Get the current username.
    
    Returns:
        The username if set, None otherwise.
    """
    return get_request_context().username
