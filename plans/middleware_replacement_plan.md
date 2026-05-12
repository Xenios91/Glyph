# Middleware Replacement Implementation Plan

## Overview

Replace two in-house middleware components with well-maintained, community-supported libraries:

| Current | Replacement | Purpose |
|---------|-------------|---------|
| [`RequestIDMiddleware`](app/core/request_tracing.py:17) | `asgi-correlation-id` | Request ID tracing and propagation |
| [`RateLimiter`](app/core/rate_limiter.py:15) | `slowapi` | Rate limiting for auth endpoints |

## Python Compatibility

| Library | Supported Versions | Project Version | Compatible? |
|---------|-------------------|-----------------|-------------|
| `asgi-correlation-id` | 3.7 - 3.12+ | 3.11 | Yes |
| `slowapi` | >=3.7, <4.0 | 3.11 | Yes |

---

## Phase 1: Replace Request Tracing with `asgi-correlation-id`

### 1.1 Install dependency

Add to [`requirements.txt`](requirements.txt:1):
```
asgi-correlation-id>=4.3.4
```

### 1.2 Update main.py

**File:** [`main.py`](main.py:14)

**Current:**
```python
from app.core.request_tracing import RequestIDMiddleware
# ...
app.add_middleware(RequestIDMiddleware)
```

**Replace with:**
```python
from asgi_correlation_id import CorrelationIdMiddleware
# ...
app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
```

The library's `CorrelationIdMiddleware` provides the same functionality:
- Extracts `X-Request-ID` from incoming headers (or generates UUID)
- Stores in `request.state.correlation_id`
- Adds `X-Request-ID` to response headers

### 1.3 Adapt request context integration

**File:** [`app/utils/request_context.py`](app/utils/request_context.py:1)

The current middleware sets request context via [`set_request_context()`](app/utils/request_context.py:77). The `asgi-correlation-id` library stores the ID in `request.state.correlation_id` rather than a ContextVar.

**Option A (Recommended):** Keep the custom request context but add a FastAPI dependency to populate it from `request.state.correlation_id`.

Create a new dependency in [`app/auth/dependencies.py`](app/auth/dependencies.py:1):
```python
from fastapi import Request
from app.utils.request_context import set_request_context

async def populate_request_context(request: Request) -> None:
    """Populate request context from correlation ID middleware state."""
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        set_request_context(request_id=correlation_id, clear_unset=True)
```

Add this as a dependency to routers or create middleware that bridges the gap.

**Option B:** Modify [`app/utils/request_context.py`](app/utils/request_context.py:1) to read from `request.state` via a request-scoped ContextVar set by custom bridge middleware.

### 1.4 Update logging integration

**File:** [`app/utils/logging_config.py`](app/utils/logging_config.py:1) (if exists)

The `asgi-correlation-id` library provides a `CorrelationIdFilter` for Python's standard `logging` module. Since the project uses `loguru`, a custom filter may be needed:

```python
from loguru import logger

class CorrelationIdLoguruFilter:
    def __call__(self, record: dict) -> None:
        from asgi_correlation_id import correlation_id
        record["correlation_id"] = correlation_id.get() or "NONE"
```

### 1.5 Remove custom middleware

**Delete:** [`app/core/request_tracing.py`](app/core/request_tracing.py:1)

**Update:** [`app/core/__init__.py`](app/core/__init__.py:9) - Remove export of `RequestIDMiddleware` and `get_request_id_from_scope`.

### 1.6 Update tests

**Files to update:**
- [`tests/test_request_tracing.py`](tests/test_request_tracing.py:1) - Rewrite tests for `asgi-correlation-id` behavior
- [`tests/conftest.py`](tests/conftest.py:1) - Remove any request tracing fixtures

---

## Phase 2: Replace Rate Limiter with `slowapi`

### 2.1 Install dependency

Add to [`requirements.txt`](requirements.txt:1):
```
slowapi>=0.1.9
```

### 2.2 Create slowapi configuration

**New file:** `app/core/rate_limiter.py` (rewrite)

```python
"""Rate limiting configuration using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request

# Create limiter with custom key function for proxy support
def rate_limit_key_func(request: Request) -> str:
    """Extract client IP, respecting trusted proxies."""
    from app.config.settings import get_settings
    settings = get_settings()
    client = getattr(request, "client", None)
    direct_ip = client.host if client else "unknown"

    if settings.trusted_proxies and direct_ip in settings.trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return direct_ip

limiter = Limiter(key_func=rate_limit_key_func)

# Rate limit definitions per endpoint
LOGIN_LIMIT = "10/minute"
REGISTER_LIMIT = "5/5 minutes"
PASSWORD_CHANGE_LIMIT = "5/5 minutes"
REFRESH_LIMIT = "10/minute"
```

### 2.3 Update auth endpoints

**File:** [`app/auth/endpoints.py`](app/auth/endpoints.py:40)

**Current pattern:**
```python
from app.core.rate_limiter import check_rate_limit, login_limiter
# ...
check_rate_limit(login_limiter, request)
```

**Replace with decorator pattern:**
```python
from app.core.rate_limiter import limiter, LOGIN_LIMIT
# ...
@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, ...) -> TokenResponse:
    # Rate limiting handled by decorator
    ...
```

**Endpoints to update:**
| Endpoint | Current Limiter | slowapi Limit |
|----------|----------------|---------------|
| `/auth/register` | `register_limiter` (5/300s) | `"5/5 minutes"` |
| `/auth/login` (OAuth2) | `login_limiter` (10/60s) | `"10/minute"` |
| `/auth/refresh` | `refresh_limiter` (10/60s) | `"10/minute"` |
| `/auth/change-password` | `password_change_limiter` (5/300s) | `"5/5 minutes"` |

### 2.4 Update web endpoints

**File:** [`app/web/endpoints/web.py`](app/web/endpoints/web.py:340)

Apply the same decorator pattern to the web registration endpoint.

### 2.5 Add rate limit exceeded handler

**File:** [`main.py`](main.py:168)

Add exception handler for `RateLimitExceeded`:
```python
from slowapi.errors import RateLimitExceeded

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )
```

Register the slowapi extension:
```python
# In create_app():
limiter.init_app(app)
```

### 2.6 Remove old rate limiter

**Delete:** Original [`app/core/rate_limiter.py`](app/core/rate_limiter.py:1) (after rewriting with slowapi)

**Update:** [`app/core/__init__.py`](app/core/__init__.py:9) - Remove old exports.

### 2.7 Update tests

**Files to update:**
- [`tests/test_rate_limiter.py`](tests/test_rate_limiter.py:1) - Rewrite for slowapi
- [`tests/conftest.py`](tests/conftest.py:35) - Remove `reset_rate_limiters` fixture (slowapi handles this differently)
- [`tests/test_auth/test_endpoints.py`](tests/test_auth/test_endpoints.py:1) - Update rate limit test patterns
- [`tests/test_playwright/conftest.py`](tests/test_playwright/conftest.py:39) - Remove `GLYPH_RATE_LIMIT_*` env vars (slowapi uses string limits)
- [`tests/test_auth/test_playwright_auth_pages.py`](tests/test_auth/test_playwright_auth_pages.py:43) - Same as above

---

## Phase 3: Integration Testing

### 3.1 Verify request tracing
- Start the application and send requests
- Confirm `X-Request-ID` header is in responses
- Confirm correlation ID propagates through request context
- Confirm log output includes correlation ID

### 3.2 Verify rate limiting
- Test each rate-limited endpoint exceeds limits
- Confirm HTTP 429 responses
- Test with trusted proxy headers (`X-Forwarded-For`)
- Verify different IPs have independent limits

### 3.3 Run full test suite
```bash
python -m pytest tests/ -v
```

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `requirements.txt` | Modify | Add `asgi-correlation-id` and `slowapi` |
| `main.py` | Modify | Replace middleware imports, add slowapi handler |
| `app/core/request_tracing.py` | Delete | Replaced by `asgi-correlation-id` |
| `app/core/rate_limiter.py` | Rewrite | Replace with slowapi configuration |
| `app/core/__init__.py` | Modify | Remove old exports |
| `app/auth/endpoints.py` | Modify | Replace `check_rate_limit()` with decorators |
| `app/web/endpoints/web.py` | Modify | Same as above |
| `app/utils/request_context.py` | Modify (optional) | Bridge to correlation_id |
| `app/auth/dependencies.py` | Modify | Add context population dependency |
| `tests/test_request_tracing.py` | Rewrite | Tests for `asgi-correlation-id` |
| `tests/test_rate_limiter.py` | Rewrite | Tests for slowapi |
| `tests/conftest.py` | Modify | Remove old fixtures |
| `tests/test_playwright/conftest.py` | Modify | Remove env var rate limit config |
| `tests/test_auth/test_playwright_auth_pages.py` | Modify | Remove env var rate limit config |

---

## Architecture Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │              FastAPI Application             │
                        └─────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼──────┐  ┌────▼──────┐  ┌────▼──────┐
            │  Correlation  │  │   CSP     │  │   CORS    │
            │   ID MDW     │  │   MDW     │  │   MDW     │
            │ (asgi-corr-  │  │ (custom)  │  │(starlette)│
            │  id lib)     │  │           │  │           │
            └───────┬──────┘  └────┬──────┘  └────┬──────┘
                    │              │               │
                    │              │               │
                    └──────────────┼───────────────┘
                                   │
                    ┌──────────────┼───────────────┐
                    │              │               │
            ┌───────▼──────┐  ┌───▼──────┐  ┌────▼──────┐
            │   Auth       │  │   API    │  │   Web     │
            │   Router     │  │   Router │  │   Router  │
            │              │  │          │  │           │
            │  @limiter    │  │          │  │ @limiter  │
            │  .limit()    │  │          │  │ .limit()  │
            │  (slowapi)   │  │          │  │ (slowapi) │
            └──────────────┘  └──────────┘  └───────────┘
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `asgi-correlation-id` stores ID in `request.state` not ContextVar | Request context breakage | Add bridge dependency to populate ContextVar |
| slowapi decorator pattern changes endpoint signatures | Test breakage | Update all affected tests |
| loguru incompatibility with correlation filter | Missing IDs in logs | Create custom loguru filter |
| Environment variable rate limit overrides lost | Config flexibility reduced | Use slowapi's `application_limits` or custom key function |
