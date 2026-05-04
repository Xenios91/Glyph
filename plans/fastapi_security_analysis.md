# FastAPI Security Recommendations Analysis

## Overview

This document analyzes the FastAPI documentation's recommended approach for user security and compares it with the current Glyph implementation.

---

## FastAPI's Recommended Security Approach

Based on the [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/), here are the key recommendations:

### 1. **OAuth2 with Password Flow + JWT Tokens** (Primary Recommendation)

FastAPI's **officially recommended** approach for user authentication is:

- **OAuth2 Password Flow** with `OAuth2PasswordBearer`
- **JWT (JSON Web Tokens)** for stateless authentication
- **Bearer Token** scheme in the `Authorization` header

#### Key Components:

```python
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
```

FastAPI recommends using `OAuth2PasswordRequestForm` for the login endpoint, which is the standard OAuth2 password grant type. This provides:
- Standardized request format (`username`, `password`, `grant_type`, `scope`, `client_id`, `client_secret`)
- Built-in compatibility with OAuth2 clients
- Proper content-type handling (`application/x-www-form-urlencoded`)

### 2. **JWT Token Structure**

FastAPI recommends:
- **Short-lived Access Tokens** (15 minutes is recommended)
- **Refresh Tokens** for obtaining new access tokens without re-authentication
- **HS256** or **RS256** algorithm
- Include `sub` (subject/user_id), `exp` (expiration), and optionally `type` claim

### 3. **Security Best Practices from FastAPI Docs**

| Practice | Recommendation |
|----------|----------------|
| Token Storage | Use `Authorization: Bearer <token>` header |
| Password Hashing | Use `passlib` with `bcrypt` |
| Token Expiration | Short-lived access tokens (15 min) |
| Secret Key | Use environment variables, never hardcode |
| CORS | Configure explicitly for production |
| HTTPS | Required in production |

---

## Current Glyph Implementation Analysis

### What Glyph Does Right ✓

| Feature | Status | Notes |
|---------|--------|-------|
| OAuth2PasswordBearer | ✓ Implemented | Uses `OAuth2PasswordBearer(tokenUrl="/auth/token")` |
| JWT Tokens | ✓ Implemented | Uses `joserfc` library (modern, maintained) |
| Bearer Authentication | ✓ Implemented | Proper `Authorization: Bearer <token>` header |
| Access + Refresh Tokens | ✓ Implemented | 15-min access, 7-day refresh tokens |
| HS256 Algorithm | ✓ Implemented | Standard symmetric signing |
| Short-lived Access Tokens | ✓ Implemented | 15 minutes |
| Cookie Support | ✓ Implemented | `access_token_cookie` for web UI |
| API Key Support | ✓ Implemented | Fallback authentication mechanism |
| Rate Limiting | ✓ Implemented | Login, registration, password change |
| Brute-force Protection | ✓ Implemented | `LoginFailureTracker` class |
| CSRF Protection | ✓ Implemented | Separate middleware |
| Security Logging | ✓ Implemented | Structured logging with rate limiting |
| Request Context | ✓ Implemented | User context propagation |

### Areas for Improvement ⚠️

#### 1. **Login Endpoint Uses JSON Instead of OAuth2 Form Data**

**Current Implementation:**
```python
@router.post("/token")
async def login(
    request: Request,
    credentials: UserLogin,  # Pydantic model from JSON body
    ...
) -> Response:
```

**FastAPI's Recommended Approach:**
```python
@router.post("/token")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    ...
) -> dict:
    username = form_data.username
    password = form_data.password
    # ... authenticate user
```

**Why this matters:**
- `OAuth2PasswordRequestForm` is the **standard OAuth2 password grant** format
- Expected content-type: `application/x-www-form-urlencoded`
- Better compatibility with OAuth2 clients and libraries
- Follows the OAuth2 RFC 6749 specification

#### 2. **Consider RS256 for Production**

**Current:** HS256 (symmetric - same key for signing and verification)

**FastAPI Recommendation:** For production systems, consider **RS256** (asymmetric - public/private key pair):
- Public key can be exposed for token verification
- Private key kept secure for signing
- Better for distributed systems and microservices

#### 3. **Token Response Format**

**Current:** Returns custom `TokenResponse` model with JSON body and cookies.

**FastAPI's Standard Pattern:**
```python
return {
    "access_token": access_token,
    "token_type": "bearer",
    "expires_in": 900  # 15 minutes in seconds
}
```

The current implementation includes `refresh_token` in the response, which is fine but deviates slightly from the minimal OAuth2 pattern.

---

## Comparison Summary

| Aspect | FastAPI Recommendation | Current Glyph | Match? |
|--------|----------------------|---------------|--------|
| Authentication Scheme | OAuth2 Bearer | OAuth2 Bearer | ✓ |
| Token Type | JWT | JWT | ✓ |
| Login Format | OAuth2PasswordRequestForm | JSON Body | ⚠️ |
| Access Token Lifetime | 15 minutes | 15 minutes | ✓ |
| Refresh Tokens | Recommended | Implemented | ✓ |
| Algorithm | HS256 or RS256 | HS256 | ✓ |
| Password Hashing | passlib + bcrypt | (Check implementation) | ? |
| API Keys | Optional | Implemented | ✓ |
| Rate Limiting | Recommended | Implemented | ✓ |
| CSRF Protection | For cookie-based auth | Implemented | ✓ |
| Security Logging | Recommended | Implemented | ✓ |

---

## Recommendation

### The Current Implementation is **Mostly Aligned** with FastAPI Best Practices

The Glyph project follows the **OAuth2 Bearer + JWT** pattern that FastAPI recommends. The main deviation is:

1. **Login Endpoint Format**: Uses JSON body instead of `OAuth2PasswordRequestForm`
   - **Impact**: Low - Works correctly but less standard
   - **Fix**: Change to use `OAuth2PasswordRequestForm` for better OAuth2 compliance

2. **Algorithm Choice**: HS256 is fine for most use cases
   - **Impact**: Low - HS256 is recommended by FastAPI for simplicity
   - **Consider**: RS256 only if distributing verification across services

### What FastAPI Recommends (Summary)

```
┌─────────────────────────────────────────────────────────────┐
│           FastAPI Recommended Security Stack                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. OAuth2PasswordBearer (Authorization: Bearer)            │
│         ↓                                                    │
│  2. OAuth2PasswordRequestForm (Login Endpoint)              │
│         ↓                                                    │
│  3. JWT Tokens (HS256/RS256)                                │
│     ├── Access Token (15 min)                               │
│     └── Refresh Token (7 days)                              │
│         ↓                                                    │
│  4. Password Hashing (passlib + bcrypt)                     │
│         ↓                                                    │
│  5. Dependencies Injection for Current User                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Verdict

**The current implementation uses the recommended FastAPI security approach (OAuth2 Bearer + JWT).** The only notable improvement would be switching the login endpoint to use `OAuth2PasswordRequestForm` for full OAuth2 compliance. The additional features (API keys, rate limiting, CSRF protection, security logging) go **beyond** the basic FastAPI recommendations and represent good security practices.

---

## References

- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI OAuth2 with Password Flow](https://fastapi.tiangolo.com/tutorial/security/first-steps/)
- [FastAPI JWT Security](https://fastapi.tiangolo.com/tutorial/security/advanced-security/)
- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [JWT Best Practices](https://auth0.com/docs/security/tokens/json-web-tokens)
