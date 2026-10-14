"""Centralized Jinja2 template configuration.

This module provides a single, shared Jinja2Templates instance for the entire
application. Using a single instance ensures:
- Consistent auto-escaping configuration across all endpoints
- Shared template cache (reduces memory overhead)
- Consistent global filters and macros
"""

import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

templates = Jinja2Templates(directory="templates")
templates.env.autoescape = True

_STATIC_DIR = Path("static")
_hash_cache: dict[str, str] = {}


def static_url(request: Request, path: str) -> str:
    """Build a static asset URL with a content-hash cache-busting query string.

    The application serves static files with long-lived immutable cache headers
    (see ``CachedStaticFiles``), which is optimal for performance but means a
    browser will not revalidate a file until the cache expires. Appending a
    short hash of the file's content makes the URL change whenever the file
    changes, so updated JavaScript/CSS is picked up on the next page load
    without waiting for the cache to expire.

    Args:
        request: The current ASGI request (provides the static URL prefix).
        path: Static asset path relative to the ``static`` directory,
            e.g. ``js/main.js``.

    Returns:
        The asset URL with a ``?v=<hash>`` query string appended.
    """
    file_path = _STATIC_DIR / path
    digest = _hash_cache.get(path)
    if digest is None:
        try:
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]
        except OSError:
            digest = "missing"
        _hash_cache[path] = digest
    return f"{request.url_for('static', path=path)}?v={digest}"


templates.env.globals["static_url"] = static_url
