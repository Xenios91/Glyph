"""Rate limiting configuration using slowapi.

Provides rate limiting for authentication endpoints to protect against
brute-force attacks. Uses slowapi with a custom key function that respects
trusted proxy configuration for accurate client IP extraction.

Rate limits can be overridden via environment variables:
    GLYPH_RATE_LIMIT_LOGIN_MAX (default: 10)
    GLYPH_RATE_LIMIT_LOGIN_WINDOW (default: 60)
    GLYPH_RATE_LIMIT_REGISTER_MAX (default: 5)
    GLYPH_RATE_LIMIT_REGISTER_WINDOW (default: 300)
    GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX (default: 5)
    GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW (default: 300)
    GLYPH_RATE_LIMIT_REFRESH_MAX (default: 10)
    GLYPH_RATE_LIMIT_REFRESH_WINDOW (default: 60)
"""

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _build_rate_limit(max_requests: int, window_seconds: int, env_prefix: str) -> str:
    """Build a slowapi rate limit string, allowing environment variable overrides.

    Args:
        max_requests: Default maximum requests allowed.
        window_seconds: Default window size in seconds.
        env_prefix: Environment variable prefix for overrides.

    Returns:
        Rate limit string in slowapi format (e.g., "10/minute", "5/5 minutes").
    """
    env_max = os.environ.get(f"GLYPH_RATE_LIMIT_{env_prefix}_MAX")
    env_window = os.environ.get(f"GLYPH_RATE_LIMIT_{env_prefix}_WINDOW")

    max_req = int(env_max) if env_max else max_requests
    window = int(env_window) if env_window else window_seconds

    # Convert to human-readable slowapi format
    if window == 60:
        return f"{max_req}/minute"
    elif window == 300:
        return f"{max_req}/5 minutes"
    elif window == 3600:
        return f"{max_req}/hour"
    else:
        return f"{max_req}/{window} seconds"


def rate_limit_key_func(request: Request) -> str:
    """Extract client IP for rate limiting, respecting trusted proxies.

    Only trusts X-Forwarded-For when the direct connection is from a
    configured trusted proxy. Otherwise uses the direct socket peer address.

    Args:
        request: FastAPI request object.

    Returns:
        Client IP address string.
    """
    from app.config.settings import get_settings

    settings = get_settings()
    client = getattr(request, "client", None)
    direct_ip = client.host if client and hasattr(client, "host") else "unknown"

    # Only trust X-Forwarded-For when connected via a trusted proxy
    if settings.trusted_proxies and direct_ip in settings.trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

    return direct_ip


# Create limiter with custom key function for proxy support
limiter = Limiter(key_func=rate_limit_key_func)


# --- Rate limit definitions per endpoint ---
# These match the original in-house rate limiter defaults.

LOGIN_LIMIT = _build_rate_limit(10, 60, "LOGIN")
REGISTER_LIMIT = _build_rate_limit(5, 300, "REGISTER")
PASSWORD_CHANGE_LIMIT = _build_rate_limit(5, 300, "PASSWORD_CHANGE")
REFRESH_LIMIT = _build_rate_limit(10, 60, "REFRESH")


def get_rate_limit_exceeded_handler() -> RateLimitExceeded:
    """Return the RateLimitExceeded exception class for handler registration.

    Returns:
        The RateLimitExceeded class from slowapi.
    """
    return RateLimitExceeded
