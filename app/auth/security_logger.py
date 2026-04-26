"""Security logging utilities for Glyph application.

This module provides specialized logging functions for authentication
and authorization events with built-in rate limiting for brute-force detection.
"""

import time
from collections import defaultdict
from typing import Any

from loguru import logger

from app.utils.request_context import get_request_context


class LoginFailureTracker:
    """Track login failures for brute-force detection.

    Monitors login failures per username and IP address, triggering
    suspicious activity alerts when thresholds are exceeded.

    Recording and checking are separated to avoid double-counting
    when multiple keys (username + IP) are checked for the same event.
    """

    def __init__(
        self,
        threshold: int = 5,
        window: float = 300.0,
        max_keys: int = 1000):
        """Initialize the login failure tracker.

        Args:
            threshold: Number of failures before triggering alert.
            window: Time window in seconds for counting failures.
            max_keys: Maximum number of unique keys to track (memory bound).
        """
        self.threshold = threshold
        self.window = window
        self.max_keys = max_keys
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._alerted: dict[str, bool] = defaultdict(bool)
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300.0  # 5 minutes

    def _cleanup_stale_keys(self, now: float) -> None:
        """Remove stale keys and evict oldest if over memory limit.

        Args:
            now: Current timestamp.
        """
        cutoff = now - self.window
        # Clean old timestamps and remove empty buckets
        for key in list(self._failures):
            self._failures[key] = [t for t in self._failures[key] if t > cutoff]
            if not self._failures[key]:
                del self._failures[key]
                self._alerted.pop(key, None)

        # Evict oldest keys if over limit
        if len(self._failures) > self.max_keys:
            keys_by_activity = sorted(
                self._failures.keys(),
                key=lambda k: max(self._failures[k]) if self._failures[k] else 0)
            keys_to_remove = keys_by_activity[:len(self._failures) - self.max_keys]
            for key in keys_to_remove:
                del self._failures[key]
                self._alerted.pop(key, None)

    def record_failure(self, key: str) -> int:
        """Record a login failure and return current failure count.

        Args:
            key: Unique identifier (username or IP).

        Returns:
            Current number of failures in the window.
        """
        now = time.monotonic()
        # Periodic cleanup of stale keys
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_stale_keys(now)
            self._last_cleanup = now

        # Clean old entries for this key
        cutoff = now - self.window
        self._failures[key] = [t for t in self._failures[key] if t > cutoff]
        self._failures[key].append(now)
        return len(self._failures[key])

    def get_failure_count(self, key: str) -> int:
        """Get current failure count without recording a new failure.

        Args:
            key: Unique identifier (username or IP).

        Returns:
            Current number of failures in the window.
        """
        now = time.monotonic()
        cutoff = now - self.window
        return len([t for t in self._failures.get(key, []) if t > cutoff])

    def is_suspicious(self, key: str) -> bool:
        """Check if the key has exceeded the failure threshold.

        This method checks the current failure count without recording
        a new failure. Use record_failure() separately to add failures.

        Args:
            key: Unique identifier (username or IP).

        Returns:
            True if the key should be flagged as suspicious.
        """
        count = self.get_failure_count(key)
        if count >= self.threshold and not self._alerted.get(key, False):
            self._alerted[key] = True
            return True
        return False

    def reset(self, key: str) -> None:
        """Reset failure count for a key (e.g., after successful login).

        Args:
            key: Unique identifier to reset.
        """
        self._failures.pop(key, None)
        self._alerted.pop(key, None)

    def reset_all(self) -> None:
        """Reset all failure counts."""
        self._failures.clear()
        self._alerted.clear()


# Global failure tracker instance
_login_failure_tracker = LoginFailureTracker()


def get_failure_tracker() -> LoginFailureTracker:
    """Get the global login failure tracker.

    Returns:
        LoginFailureTracker: The global tracker instance.
    """
    return _login_failure_tracker


def log_login_attempt(
    username: str,
    ip_address: str | None = None,
    user_agent: str | None = None) -> None:
    """Log that a login attempt has been initiated.

    This is called at the start of the login flow to record the attempt
    before the outcome is known. Use log_login_success() or log_login_failure()
    to record the final result.

    Args:
        username: The username that attempted to log in.
        ip_address: The IP address of the request.
        user_agent: The user agent string.
    """
    log_data: dict[str, Any] = {
        "event": "login_attempt",
        "username": username,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    logger.bind(**log_data).info(
        "Login attempt initiated: {}", username)


def log_login_success(
    user_id: int,
    username: str,
    session_id: str | None = None,
    ip_address: str | None = None) -> None:
    """Log a successful login.

    Args:
        user_id: The user's ID.
        username: The user's username.
        session_id: The session ID.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "login_success",
        "user_id": user_id,
        "username": username,
        "session_id": session_id,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "Login successful: {} (user_id={})", username, user_id)

    # Reset failure tracker on successful login
    _login_failure_tracker.reset(username)
    if ip_address:
        _login_failure_tracker.reset(ip_address)


def log_login_failure(
    username: str,
    reason: str,
    ip_address: str | None = None,
    attempt_number: int | None = None) -> None:
    """Log a failed login attempt with brute-force detection.

    Args:
        username: The username that attempted to log in.
        reason: The reason for failure.
        ip_address: The IP address of the request.
        attempt_number: The attempt number (for tracking multiple failures).
    """
    log_data: dict[str, Any] = {
        "event": "login_failure",
        "username": username,
        "reason": reason,
        "ip_address": ip_address,
    }

    if attempt_number:
        log_data["attempt_number"] = attempt_number

    logger.bind(**log_data).warning(
        "Login failed: {} - {}", username, reason)

    # Track for brute-force detection - record first, then check thresholds
    _login_failure_tracker.record_failure(username)
    if ip_address:
        _login_failure_tracker.record_failure(ip_address)

    suspicious_username = _login_failure_tracker.is_suspicious(username)
    suspicious_ip = ip_address and _login_failure_tracker.is_suspicious(ip_address)

    if suspicious_username:
        log_suspicious_activity(
            user_id=None,
            activity_type="brute_force_login_attempt",
            details={
                "username": username,
                "reason": reason,
                "attempt_number": attempt_number,
                "target": "username",
            },
            ip_address=ip_address)
    if suspicious_ip:
        log_suspicious_activity(
            user_id=None,
            activity_type="brute_force_login_attempt",
            details={
                "username": username,
                "reason": reason,
                "attempt_number": attempt_number,
                "target": "ip_address",
            },
            ip_address=ip_address)


def log_logout(
    user_id: int,
    username: str,
    session_id: str | None = None,
    ip_address: str | None = None) -> None:
    """Log a user logout.

    Args:
        user_id: The user's ID.
        username: The user's username.
        session_id: The session ID.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "logout",
        "user_id": user_id,
        "username": username,
        "session_id": session_id,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "User logged out: {} (user_id={})", username, user_id)


def log_token_refresh(
    user_id: int,
    token_type: str,
    ip_address: str | None = None) -> None:
    """Log a token refresh event.

    Args:
        user_id: The user's ID.
        token_type: The type of token being refreshed (access, refresh).
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "token_refresh",
        "user_id": user_id,
        "token_type": token_type,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).debug(
        "Token refreshed: user_id={}, type={}", user_id, token_type)


def log_api_key_usage(
    user_id: int,
    api_key_prefix: str,
    endpoint: str,
    ip_address: str | None = None) -> None:
    """Log API key usage.

    Args:
        user_id: The user's ID.
        api_key_prefix: First 4 characters of the API key for identification.
        endpoint: The API endpoint accessed.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "api_key_usage",
        "user_id": user_id,
        "api_key_prefix": api_key_prefix,
        "endpoint": endpoint,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).debug(
        "API key used: user_id={}, key={}..., endpoint={}",
        user_id, api_key_prefix, endpoint)


def log_permission_denied(
    user_id: int,
    username: str | None,
    resource: str,
    required_permission: str,
    ip_address: str | None = None) -> None:
    """Log a permission denied event.

    Args:
        user_id: The user's ID.
        username: The user's username.
        resource: The resource that was accessed.
        required_permission: The permission that was required.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "permission_denied",
        "user_id": user_id,
        "username": username,
        "resource": resource,
        "required_permission": required_permission,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).warning(
        "Permission denied: user_id={}, resource={}, permission={}",
        user_id, resource, required_permission)


def log_suspicious_activity(
    user_id: int | None,
    activity_type: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None) -> None:
    """Log suspicious activity.

    Args:
        user_id: The user's ID (if known).
        activity_type: The type of suspicious activity.
        details: Additional details about the activity.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "suspicious_activity",
        "user_id": user_id,
        "activity_type": activity_type,
        "ip_address": ip_address,
    }

    if details:
        log_data.update(details)

    logger.bind(**log_data).warning(
        "Suspicious activity detected: {}", activity_type)


def log_password_change(
    user_id: int,
    username: str,
    ip_address: str | None = None) -> None:
    """Log a password change event.

    Args:
        user_id: The user's ID.
        username: The user's username.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "password_change",
        "user_id": user_id,
        "username": username,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "Password changed: user_id={}, username={}", user_id, username)


def log_account_lockout(
    user_id: int | None,
    username: str,
    reason: str,
    ip_address: str | None = None) -> None:
    """Log an account lockout event.

    Args:
        user_id: The user's ID (if known).
        username: The username that was locked out.
        reason: The reason for lockout.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "account_lockout",
        "user_id": user_id,
        "username": username,
        "reason": reason,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).warning(
        "Account locked: {} - {}", username, reason)


def log_account_unlock(
    user_id: int,
    username: str,
    unlocked_by: str | None = None) -> None:
    """Log an account unlock event.

    Args:
        user_id: The user's ID.
        username: The username that was unlocked.
        unlocked_by: Who unlocked the account (admin, auto, etc.).
    """
    log_data: dict[str, Any] = {
        "event": "account_unlock",
        "user_id": user_id,
        "username": username,
        "unlocked_by": unlocked_by,
    }

    logger.bind(**log_data).info(
        "Account unlocked: user_id={}, username={}", user_id, username)


def log_user_registration(
    user_id: int,
    username: str,
    ip_address: str | None = None) -> None:
    """Log a user registration event.

    This is a normal operational event logged at INFO level,
    not classified as suspicious activity.

    Args:
        user_id: The user's ID.
        username: The user's username.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "user_registration",
        "user_id": user_id,
        "username": username,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "User registered: user_id={}, username={}", user_id, username)


def log_api_key_created(
    user_id: int,
    key_id: int,
    key_prefix: str,
    name: str,
    ip_address: str | None = None) -> None:
    """Log an API key creation event.

    Args:
        user_id: The user's ID.
        key_id: The API key record ID.
        key_prefix: First 8 characters of the API key for identification.
        name: Human-readable name for the key.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "api_key_created",
        "user_id": user_id,
        "key_id": key_id,
        "key_prefix": key_prefix,
        "name": name,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "API key created: user_id={}, key_id={}, name={}, prefix={}",
        user_id, key_id, name, key_prefix)


def log_api_key_deleted(
    user_id: int,
    key_id: int,
    name: str,
    ip_address: str | None = None) -> None:
    """Log an API key deletion event.

    Args:
        user_id: The user's ID.
        key_id: The API key record ID.
        name: Human-readable name for the key.
        ip_address: The IP address of the request.
    """
    log_data: dict[str, Any] = {
        "event": "api_key_deleted",
        "user_id": user_id,
        "key_id": key_id,
        "name": name,
        "ip_address": ip_address,
    }

    logger.bind(**log_data).info(
        "API key deleted: user_id={}, key_id={}, name={}",
        user_id, key_id, name)


def log_csrf_failure(
    ip_address: str | None = None,
    path: str | None = None,
    method: str | None = None) -> None:
    """Log a CSRF validation failure.

    Args:
        ip_address: The IP address of the request.
        path: The request path.
        method: The HTTP method.
    """
    log_data: dict[str, Any] = {
        "event": "csrf_failure",
        "ip_address": ip_address,
        "path": path,
        "method": method,
    }

    logger.bind(**log_data).warning(
        "CSRF validation failed: method={}, path={}", method, path)
