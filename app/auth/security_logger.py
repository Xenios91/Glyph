"""Security logging utilities for Glyph application.

This module provides specialized logging functions for authentication
and authorization events.
"""

import logging
from typing import Any

from app.utils.logging_config import get_logger
from app.utils.request_context import get_request_context


logger = get_logger(__name__)


def log_login_attempt(username: str, ip_address: str | None = None,
                      user_agent: str | None = None, success: bool = True,
                      reason: str | None = None) -> None:
    """Log a login attempt.
    
    Args:
        username: The username that attempted to log in.
        ip_address: The IP address of the request.
        user_agent: The user agent string.
        success: Whether the login was successful.
        reason: Reason for failure (if success is False).
    """
    ctx = get_request_context()
    
    log_data = {
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
    else:
        logger.warning("Login attempt failed: %s - %s", username, reason,
                      extra={"extra_data": log_data})


def log_login_success(user_id: int, username: str, session_id: str | None = None,
                      ip_address: str | None = None) -> None:
    """Log a successful login.
    
    Args:
        user_id: The user's ID.
        username: The user's username.
        session_id: The session ID.
        ip_address: The IP address of the request.
    """
    ctx = get_request_context()
    
    log_data = {
        "event": "login_success",
        "user_id": user_id,
        "username": username,
        "session_id": session_id,
        "ip_address": ip_address,
    }
    
    logger.info("Login successful: %s (user_id=%d)", username, user_id,
               extra={"extra_data": log_data})


def log_login_failure(username: str, reason: str,
                      ip_address: str | None = None,
                      attempt_number: int | None = None) -> None:
    """Log a failed login attempt.
    
    Args:
        username: The username that attempted to log in.
        reason: The reason for failure.
        ip_address: The IP address of the request.
        attempt_number: The attempt number (for tracking multiple failures).
    """
    log_data = {
        "event": "login_failure",
        "username": username,
        "reason": reason,
        "ip_address": ip_address,
    }
    
    if attempt_number:
        log_data["attempt_number"] = attempt_number
    
    logger.warning("Login failed: %s - %s", username, reason,
                  extra={"extra_data": log_data})


def log_logout(user_id: int, username: str, session_id: str | None = None) -> None:
    """Log a user logout.
    
    Args:
        user_id: The user's ID.
        username: The user's username.
        session_id: The session ID.
    """
    log_data = {
        "event": "logout",
        "user_id": user_id,
        "username": username,
        "session_id": session_id,
    }
    
    logger.info("User logged out: %s (user_id=%d)", username, user_id,
               extra={"extra_data": log_data})


def log_token_refresh(user_id: int, token_type: str,
                      ip_address: str | None = None) -> None:
    """Log a token refresh event.
    
    Args:
        user_id: The user's ID.
        token_type: The type of token being refreshed (access, refresh).
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "token_refresh",
        "user_id": user_id,
        "token_type": token_type,
        "ip_address": ip_address,
    }
    
    logger.info("Token refreshed: user_id=%d, type=%s", user_id, token_type,
               extra={"extra_data": log_data})


def log_api_key_usage(user_id: int, api_key_prefix: str, endpoint: str,
                      ip_address: str | None = None) -> None:
    """Log API key usage.
    
    Args:
        user_id: The user's ID.
        api_key_prefix: First 4 characters of the API key for identification.
        endpoint: The API endpoint accessed.
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "api_key_usage",
        "user_id": user_id,
        "api_key_prefix": api_key_prefix,
        "endpoint": endpoint,
        "ip_address": ip_address,
    }
    
    logger.info("API key used: user_id=%d, key=%s..., endpoint=%s",
               user_id, api_key_prefix, endpoint,
               extra={"extra_data": log_data})


def log_permission_denied(user_id: int, username: str | None,
                          resource: str, required_permission: str,
                          ip_address: str | None = None) -> None:
    """Log a permission denied event.
    
    Args:
        user_id: The user's ID.
        username: The user's username.
        resource: The resource that was accessed.
        required_permission: The permission that was required.
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "permission_denied",
        "user_id": user_id,
        "username": username,
        "resource": resource,
        "required_permission": required_permission,
        "ip_address": ip_address,
    }
    
    logger.warning("Permission denied: user_id=%d, resource=%s, permission=%s",
                  user_id, resource, required_permission,
                  extra={"extra_data": log_data})


def log_suspicious_activity(user_id: int | None, activity_type: str,
                            details: dict[str, Any] | None = None,
                            ip_address: str | None = None) -> None:
    """Log suspicious activity.
    
    Args:
        user_id: The user's ID (if known).
        activity_type: The type of suspicious activity.
        details: Additional details about the activity.
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "suspicious_activity",
        "user_id": user_id,
        "activity_type": activity_type,
        "ip_address": ip_address,
    }
    
    if details:
        log_data.update(details)
    
    logger.warning("Suspicious activity detected: %s", activity_type,
                  extra={"extra_data": log_data})


def log_password_change(user_id: int, username: str,
                        ip_address: str | None = None) -> None:
    """Log a password change event.
    
    Args:
        user_id: The user's ID.
        username: The user's username.
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "password_change",
        "user_id": user_id,
        "username": username,
        "ip_address": ip_address,
    }
    
    logger.info("Password changed: user_id=%d, username=%s", user_id, username,
               extra={"extra_data": log_data})


def log_account_lockout(user_id: int | None, username: str,
                        reason: str, ip_address: str | None = None) -> None:
    """Log an account lockout event.
    
    Args:
        user_id: The user's ID (if known).
        username: The username that was locked out.
        reason: The reason for lockout.
        ip_address: The IP address of the request.
    """
    log_data = {
        "event": "account_lockout",
        "user_id": user_id,
        "username": username,
        "reason": reason,
        "ip_address": ip_address,
    }
    
    logger.warning("Account locked: %s - %s", username, reason,
                  extra={"extra_data": log_data})


def log_account_unlock(user_id: int, username: str,
                       unlocked_by: str | None = None) -> None:
    """Log an account unlock event.
    
    Args:
        user_id: The user's ID.
        username: The username that was unlocked.
        unlocked_by: Who unlocked the account (admin, auto, etc.).
    """
    log_data = {
        "event": "account_unlock",
        "user_id": user_id,
        "username": username,
        "unlocked_by": unlocked_by,
    }
    
    logger.info("Account unlocked: user_id=%d, username=%s", user_id, username,
               extra={"extra_data": log_data})
