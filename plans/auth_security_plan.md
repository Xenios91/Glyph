# Authentication Security Plan (Dependencies-Only Approach)

## Overview
This plan outlines the changes needed to secure all functionality behind login using only FastAPI dependencies, without adding custom middleware.

## Current State Analysis

### Authentication System (Already Implemented)
- JWT-based authentication with access and refresh tokens
- API key support for programmatic access
- User repository with password hashing
- Auth endpoints at `/auth/*`

### Available Dependencies in `app/auth/dependencies.py`

| Dependency | Purpose | Behavior |
|------------|---------|----------|
| `get_current_user` | Get authenticated user | Returns 401 if not authenticated |
| `get_current_active_user` | Get authenticated AND active user | Returns 401 if not authenticated, 403 if inactive |
| `get_optional_user` | Get user if authenticated | Returns None if not authenticated (no error) |
| `require_write_permission` | Require write permission | Returns 403 if user lacks permission |
| `require_admin_permission` | Require admin permission | Returns 403 if user lacks permission |

## Implementation Plan (Dependencies Only)

### Phase 1: Update API Endpoints to Require Authentication

Change `get_optional_user` to `get_current_active_user` in:

**1. `app/api/v1/endpoints/predictions.py`**
```python
# Line 153 - get_prediction
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 223 - get_prediction_details  
current_user: Annotated[User, Depends(get_current_active_user)]
```

**2. `app/api/v1/endpoints/models.py`**
```python
# Line 35 - delete_model
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 67 - get_function
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 124 - get_functions
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 160 - get_prediction_details
current_user: Annotated[User, Depends(get_current_active_user)]
```

**3. `app/api/v1/endpoints/status.py`**
```python
# Line 31 - get_status
current_user: Annotated[User, Depends(get_current_active_user)]
```

### Phase 2: Update Web Endpoints to Require Authentication

**File: `app/web/endpoints/web.py`**

Change `get_optional_user` to `get_current_active_user` for protected pages:

```python
# Line 22 - home
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 40 - config
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 80 - get_upload_binary
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 102 - get_list_models
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 126 - get_list_predictions
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 157 - get_prediction_details
current_user: Annotated[User, Depends(get_current_active_user)]

# Line 212 - get_prediction
current_user: Annotated[User, Depends(get_current_active_user)]
```

Keep `get_optional_user` for login/register (to check if already logged in):
```python
# Line 253 - login_page (keep as is)
current_user: Annotated[User | None, Depends(get_optional_user)]

# Line 272 - register_page (keep as is)
current_user: Annotated[User | None, Depends(get_optional_user)]
```

### Phase 3: Update Exception Handler for Web Redirects

**File: `main.py`**

Update the HTTP exception handler to redirect web requests to login on 401:

```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse:
    """Handle HTTP exceptions with redirect to login for 401 on web requests."""
    accept = request.headers.get("Accept", "")
    
    # Redirect to login for 401 on web requests
    if exc.status_code == 401 and "text/html" in accept:
        from fastapi.responses import RedirectResponse
        redirect_url = "/login?redirect=" + request.url.path
        return RedirectResponse(url=redirect_url, status_code=303)
    
    if "text/html" in accept:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": f"Error {exc.status_code}: {exc.detail}"
            },
            status_code=exc.status_code,
        )
    
    # Return JSON for API requests
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail} if isinstance(exc.detail, str) else exc.detail
    )
```

### Phase 4: Update Templates for Auth State

**File: `templates/layout.html`**

Update navbar to show different links based on authentication state:

```html
<nav class="navbar">
    {% if user and user.username %}
        <!-- Authenticated user menu -->
        <a href="/">Home</a>
        <a href="/uploadBinary">Upload Binary</a>
        <a href="/getModels">Models</a>
        <a href="/getPredictions">Predictions</a>
        <a href="/config">Config</a>
        <a href="/profile">Profile</a>
        <a href="/auth/logout">Logout</a>
    {% else %}
        <!-- Unauthenticated user menu -->
        <a href="/login">Login</a>
        <a href="/register">Register</a>
    {% endif %}
</nav>
```

### Phase 5: Add Frontend JavaScript for Auth Handling

**File: `static/js/common.js`**

Add functions to handle 401 responses:

```javascript
// Intercept fetch requests and handle 401
async function authenticatedFetch(url, options = {}) {
    const token = document.cookie.match(/access_token_cookie=([^;]+)/)?.[1];
    const headers = { ...options.headers };
    
    if (token && !headers['Authorization']) {
        headers['Authorization'] = 'Bearer ' + token;
    }
    
    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
    }
    
    return response;
}

// Check auth status on page load
async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/me', {
            headers: { 'Accept': 'application/json' }
        });
        return response.status === 200;
    } catch (error) {
        return false;
    }
}
```

## Endpoints Summary

| Endpoint | Current | Required | Change |
|----------|---------|----------|--------|
| `/auth/register` | None | None | - |
| `/auth/token` | None | None | - |
| `/auth/refresh` | None | None | - |
| `/auth/logout` | None | None | - |
| `/auth/me` | `get_current_active_user` | `get_current_active_user` | - |
| `/login` | `get_optional_user` | `get_optional_user` | - |
| `/register` | `get_optional_user` | `get_optional_user` | - |
| `/profile` | `get_current_active_user` | `get_current_active_user` | - |
| `/` (home) | `get_optional_user` | `get_current_active_user` | **Change** |
| `/config` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/uploadBinary` (GET) | `get_optional_user` | `get_current_active_user` | **Change** |
| `/getModels` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/getPredictions` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/getPrediction` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/getPredictionDetails` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/binaries/uploadBinary` | `get_current_active_user` | `get_current_active_user` | - |
| `/api/v1/binaries/listBins` | `get_current_active_user` | `get_current_active_user` | - |
| `/api/v1/predictions/predict` | `get_current_active_user` | `get_current_active_user` | - |
| `/api/v1/predictions/getPrediction` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/predictions/deletePrediction` | `get_current_active_user` | `get_current_active_user` | - |
| `/api/v1/predictions/getPredictionDetails` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/models/deleteModel` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/models/getFunction` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/models/getFunctions` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/models/getPredictionDetails` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/config/save` | `get_current_active_user` | `get_current_active_user` | - |
| `/api/v1/status/getStatus` | `get_optional_user` | `get_current_active_user` | **Change** |
| `/api/v1/status/statusUpdate` | `get_current_active_user` | `get_current_active_user` | - |

## Files to Modify

| File | Changes |
|------|---------|
| `app/api/v1/endpoints/predictions.py` | 2 dependency changes |
| `app/api/v1/endpoints/models.py` | 4 dependency changes |
| `app/api/v1/endpoints/status.py` | 1 dependency change |
| `app/web/endpoints/web.py` | 7 dependency changes |
| `main.py` | Update exception handler for 401 redirect |
| `templates/layout.html` | Update navbar based on auth state |
| `static/js/common.js` | Add auth handling functions |

## Testing Checklist

- [ ] Unauthenticated user accessing `/` gets redirected to `/login?redirect=/`
- [ ] Unauthenticated user accessing `/uploadBinary` gets redirected to login
- [ ] Unauthenticated user accessing `/getModels` gets redirected to login
- [ ] Unauthenticated user accessing `/getPredictions` gets redirected to login
- [ ] Unauthenticated user CAN access `/login`
- [ ] Unauthenticated user CAN access `/register`
- [ ] API requests without valid token return 401 JSON
- [ ] Logged-in user can access all protected endpoints
- [ ] Logout clears cookies and redirects to home
