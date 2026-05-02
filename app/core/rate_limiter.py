"""Rate limiting utilities for authentication endpoints.

Provides in-memory rate limiting to protect against brute-force attacks
on login, registration, and password change endpoints.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status


class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints.

    Tracks request counts per IP address within a sliding time window.
    When the threshold is exceeded, returns HTTP 429 Too Many Requests.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        """Check if a key (IP address) has exceeded the rate limit.

        Args:
            key: The identifier to check (usually IP address).

        Returns:
            True if the key is rate limited, False otherwise.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.window_seconds)

        # Clean up old entries
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        if len(self._requests[key]) >= self.max_requests:
            return True

        self._requests[key].append(now)
        return False

    def cleanup(self) -> None:
        """Remove expired entries to prevent memory leaks."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.window_seconds)
        expired_keys = [
            key for key, times in self._requests.items()
            if not times or all(t <= window_start for t in times)
        ]
        for key in expired_keys:
            del self._requests[key]


def get_client_ip(request: Any) -> str:
    """Extract client IP from request, considering trusted proxy headers.

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


def check_rate_limit(limiter: RateLimiter, request: Any) -> None:
    """Check rate limit for a request and raise HTTPException if exceeded.

    Args:
        limiter: RateLimiter instance to check against.
        request: FastAPI request object.

    Raises:
        HTTPException: If rate limit is exceeded.
    """
    client_ip = get_client_ip(request)
    if limiter.is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )


# Rate limiters for different endpoints
login_limiter = RateLimiter(max_requests=10, window_seconds=60)
register_limiter = RateLimiter(max_requests=5, window_seconds=300)
password_change_limiter = RateLimiter(max_requests=5, window_seconds=300)
refresh_limiter = RateLimiter(max_requests=10, window_seconds=60)
