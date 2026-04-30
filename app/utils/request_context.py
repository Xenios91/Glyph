"""Request context management for Glyph application.

This module provides async-safe context storage for request-specific data
that can be accessed throughout the request lifecycle using ContextVars.

ContextVars are safe across async boundaries (await, create_task) but do NOT
propagate to new threads or new event loops (asyncio.run). For those cases,
use capture_request_context() to snapshot the current values into a
CapturedContext dataclass, pass it explicitly, and then restore it with
restore_request_context() on the target side.
"""

from contextvars import ContextVar
from dataclasses import dataclass


# Async-compatible context variables
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
_username_var: ContextVar[str | None] = ContextVar("username", default=None)
_task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)


@dataclass(frozen=True)
class CapturedContext:
    """Snapshot of request context values for cross-thread/loop propagation.

    ContextVars do not propagate to new threads or new event loops
    (e.g. asyncio.run()). This dataclass captures the current values so
    they can be explicitly passed and restored on the target side.
    """

    request_id: str | None
    user_id: int | None
    username: str | None
    task_id: str | None


def capture_request_context() -> CapturedContext:
    """Capture the current request context into a snapshot.

    Call this on the request thread/loop before handing off work to a
    background thread or a new event loop, then pass the snapshot
    explicitly to the target.

    Returns:
        CapturedContext with the current ContextVar values.
    """
    return CapturedContext(
        request_id=_request_id_var.get(),
        user_id=_user_id_var.get(),
        username=_username_var.get(),
        task_id=_task_id_var.get(),
    )


def restore_request_context(
    captured: CapturedContext,
    override_task_id: str | None = None,
) -> None:
    """Restore request context from a captured snapshot.

    Call this on the target thread/loop after receiving a CapturedContext
    that was captured on the originating request thread.

    Args:
        captured: The captured context snapshot.
        override_task_id: If provided, override the task_id from the
            snapshot (useful when the task ID changes during handoff).
    """
    _request_id_var.set(captured.request_id)
    _user_id_var.set(captured.user_id)
    _username_var.set(captured.username)
    _task_id_var.set(override_task_id if override_task_id is not None else captured.task_id)


class RequestContext:
    """Request context for storing request-specific data.

    This class provides a unified interface for accessing request context
    data using async-safe ContextVars.
    """

    def __init__(self) -> None:
        # Initialize from current ContextVar values
        pass

    @property
    def request_id(self) -> str | None:
        """Get the request ID.

        Returns:
            The request ID if set, None otherwise.
        """
        return _request_id_var.get()

    @request_id.setter
    def request_id(self, value: str | None) -> None:
        """Set the request ID.

        Args:
            value: The request ID to set.
        """
        _request_id_var.set(value)

    @property
    def user_id(self) -> int | None:
        """Get the user ID.

        Returns:
            The user ID if set, None otherwise.
        """
        return _user_id_var.get()

    @user_id.setter
    def user_id(self, value: int | None) -> None:
        """Set the user ID.

        Args:
            value: The user ID to set.
        """
        _user_id_var.set(value)

    @property
    def username(self) -> str | None:
        """Get the username.

        Returns:
            The username if set, None otherwise.
        """
        return _username_var.get()

    @username.setter
    def username(self, value: str | None) -> None:
        """Set the username.

        Args:
            value: The username to set.
        """
        _username_var.set(value)

    @property
    def task_id(self) -> str | None:
        """Get the task ID (for background tasks).

        Returns:
            The task ID if set, None otherwise.
        """
        return _task_id_var.get()

    @task_id.setter
    def task_id(self, value: str | None) -> None:
        """Set the task ID.

        Args:
            value: The task ID to set.
        """
        _task_id_var.set(value)

def get_request_context() -> RequestContext:
    """Get the current request context.

    Returns a new RequestContext instance that reads from the current
    ContextVar values. Each call creates a fresh view of the context.

    Returns:
        RequestContext: The current request context instance.
    """
    return RequestContext()


def set_request_context(
    request_id: str | None = None,
    user_id: int | None = None,
    username: str | None = None,
    task_id: str | None = None,
    clear_unset: bool = True) -> None:
    """Set the current request context.

    Args:
        request_id: Unique request identifier.
        user_id: User ID if authenticated.
        username: Username if authenticated.
        task_id: Task ID for background tasks.
        clear_unset: If True (default), clear any fields not explicitly provided.
                     If False, only update the fields provided (legacy behavior).
    """
    if clear_unset:
        _request_id_var.set(request_id)
        _user_id_var.set(user_id)
        _username_var.set(username)
        _task_id_var.set(task_id)
    else:
        if request_id is not None:
            _request_id_var.set(request_id)
        if user_id is not None:
            _user_id_var.set(user_id)
        if username is not None:
            _username_var.set(username)
        if task_id is not None:
            _task_id_var.set(task_id)


def clear_request_context() -> None:
    """Clear the current request context."""
    _request_id_var.set(None)
    _user_id_var.set(None)
    _username_var.set(None)
    _task_id_var.set(None)


def get_request_id() -> str | None:
    """Get the current request ID.

    Returns:
        The request ID if set, None otherwise.
    """
    return _request_id_var.get()


def get_user_id() -> int | None:
    """Get the current user ID.

    Returns:
        The user ID if set, None otherwise.
    """
    return _user_id_var.get()


def get_username() -> str | None:
    """Get the current username.

    Returns:
        The username if set, None otherwise.
    """
    return _username_var.get()


def get_task_id() -> str | None:
    """Get the current task ID.

    Returns:
        The task ID if set, None otherwise.
    """
    return _task_id_var.get()
