# Authlib Authentication Implementation Plan for Glyph

## Overview

This document outlines the implementation of authlib-based authentication for the Glyph binary analysis tool. The implementation will support:

1. **Web UI Authentication**: User accounts with session-based authentication for the web interface
2. **API Authentication**: JWT-based authentication for programmatic API access via scripts

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authentication Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Web UI Auth                            │  │
│  │              (Cookie-based Sessions)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Authlib JWT Handler (JOSE)                  │  │
│  │         - Token generation/verification                  │  │
│  │         - Access tokens & refresh tokens                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Authentication Dependencies                     │  │
│  │         - User model & validation                         │  │
│  │         - Permission checking                             │  │
│  │         - Session management                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Database Layer                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    User Table                             │  │
│  │  - id, username, email, hashed_password                   │  │
│  │  - permissions, is_active, created_at, updated_at         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 API Token Table                           │  │
│  │  - id, user_id, name, hashed_token, token_prefix          │  │
│  │  - permissions, expires_at, is_active, last_used_at       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Authentication Flow

### Web UI Authentication Flow

```
User Login (Web)
     │
     ▼
┌─────────────────────────────────────────┐
│ POST /auth/token                        │
│ (form data: username, password)         │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Validate credentials against User table │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Generate JWT access & refresh tokens    │
│ (using authlib.jose)                    │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Set tokens in HTTP-only cookies         │
│ - access_token_cookie (15 min)          │
│ - refresh_token_cookie (7 days)         │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Redirect to home page                   │
└─────────────────────────────────────────┘

Subsequent Web Requests:
     │
     ▼
┌─────────────────────────────────────────┐
│ Request with access_token cookie        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Middleware validates token              │
│ - If expired, auto-refresh with         │
│   refresh token cookie                  │
│ - If refresh expired, redirect to login │
└─────────────────────────────────────────┘
```

### API Token Creation Flow (User Profile)

```
User creates API token in profile:
     │
     ▼
┌─────────────────────────────────────────┐
│ POST /auth/api-tokens                   │
│ (authenticated web request)             │
│ {                                       │
│   "name": "My Script Token",            │
│   "permissions": ["read", "write"],     │
│   "expires_days": 30                    │
│ }                                       │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Generate unique API token               │
│ - Hash token with bcrypt/argon2         │
│ - Store hash in database                │
│ - Return plaintext token ONCE           │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Display token to user (copy/save)       │
│ ⚠️ Token shown only once!               │
└─────────────────────────────────────────┘
```

### API Authentication Flow (Using API Token)

```
API Client Request (Script/Program)
     │
     ▼
┌─────────────────────────────────────────┐
│ Any API endpoint                        │
│ Authorization: Bearer <api_token>       │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Validate API token                      │
│ - Check token prefix matches            │
│ - Verify hashed token in database       │
│ - Check expiration & active status      │
│ - Verify permissions                    │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ Execute request as user                 │
│ (update last_used_at)                   │
└─────────────────────────────────────────┘
```

## File Structure

```
app/
├── auth/
│   ├── __init__.py              # Public API exports
│   ├── jwt_handler.py           # Authlib JWT handler
│   ├── dependencies.py          # Auth dependencies & user model
│   ├── endpoints.py             # Auth endpoints (login, register, etc.)
│   ├── oauth2.py                # OAuth2 provider configuration
│   ├── schemas.py               # Pydantic schemas for auth
│   └── repository.py            # User & API key repository
├── database/
│   ├── models.py                # Add User, APIKey models
│   └── repositories/
│       └── user_repository.py   # User CRUD operations
├── config/
│   └── settings.py              # Add auth settings
└── core/
    └── lifespan.py              # Add auth initialization
```

## Implementation Steps

### Step 1: Add Dependencies

Add authlib to requirements.txt:
```
authlib==1.3.0
argon2-cffi==23.1.0
argon2-cffi-bindings==21.2.0
```

### Step 2: Update Database Models

Add User and APIKey models to `app/database/models.py`:

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int]
    username: Mapped[str]  # unique
    email: Mapped[str]     # unique
    hashed_password: Mapped[str]
    full_name: Mapped[str]
    permissions: Mapped[str]  # JSON array
    is_active: Mapped[bool]
    created_at: Mapped[datetime]
    modified_at: Mapped[datetime]

class APIKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int]
    user_id: Mapped[int]  # foreign key to User
    name: Mapped[str]
    hashed_key: Mapped[str]
    key_prefix: Mapped[str]  # for display
    permissions: Mapped[str]  # JSON array
    expires_at: Mapped[datetime]
    is_active: Mapped[bool]
    last_used_at: Mapped[datetime]
    created_at: Mapped[datetime]
```

### Step 3: Configure Settings

Add to `app/config/settings.py`:

```python
class GlyphSettings(BaseSettings):
    # Existing settings...
    
    # JWT Settings
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for JWT signing"
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)
    
    # OAuth2 Settings
    oauth2_enabled: bool = Field(default=False)
    oauth2_session_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
```

### Step 4: Create JWT Handler

Create `app/auth/jwt_handler.py`:

```python
from authlib.jose import jwt, JWT
from authlib.jose.errors import DecodeError, InvalidTokenError

class JWTHandler:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.jwt = JWT()
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(self, subject: str, extra_claims: dict = None) -> str:
        # Generate access token using authlib
        pass
    
    def create_refresh_token(self, subject: str, extra_claims: dict = None) -> str:
        # Generate refresh token using authlib
        pass
    
    def verify_access_token(self, token: str) -> dict:
        # Verify and decode access token
        pass
    
    def verify_refresh_token(self, token: str) -> dict:
        # Verify and decode refresh token
        pass
```

### Step 5: Create Authentication Endpoints

Create `app/auth/endpoints.py`:

```python
# Endpoints:
# POST /auth/token - OAuth2 password grant (login)
# POST /auth/refresh - Refresh access token
# POST /auth/register - Register new user
# POST /auth/logout - Logout (clear cookies for web)
# GET /auth/me - Get current user info
# POST /auth/change-password - Change password
# GET /auth/api-keys - List API keys
# POST /auth/api-keys - Create API key
# DELETE /auth/api-keys/{key_id} - Delete API key
```

### Step 6: Create Authentication Dependencies

Create `app/auth/dependencies.py`:

```python
# Dependencies:
# get_current_user - Extract user from JWT token
# get_current_active_user - Verify user is active
# require_auth - Alias for get_current_user
# require_write_permission - Check write permission
# require_admin_permission - Check admin permission
# get_optional_user - Optional authentication
```

### Step 7: Integrate with Main Application

Update `main.py`:

```python
from app.auth.endpoints import router as auth_router
from app.auth.middleware import AuthMiddleware

app.include_router(auth_router, prefix="/auth")
app.add_middleware(AuthMiddleware)
```

### Step 8: Update Existing Endpoints

Add authentication to protected endpoints:

```python
@app.api.v1.endpoints.binaries.router.post("/upload")
async def upload_binary(
    current_user: User = Depends(get_current_active_user),
    ...
):
    # Protected endpoint
    pass
```

### Step 9: Create Web UI Templates

Create login/register templates:

```
templates/
├── login.html
├── register.html
├── profile.html          # User profile with API token management
└── components/
    └── user_menu.html
```

### Step 10: Write Tests

Create tests for authentication:

```
tests/
└── test_auth/
    ├── test_jwt_handler.py
    ├── test_endpoints.py
    ├── test_dependencies.py
    └── test_repository.py
```

## Security Considerations

1. **Password Hashing**: Use Argon2id for password hashing
2. **JWT Token Security**:
   - Access tokens: Short-lived (15 minutes)
   - Refresh tokens: Longer-lived (7 days), stored in HTTP-only cookies
3. **API Token Security**:
   - Tokens hashed with bcrypt before storage
   - Plaintext token shown only once at creation
   - Tokens can be revoked by user at any time
   - Optional expiration dates
4. **CSRF Protection**: Already implemented, ensure compatibility
5. **Rate Limiting**: Implement rate limiting on auth endpoints
6. **HTTPS**: Enforce HTTPS in production
7. **Secure Cookies**: HttpOnly, Secure, SameSite=Strict

## API Documentation

The authentication endpoints will be documented in FastAPI's automatic OpenAPI documentation at `/docs`.

### Example API Usage with API Token

```bash
# Step 1: User logs in via web UI and creates an API token
# (done through the web interface at /profile)

# Step 2: Use the API token for script-based API access
export GLYPH_API_TOKEN="glp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# List models
curl -X GET "http://localhost:8000/api/v1/models" \
  -H "Authorization: Bearer $GLYPH_API_TOKEN"

# Upload binary for analysis
curl -X POST "http://localhost:8000/api/v1/binaries/upload" \
  -H "Authorization: Bearer $GLYPH_API_TOKEN" \
  -F "file=@/path/to/binary"

# Get prediction status
curl -X GET "http://localhost:8000/api/v1/status/task/{task_id}" \
  -H "Authorization: Bearer $GLYPH_API_TOKEN"
```

### Example Web UI Usage

```python
# Python script using requests with session
import requests

# Create a session
session = requests.Session()

# Login
session.post(
    "http://localhost:8000/auth/token",
    data={"username": "admin", "password": "password"}
)

# Cookies are automatically handled
response = session.get("http://localhost:8000/api/v1/models")
print(response.json())
```

## Migration Plan

1. Implement authentication module (non-breaking)
2. Add User table migration
3. Create default admin user
4. Enable authentication (configurable via settings)
5. Update existing endpoints to require authentication
6. Update web UI with login/register pages

## Testing Checklist

- [ ] User registration works
- [ ] User login returns valid tokens
- [ ] Access token expires after configured time
- [ ] Refresh token generates new access token
- [ ] Invalid tokens are rejected
- [ ] Permission checks work correctly
- [ ] Web UI login sets cookies correctly
- [ ] API key authentication works
- [ ] Logout clears session/cookies
