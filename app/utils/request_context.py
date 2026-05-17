"""Request context management using async-safe ContextVars.

For cross-thread or cross-event-loop propagation, use capture_request_context()
and restore_request_context() to explicitly pass context snapshots.
"""

from contextvars import ContextVar
from dataclasses import dataclass


_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)
_username_var: ContextVar[str | None] = ContextVar("username", default=None)
_task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)


@dataclass(frozen=True)
class CapturedContext:
    """Snapshot of request context values for cross-thread/loop propagation."""

    request_id: str | None
    user_id: int | None
    username: str | None
    task_id: str | None


def capture_request_context() -> CapturedContext:
    """Capture the current request context into a snapshot."""
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

    Args:
        captured: The captured context snapshot.
        override_task_id: If provided, override the task_id from the snapshot.
    """
    _request_id_var.set(captured.request_id)
    _user_id_var.set(captured.user_id)
    _username_var.set(captured.username)
    _task_id_var.set(override_task_id if override_task_id is not None else captured.task_id)


class RequestContext:
    """Request context for storing request-specific data via ContextVars."""

    @property
    def request_id(self) -> str | None:
        return _request_id_var.get()

    @request_id.setter
    def request_id(self, value: str | None) -> None:
        _request_id_var.set(value)

    @property
    def user_id(self) -> int | None:
        return _user_id_var.get()

    @user_id.setter
    def user_id(self, value: int | None) -> None:
        _user_id_var.set(value)

    @property
    def username(self) -> str | None:
        return _username_var.get()

    @username.setter
    def username(self, value: str | None) -> None:
        _username_var.set(value)

    @property
    def task_id(self) -> str | None:
        return _task_id_var.get()

    @task_id.setter
    def task_id(self, value: str | None) -> None:
        _task_id_var.set(value)

def get_request_context() -> RequestContext:
    """Get the current request context."""
    return RequestContext()


class _UnsetSentinel:
    """Sentinel to distinguish "not provided" from "explicitly set to None"."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "<UNSET>"


_UNSET = _UnsetSentinel()


def set_request_context(
    request_id: str | None | _UnsetSentinel = _UNSET,
    user_id: int | None | _UnsetSentinel = _UNSET,
    username: str | None | _UnsetSentinel = _UNSET,
    task_id: str | None | _UnsetSentinel = _UNSET,
    clear_unset: bool = False) -> None:
    """Set the current request context.

    Args:
        request_id: Unique request identifier.
        user_id: User ID if authenticated.
        username: Username if authenticated.
        task_id: Task ID for background tasks.
        clear_unset: If True, clear all fields first, then apply only provided values.
    """
    if clear_unset:
        _request_id_var.set(None)
        _user_id_var.set(None)
        _username_var.set(None)
        _task_id_var.set(None)

    if request_id is not _UNSET:
        _request_id_var.set(request_id)  # pyright: ignore[reportArgumentType]
    if user_id is not _UNSET:
        _user_id_var.set(user_id)  # pyright: ignore[reportArgumentType]
    if username is not _UNSET:
        _username_var.set(username)  # pyright: ignore[reportArgumentType]
    if task_id is not _UNSET:
        _task_id_var.set(task_id)  # pyright: ignore[reportArgumentType]


def clear_request_context() -> None:
    """Clear the current request context."""
    _request_id_var.set(None)
    _user_id_var.set(None)
    _username_var.set(None)
    _task_id_var.set(None)


def get_request_id() -> str | None:
    return _request_id_var.get()


def get_user_id() -> int | None:
    return _user_id_var.get()


def get_username() -> str | None:
    return _username_var.get()


def get_task_id() -> str | None:
    return _task_id_var.get()
