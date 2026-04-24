"""Security logging utilities for Glyph application.

This module provides specialized logging functions for authentication
and authorization events with built-in rate limiting for brute-force detection.
"""

import logging
import time
from collections import defaultdict
from typing import Any

from app.utils.logging_config import get_logger
from app.utils.request_context import get_request_context


logger = get_logger(__name__)


class LoginFailureTracker:
    """Track login failures for brute-force detection.

    Monitors login failures per username and IP address, triggering
    suspicious activity alerts when thresholds are exceeded.
    """

    def __init__(
        self,
        threshold: int = 5,
        window: float = 300.0,
    ):
        """Initialize the login failure tracker.

        Args:
            threshold: Number of failures before triggering alert.
            window: Time window in seconds for counting failures.
        """
        self.threshold = threshold
        self.window = window
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._alerted: dict[str, bool] = defaultdict(bool)

    def record_failure(self, key: str) -> int:
        """Record a login failure and return current failure count.

        Args:
            key: Unique identifier (username or IP).

        Returns:
            Current number of failures in the window.
        """
        now = time.time()
        # Clean old entries
        cutoff = now - self.window
        self._failures[key] = [t for t in self._failures[key] if t > cutoff]
        self._failures[key].append(now)
        return len(self._failures[key])

    def is_suspicious(self, key: str) -> bool:
        """Check if the key has exceeded the failure threshold.

        Args:
            key: Unique identifier (username or IP).

        Returns:
            True if the key should be flagged as suspicious.
        """
        count = self.record_failure(key)
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
    user_agent: str | None = None,
    success: bool = True,
    reason: str | None = None,
) -> None:
    """Log a login attempt.

    Args:
        username: The username that attempted to log in.
        ip_address: The IP address of the request.
        user_agent: The user agent string.
        success: Whether the login was successful.
        reason: Reason for failure (if success is False).
    """
    log_data: dict[str, Any] = {
        "event": "login_attempt",
        "username": username,
        "success": success,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }

    if not success and reason:
        log_data["reason"] = reason

    if success:
        logger.info("Login attempt: %s", username, extra={"extra_data": log_data})
        # Reset failure tracker on successful login
        _login_failure_tracker.reset(username)
        if ip_address:
            _login_failure_tracker.reset(ip_address)
    else:
        logger.warning(
            "Login attempt failed: %s - %s", username, reason,
            extra={"extra_data": log_data},
        )


def log_login_success(
    user_id: int,
    username: str,
    session_id: str | None = None,
    ip_address: str | None = None,
) -> None:
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

    logger.info(
        "Login successful: %s (user_id=%d)", username, user_id,
        extra={"extra_data": log_data},
    )

    # Reset failure tracker on successful login
    _login_failure_tracker.reset(username)
    if ip_address:
        _login_failure_tracker.reset(ip_address)


def log_login_failure(
    username: str,
    reason: str,
    ip_address: str | None = None,
    attempt_number: int | None = None,
) -> None:
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

    logger.warning(
        "Login failed: %s - %s", username, reason,
        extra={"extra_data": log_data},
    )

    # Track for brute-force detection
    suspicious_username = _login_failure_tracker.is_suspicious(username)
    suspicious_ip = ip_address and _login_failure_tracker.is_suspicious(ip_address)

    if suspicious_username or suspicious_ip:
        log_suspicious_activity(
            user_id=None,
            activity_type="brute_force_login_attempt",
            details={
                "username": username,
                "reason": reason,
                "attempt_number": attempt_number,
            },
            ip_address=ip_address,
        )


def log_logout(
    user_id: int,
    username: str,
    session_id: str | None = None,
) -> None:
    """Log a user logout.

    Args:
        user_id: The user's ID.
        username: The user's username.
        session_id: The session ID.
    """
    log_data: dict[str, Any] = {
        "event": "logout",
        "user_id": user_id,
        "username": username,
        "session_id": session_id,
    }

    logger.info(
        "User logged out: %s (user_id=%d)", username, user_id,
        extra={"extra_data": log_data},
    )


def log_token_refresh(
    user_id: int,
    token_type: str,
    ip_address: str | None = None,
) -> None:
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

    logger.info(
        "Token refreshed: user_id=%d, type=%s", user_id, token_type,
        extra={"extra_data": log_data},
    )


def log_api_key_usage(
    user_id: int,
    api_key_prefix: str,
    endpoint: str,
    ip_address: str | None = None,
) -> None:
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

    logger.info(
        "API key used: user_id=%d, key=%s..., endpoint=%s",
        user_id, api_key_prefix, endpoint,
        extra={"extra_data": log_data},
    )


def log_permission_denied(
    user_id: int,
    username: str | None,
    resource: str,
    required_permission: str,
    ip_address: str | None = None,
) -> None:
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

    logger.warning(
        "Permission denied: user_id=%d, resource=%s, permission=%s",
        user_id, resource, required_permission,
        extra={"extra_data": log_data},
    )


def log_suspicious_activity(
    user_id: int | None,
    activity_type: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
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

    logger.warning(
        "Suspicious activity detected: %s", activity_type,
        extra={"extra_data": log_data},
    )


def log_password_change(
    user_id: int,
    username: str,
    ip_address: str | None = None,
) -> None:
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

    logger.info(
        "Password changed: user_id=%d, username=%s", user_id, username,
        extra={"extra_data": log_data},
    )


def log_account_lockout(
    user_id: int | None,
    username: str,
    reason: str,
    ip_address: str | None = None,
) -> None:
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

    logger.warning(
        "Account locked: %s - %s", username, reason,
        extra={"extra_data": log_data},
    )


def log_account_unlock(
    user_id: int,
    username: str,
    unlocked_by: str | None = None,
) -> None:
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

    logger.info(
        "Account unlocked: user_id=%d, username=%s", user_id, username,
        extra={"extra_data": log_data},
    )
