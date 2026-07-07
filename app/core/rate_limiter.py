"""Rate limiting configuration using slowapi."""

import os

from fastapi import Request
from slowapi import Limiter


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
    """Extract client IP for rate limiting, respecting trusted proxies.

    When the direct connection is from a trusted proxy, extract the real client
    IP from X-Forwarded-For by walking the chain right-to-left and returning
    the first (rightmost) IP that is NOT a trusted proxy. This prevents attackers
    from spoofing the client IP by injecting fake entries into the header.
    """
    from app.config.settings import get_settings

    settings = get_settings()
    client = getattr(request, "client", None)
    direct_ip: str = client.host if client and hasattr(client, "host") else "unknown"

    trusted_proxies = set(settings.trusted_proxies) if settings.trusted_proxies else set()

    if trusted_proxies and direct_ip in trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: client_ip, proxy1_ip, proxy2_ip, ...
            # Walk right-to-left to find the first non-proxy IP (the real client).
            ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            for ip in reversed(ips):
                if ip not in trusted_proxies:
                    return ip
            # All IPs in the chain are trusted proxies; fall back to the leftmost.
            return ips[0] if ips else direct_ip

    return direct_ip


limiter = Limiter(key_func=rate_limit_key_func)

LOGIN_LIMIT = _build_rate_limit(10, 60, "LOGIN")
REGISTER_LIMIT = _build_rate_limit(5, 300, "REGISTER")
PASSWORD_CHANGE_LIMIT = _build_rate_limit(5, 300, "PASSWORD_CHANGE")
REFRESH_LIMIT = _build_rate_limit(10, 60, "REFRESH")
