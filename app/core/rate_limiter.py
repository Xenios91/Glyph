"""Rate limiting configuration using slowapi."""

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def _build_rate_limit(max_requests: int, window_seconds: int, env_prefix: str) -> str:
    """Build a slowapi rate limit string, allowing environment variable overrides."""
    env_max = os.environ.get(f"GLYPH_RATE_LIMIT_{env_prefix}_MAX")
    env_window = os.environ.get(f"GLYPH_RATE_LIMIT_{env_prefix}_WINDOW")

    max_req = int(env_max) if env_max else max_requests
    window = int(env_window) if env_window else window_seconds

    if window == 60:
        return f"{max_req}/minute"
    elif window == 300:
        return f"{max_req}/5 minutes"
    elif window == 3600:
        return f"{max_req}/hour"
    else:
        return f"{max_req}/{window} seconds"


def rate_limit_key_func(request: Request) -> str:
    """Extract client IP for rate limiting, respecting trusted proxies."""
    from app.config.settings import get_settings

    settings = get_settings()
    client = getattr(request, "client", None)
    direct_ip = client.host if client and hasattr(client, "host") else "unknown"

    if settings.trusted_proxies and direct_ip in settings.trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

    return direct_ip


limiter = Limiter(key_func=rate_limit_key_func)

LOGIN_LIMIT = _build_rate_limit(10, 60, "LOGIN")
REGISTER_LIMIT = _build_rate_limit(5, 300, "REGISTER")
PASSWORD_CHANGE_LIMIT = _build_rate_limit(5, 300, "PASSWORD_CHANGE")
REFRESH_LIMIT = _build_rate_limit(10, 60, "REFRESH")


def get_rate_limit_exceeded_handler() -> RateLimitExceeded:
    """Return the RateLimitExceeded class for handler registration."""
    return RateLimitExceeded
