# Glyph API Reference

This document provides a comprehensive reference for the Glyph REST API.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Most API endpoints require authentication via JWT Bearer token. Include the token in the `Authorization` header:

```
Authorization: Bearer <your_access_token>
```

### Obtaining a Token

```bash
curl -X POST http://localhost:8000/auth/token \
  -d "username=admin&password=password"
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

## Endpoints

### Health Checks

#### GET /health

Liveness probe for orchestrators.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok"
}
```

#### GET /ready

Readiness probe checking dependency availability.

```bash
curl http://localhost:8000/ready
```

Response:
```json
{
  "status": "ok",
  "components": {
    "database": "ok"
  }
}
```

### Authentication

#### POST /auth/register

Register a new user.

**Request Body:**
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "New User"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "username": "newuser",
  "email": "user@example.com",
  "full_name": "New User",
  "is_active": true,
  "permissions": ["read"]
}
```

#### POST /auth/token

Authenticate and obtain tokens.

**Request:** Form-encoded `username` and `password`.

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### POST /auth/refresh

Refresh access token.

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

#### POST /auth/logout

Log out and invalidate cookies.

**Headers:** `Authorization: Bearer <token>`

**Response:** `200 OK`

### Binaries

#### POST /api/v1/binaries/upload

Upload a binary file for analysis.

**Request:** `multipart/form-data` with `file` field.

**Response:** `201 Created`
```json
{
  "id": 1,
  "filename": "malware_sample.exe",
  "file_size": 1234567,
  "md5": "d41d8cd98f00b204e9800998ecf8427e",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "status": "uploaded"
}
```

#### GET /api/v1/binaries

List all uploaded binaries.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "filename": "malware_sample.exe",
    "status": "processed",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

#### GET /api/v1/binaries/{binary_id}

Get details for a specific binary.

**Response:** `200 OK`
```json
{
  "id": 1,
  "filename": "malware_sample.exe",
  "file_size": 1234567,
  "md5": "d41d8cd98f00b204e9800998ecf8427e",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "status": "processed",
  "functions": [...],
  "created_at": "2024-01-01T00:00:00"
}
```

#### DELETE /api/v1/binaries/{binary_id}

Delete a binary and associated data.

**Response:** `204 No Content`

### Models

#### POST /api/v1/models

Create a new ML model.

**Request:** `multipart/form-data` with `name`, `description`, and model file.

**Response:** `201 Created`
```json
{
  "id": 1,
  "name": "trojan_detector",
  "description": "Model for detecting trojan malware",
  "accuracy": 0.95,
  "created_at": "2024-01-01T00:00:00"
}
```

#### GET /api/v1/models

List all trained models.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "trojan_detector",
    "accuracy": 0.95,
    "created_at": "2024-01-01T00:00:00"
  }
]
```

#### DELETE /api/v1/models/{model_id}

Delete a model.

**Response:** `204 No Content`

### Predictions

#### POST /api/v1/predictions

Run a prediction on a binary using a model.

**Request Body:**
```json
{
  "binary_id": 1,
  "model_id": 1
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "binary_id": 1,
  "model_id": 1,
  "status": "pending",
  "created_at": "2024-01-01T00:00:00"
}
```

#### GET /api/v1/predictions

List all predictions.

**Response:** `200 OK`

#### GET /api/v1/predictions/{prediction_id}

Get prediction results.

**Response:** `200 OK`
```json
{
  "id": 1,
  "binary_id": 1,
  "model_id": 1,
  "status": "completed",
  "results": [
    {
      "function_name": "func_1234",
      "prediction": "malicious",
      "confidence": 0.95
    }
  ],
  "created_at": "2024-01-01T00:00:00"
}
```

### Dangerous Functions

#### GET /api/v1/dangerous_functions

List known dangerous functions.

**Response:** `200 OK`
```json
[
  {
    "name": "VirtualAllocEx",
    "category": "Memory Manipulation",
    "description": "Allocates memory in another process"
  }
]
```

#### GET /api/v1/dangerous_functions/search?q=VirtualAlloc

Search dangerous functions by name.

**Response:** `200 OK`

### Tasks

#### GET /api/v1/tasks

List processing tasks.

**Response:** `200 OK`

#### GET /api/v1/tasks/{task_id}

Get task status and results.

**Response:** `200 OK`
```json
{
  "id": 1,
  "status": "completed",
  "progress": 100,
  "result": {...},
  "created_at": "2024-01-01T00:00:00"
}
```

## Error Responses

| Status Code | Description |
|---|---|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 413 | Payload Too Large - File exceeds size limit |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

Error Response Format:
```json
{
  "detail": "Error description"
}
```

## Rate Limiting

| Endpoint | Limit |
|---|---|
| /auth/login | 5 requests per minute |
| /auth/register | 3 requests per minute |
| /auth/refresh | 10 requests per minute |
| General API | 100 requests per minute |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Time until limit resets
