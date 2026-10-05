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

API keys are also supported. Pass the key in the `Authorization` header as a Bearer token (the server falls back to API key verification when the token is not a valid JWT):

```
Authorization: Bearer <your_api_key>
```

### Authentication Endpoints

Base path: `/auth`

#### POST `/register`

Register a new user account.

**Request Body:**
```json
{
  "username": "jdoe",
  "email": "jdoe@example.com",
  "password": "securepassword123",
  "full_name": "Jane Doe"
}
```

- `username` (required, 3-64 chars)
- `email` (required, valid email)
- `password` (required, 8-128 chars)
- `full_name` (optional, max 128 chars)

**Response:** `201 Created`

```json
{
  "id": 1,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

**Errors:**
- `400` — Username or email already registered

---

#### POST `/token`

Authenticate with username and password (OAuth2 password grant, form-encoded). Returns access and refresh tokens, and sets `access_token_cookie` and `refresh_token_cookie` (both HTTP-only) for browser sessions.

**Request:** `application/x-www-form-urlencoded` with `username` and `password` fields.

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**
- `401` — Invalid credentials
- `403` — Account is disabled
- `429` — Too many failed login attempts (account/IP temporarily blocked)

---

#### POST `/refresh`

Exchange a refresh token for a new access and refresh token pair. Also re-sets the token cookies.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOi..."
}
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors:**
- `401` — Invalid, expired refresh token, or user not found/inactive

---

#### GET `/logout` and POST `/logout`

Clear the session by deleting the `access_token_cookie` and `refresh_token_cookie` cookies. For web requests (`Accept: text/html`) the response is a `303` redirect to `/`; for API requests it is a JSON body:

```json
{
  "message": "Logged out successfully"
}
```

---

#### GET `/me`

Get the authenticated user's profile.

**Response:** `200 OK`

```json
{
  "id": 1,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00+00:00"
}
```

---

#### POST `/change-password`

Change the authenticated user's password.

**Request Body:**
```json
{
  "current_password": "oldpassword123",
  "new_password": "newpassword456"
}
```

- `new_password` (required, 8-128 chars)

**Response:** `200 OK`

**Errors:**
- `400` — Current password is incorrect

---

#### POST `/update-profile`

Update the authenticated user's profile.

**Request Body:**
```json
{
  "full_name": "Jane Q. Doe",
  "email": "newemail@example.com"
}
```

All fields are optional; only provided fields are updated.

**Response:** `200 OK`

---

#### GET `/api-keys`

List the authenticated user's API keys (secrets are never returned). Returns a bare JSON array.

**Response:** `200 OK`

```json
[
  {
    "id": 1,
    "name": "ci-pipeline",
    "key_prefix": "glp_ab12",
    "permissions": ["read"],
    "expires_at": null,
    "is_active": true,
    "last_used_at": null,
    "created_at": "2024-01-01T00:00:00+00:00"
  }
]
```

---

#### POST `/api-keys`

Create a new API key. The full secret is returned **only once**, in this response.

**Request Body:**
```json
{
  "name": "ci-pipeline",
  "permissions": ["read"],
  "expires_days": 90
}
```

- `name` (required, 1-128 chars)
- `permissions` (optional, default `["read"]`)
- `expires_days` (optional, 1-365)

**Response:** `201 Created`

```json
{
  "id": 1,
  "name": "ci-pipeline",
  "key_prefix": "glp_ab12",
  "permissions": ["read"],
  "expires_at": "2024-04-01T00:00:00+00:00",
  "is_active": true,
  "last_used_at": null,
  "created_at": "2024-01-01T00:00:00+00:00",
  "secret": "glp_XXXX..."
}
```

---

#### DELETE `/api-keys/{key_id}`

Revoke (delete) an API key.

**Response:** `200 OK`

**Errors:**
- `404` — API key not found

---

## Response Format

Successful responses are wrapped in a standard envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed",
  "metadata": {
    "timestamp": "2024-01-01T00:00:00+00:00",
    "request_id": null
  }
}
```

Error responses follow this format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description"
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00+00:00",
    "request_id": null
  }
}
```

| Status Code | Description |
|---|---|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 413 | Payload Too Large - File exceeds size limit |
| 422 | Unprocessable Entity - Validation error |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Feature disabled or not configured (e.g., LLM analysis) |

---

## Endpoints

### Binaries

Base path: `/api/v1/binaries`

#### POST `/uploadBinary`

Upload a binary file for analysis. The file is validated and persisted, then a background decompilation task is queued.

**Request:** `multipart/form-data` with:
- `binary_file` (required): The binary file to upload.
- `name` (required): Name to assign to the binary.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "binary_id": 1,
    "uuid": "550e8400-e29b-41d4-a716-446655440000"
  },
  "message": "Binary uploaded successfully"
}
```

The `uuid` can be used to track the background decompilation task via `/api/v1/status`.

**Errors:**
- `400` — No file provided, or validation failed (e.g., unsupported file type)
- `413` — File exceeds the maximum size limit

---

#### GET `/list`

List binaries uploaded by the current user (paginated).

**Query Parameters:**
- `page` (optional, default `1`): Page number (1-based).
- `page_size` (optional, default `50`, max `200`): Items per page.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1,
        "name": "malware_sample.exe",
        "file_size": 1234567,
        "mime_type": "application/x-msdownload",
        "function_count": 150,
        "created_at": "2024-01-01T00:00:00+00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50,
    "total_pages": 1
  },
  "message": "Binaries retrieved successfully"
}
```

---

#### GET `/listBins`

List binary filenames (legacy, deprecated). Use `GET /list` for the database-backed listing.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "files": ["malware_sample.exe"]
  },
  "message": "Binaries retrieved successfully"
}
```

---

#### GET `/binaries/{binary_id}`

Get detailed metadata for a specific binary.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "malware_sample.exe",
    "file_size": 1234567,
    "mime_type": "application/x-msdownload",
    "uploaded_by": 1,
    "created_at": "2024-01-01T00:00:00+00:00",
    "modified_at": "2024-01-01T00:00:00+00:00",
    "function_count": 150
  },
  "message": "Binary details retrieved successfully"
}
```

**Errors:**
- `404` — Binary not found
- `403` — Access denied (binary owned by another user)

---

#### GET `/functions/{binary_id}`

List decompiled functions for a specific binary (paginated).

**Query Parameters:**
- `page` (optional, default `1`): Page number (1-based).
- `page_size` (optional, default `50`, max `200`): Items per page.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "function_name": "func_401000",
        "entrypoint": "0x401000",
        "raw_code_lines": 24
      }
    ],
    "total": 150,
    "page": 1,
    "page_size": 50,
    "total_pages": 3
  },
  "message": "Functions retrieved successfully"
}
```

**Errors:**
- `404` — Binary not found
- `403` — Access denied (binary owned by another user)

---

#### DELETE `/binaries/{binary_id}`

Delete a binary and associated data.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "message": "Binary 'sample_app.exe' deleted successfully"
  },
  "message": "Binary deleted successfully"
}
```

**Errors:**
- `404` — Binary not found
- `403` — Access denied (binary owned by another user)

---

#### POST `/uploadBulk`

Upload multiple binary files in a single request. Each file is processed independently and a background decompilation task is queued for each.

**Request:** `multipart/form-data` with:
- `files` (required): Binary files to upload (up to 20).
- `names` (required): Comma-separated names, one per file. If fewer names are provided than files, the original filenames are used.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "name": "sample1.exe",
        "status": "success",
        "binary_id": 1,
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "error": null
      },
      {
        "name": "sample2.exe",
        "status": "error",
        "error": "File exceeds maximum size"
      }
    ],
    "total": 2,
    "successful": 1,
    "failed": 1
  },
  "message": "Bulk upload complete: 1 succeeded, 1 failed"
}
```

**Errors:**
- `400` — More than 20 files submitted

---

### Models

Base path: `/api/v1/models`

#### DELETE `/deleteModel`

Delete a single model by name and all associated predictions.

**Query Parameters:**
- `model_name` (required): Name of the model to delete.

**Response:** `200 OK`

**Errors:**
- `404` — Model not found
- `403` — Access denied (model owned by another user)

---

#### DELETE `/deleteModels`

Delete multiple models by comma-separated names.

**Query Parameters:**
- `model_names` (required): Comma-separated list of model names (max 100).

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "deleted": ["model_a", "model_b"],
    "failed": ["model_c"]
  },
  "message": "Deleted 2 model(s); failed to delete 1: model_c"
}
```

Models that are missing or owned by another user are silently skipped (reported in `failed`) to avoid leaking their existence.

**Errors:**
- `400` — No model names provided, or more than 100 names

---

#### GET `/getFunction`

Get decompiled code for a single function from a model.

**Query Parameters:**
- `model_name` (required): Model name.
- `function_name` (required): Function name.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "function_name": "func_401000",
    "entrypoint": "0x401000",
    "tokens": "..."
  },
  "message": "Function retrieved successfully"
}
```

**Errors:**
- `404` — Function not found
- `403` — Access denied (function owned by another user)

---

#### GET `/getFunctions`

List all extracted functions for a trained model.

**Query Parameters:**
- `model_name` (required): Model name.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "functions": [
      {
        "id": 1,
        "function_name": "func_401000",
        "entrypoint": "0x401000",
        "tokens": "..."
      }
    ]
  },
  "message": "Functions retrieved successfully"
}
```

---

#### GET `/getPredictionDetails`

Get detailed prediction results for a specific function, comparing model and prediction tokens.

**Query Parameters:**
- `model_name` (required): Model name.
- `function_name` (required): Function name.
- `task_name` (required): Prediction task name.

**Response:** `200 OK`

**Errors:**
- `404` — Prediction not found (the model function itself is optional; if it is missing the response still succeeds with a placeholder in place of the model tokens)
- `403` — Access denied (prediction owned by another user)

---

### Predictions

Base path: `/api/v1/predictions`

#### POST `/predict`

Run a prediction on a binary using a trained model. The prediction is queued as a background task; track progress with the returned `uuid`.

**Request Body:**
```json
{
  "modelName": "trojan_detector",
  "taskName": "predict_sample1",
  "uuid": null
}
```

- `modelName` (required): Name of the trained model.
- `taskName` (required): Name of the binary/task to predict on. Must be unique.
- `uuid` (optional): Custom UUID for the prediction task.

**Response:** `201 Created`

```json
{
  "success": true,
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000"
  },
  "message": "Prediction task created successfully"
}
```

**Errors:**
- `400` — `taskName` missing or empty
- `409` — A prediction task with that name already exists

---

#### GET `/getPredictionsList`

List all predictions (paginated).

**Query Parameters:**
- `page` (optional, default `1`): Page number (1-based).
- `page_size` (optional, default `50`, max `200`): Items per page.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "task_name": "predict_001",
        "model_name": "trojan_detector"
      }
    ],
    "total": 12,
    "page": 1,
    "page_size": 50,
    "total_pages": 1
  },
  "message": "Predictions list retrieved successfully"
}
```

---

#### GET `/getPrediction`

Get the results of a specific prediction task for a model.

**Query Parameters:**
- `model_name` (required): Model name.
- `task_name` (required): Prediction task name.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "prediction": {
      "task_name": "predict_001",
      "model_name": "trojan_detector",
      "predictions": { ... }
    }
  },
  "message": "Prediction retrieved successfully"
}
```

**Errors:**
- `404` — Prediction not found
- `403` — Access denied (prediction owned by another user)

---

#### DELETE `/deletePrediction`

Delete a single prediction task by task name.

**Query Parameters:**
- `task_name` (required): Prediction task name.

**Response:** `200 OK`

**Errors:**
- `403` — Access denied (prediction owned by another user)

---

#### DELETE `/deletePredictions`

Delete multiple prediction tasks by comma-separated task names.

**Query Parameters:**
- `task_names` (required): Comma-separated list of prediction task names.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "deleted": ["predict_001", "predict_002"],
    "failed": []
  },
  "message": "Deleted 2 prediction(s)"
}
```

**Errors:**
- `400` — No task names provided

---

#### GET `/getPredictionDetails`

Retrieve detailed prediction results for a specific function by comparing model tokens against prediction tokens.

**Query Parameters:**
- `model_name` (required): Model name.
- `function_name` (required): Function name.
- `task_name` (required): Prediction task name.

**Response:** `200 OK`

**Errors:**
- `404` — Function not found
- `403` — Access denied (model or prediction owned by another user)

---

### Status

Base path: `/api/v1/status`

#### GET `/getStatus`

Get the current status of a task.

**Query Parameters:**
- `uuid` (required): Task UUID.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "status": "completed"
  },
  "message": "Task status retrieved successfully"
}
```

**Errors:**
- `404` — UUID not found
- `403` — Access denied (task owned by another user)

---

#### POST `/statusUpdate`

Update task status. Requires task ownership.

**Request Body:**
```json
{
  "uuid": "uuid-string",
  "status": "completed"
}
```

**Response:** `200 OK`

**Errors:**
- `404` — UUID not found
- `403` — Access denied (task owned by another user)

---

#### GET `/streamStatus`

Subscribe to real-time status updates for a background task using Server-Sent Events (SSE). The server polls the task status at regular intervals and streams events until the task reaches a terminal state (`completed`, `error`, `failed`, `cancelled`) or the timeout is exceeded.

**Query Parameters:**
- `uuid` (required): Task UUID.
- `interval` (optional, default `2.0`, range `0.5`–`30`): Polling interval in seconds.
- `timeout` (optional, default `600`, range `10`–`3600`): Maximum streaming duration in seconds.

**Response:** `200 OK` with `Content-Type: text/event-stream`. Each event is a JSON payload:

```
data: {"type": "progress", "status": "processing", "timestamp": 1704067200.0}

data: {"type": "completed", "status": "completed", "timestamp": 1704067260.0}
```

Event `type` values: `progress` (in-flight), `completed`, `error`, `failed`, `cancelled`, or `timeout` (stream duration exceeded).

**Errors:**
- `404` — Task not found
- `403` — Access denied (task owned by another user)

---

### Config

Base path: `/api/v1/config`

#### POST `/save`

Save application configuration. All fields are optional; only provided fields are updated.

**Request Body:**
```json
{
  "max_file_size_mb": 100,
  "cpu_cores": 4,
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com",
    "port": null,
    "api_path": "/v1/chat/completions",
    "model": "gpt-4o-mini",
    "api_key": "sk-...",
    "timeout_seconds": 120,
    "temperature": 0.0,
    "max_tokens": null,
    "max_concurrent": 5
  }
}
```

- `max_file_size_mb` (optional): Maximum upload size in megabytes (1–2048).
- `cpu_cores` (optional): Number of CPU cores to use (1–`MAX_CPU_CORES`).
- `llm` (optional): Partial LLM endpoint configuration. `base_url` must be a host-only http(s) URL; the path goes in `api_path`. Explicit `null` clears `port` and `max_tokens`; an empty string clears `api_key`.

LLM field ranges: `port` 1–65535, `timeout_seconds` 5–600, `temperature` 0–2, `max_tokens` ≥ 1, `max_concurrent` 1–20.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {},
  "message": "Configuration saved successfully"
}
```

**Errors:**
- `400` — Invalid value: `INVALID_FILE_SIZE`, `INVALID_CPU_CORES`, or an LLM field (`INVALID_LLM_BASE_URL`, `INVALID_LLM_PORT`, `INVALID_LLM_API_PATH`, `INVALID_LLM_MODEL`, `INVALID_LLM_TIMEOUT`, `INVALID_LLM_TEMPERATURE`, `INVALID_LLM_MAX_TOKENS`, `INVALID_LLM_MAX_CONCURRENT`)

---

#### POST `/llm-test`

Send a minimal prompt to the configured LLM endpoint to verify it is reachable.

**Request:** no body.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "ok": true,
    "model": "gpt-4o-mini",
    "elapsed_ms": 412
  },
  "message": "LLM endpoint is reachable"
}
```

If the endpoint is reachable but misbehaves (timeout, non-200 status, unexpected response format, empty content), the response is `200 OK` with `ok: false` and an `error` message.

**Errors:**
- `429` — Rate limit exceeded
- `503` — `LLM_NOT_CONFIGURED` (LLM feature disabled or base URL missing/malformed)

---

### Dangerous Functions

Base path: `/api/v1/dangerous-functions`

#### GET `/catalog`

List all known dangerous functions from the catalog, or filter by category.

**Query Parameters:**
- `category` (optional): Filter by category (e.g., `Buffer Overflow`).

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "categories": ["Buffer Overflow", "Code Injection"],
    "entries": [
      {
        "name": "strcpy",
        "category": "Buffer Overflow",
        "severity": "High",
        "cwe": "CWE-120",
        "description": "Unbounded string copy",
        "safe_alternative": "strlcpy"
      }
    ]
  },
  "message": "Catalog retrieved successfully"
}
```

---

#### GET `/catalog/{function_name}`

Get details for a specific dangerous function entry.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "name": "strcpy",
    "category": "Buffer Overflow",
    "severity": "High",
    "cwe": "CWE-120",
    "description": "Unbounded string copy",
    "safe_alternative": "strlcpy"
  },
  "message": "Catalog entry for 'strcpy' retrieved"
}
```

If the function is not in the catalog, the response is a `200 OK` with the standard error body and code `CATALOG_NOT_FOUND` (no HTTP error status is raised):

```json
{
  "success": false,
  "error": {
    "code": "CATALOG_NOT_FOUND",
    "message": "Function 'foo' not found in catalog"
  },
  "metadata": {
    "timestamp": "2024-01-01T00:00:00+00:00",
    "request_id": null
  }
}
```

---

#### GET `/available-models`

List models and prediction tasks available for dangerous function scanning (scoped to targets the current user can access).

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "models": ["trojan_detector"],
    "prediction_tasks": ["predict_001"]
  },
  "message": "Available targets retrieved"
}
```

---

#### POST `/scan`

Scan a model, prediction task, or binary for dangerous functions. At least one of `modelName`, `taskName`, or `binaryId` must be provided; if more than one is given, `modelName` takes precedence. The report is persisted so it can be restored via `GET /scan-results`.

**Request Body:**
```json
{
  "modelName": "trojan_detector",
  "taskName": null,
  "binaryId": null
}
```

- `modelName` (optional): Model name to scan.
- `taskName` (optional): Prediction task name to scan instead.
- `binaryId` (optional): Binary ID to scan directly from the library.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "model_name": "trojan_detector",
    "total_functions_scanned": 150,
    "total_found": 12,
    "critical_count": 2,
    "high_count": 5,
    "medium_count": 4,
    "low_count": 1,
    "results": [
      {
        "function_name": "strcpy",
        "containing_function": "func_401000",
        "entrypoint": "0x401000",
        "category": "Buffer Overflow",
        "severity": "High",
        "cwe": "CWE-120",
        "description": "Buffer overflow via unbounded string copy",
        "safe_alternative": "strncpy",
        "usage_context": ["char buf[64];", "strcpy(buf, input);"],
        "containing_function_code": "..."
      }
    ]
  },
  "message": "Scan complete: 12 dangerous functions found"
}
```

The `message` is `"Scan complete: N dangerous functions found"` when matches exist, or `"No functions found for '<target>'"` when the target has no functions.

**Errors:**
- `400` — None of `modelName`, `taskName`, or `binaryId` provided
- `404` — Model, prediction task, or binary not found
- `403` — Access denied (target owned by another user)
- `500` — Prediction data could not be deserialized (corrupt or failed security validation)

---

#### POST `/llm-analysis`

Send scanner findings to the user-configured OpenAI-compatible chat completions endpoint for analysis. No re-scan is performed — the client supplies findings obtained from a prior scan. When `save` is `true` (the default), results are upserted to the database.

**Request Body:**
```json
{
  "target_name": "trojan_detector",
  "save": true,
  "findings": [
    {
      "function_name": "strcpy",
      "containing_function": "func_401000",
      "entrypoint": "0x401000",
      "category": "Buffer Overflow",
      "severity": "high",
      "cwe": "CWE-120",
      "description": "Buffer overflow via unbounded string copy",
      "safe_alternative": "strncpy",
      "usage_context": ["char buf[64];", "strcpy(buf, input);"],
      "containing_function_code": "..."
    }
  ]
}
```

- `target_name` (required, 1-128 chars): Stable name of the scanned target, typically the scan's `model_name`.
- `save` (optional, default `true`): Persist results to the database.
- `findings` (required, 1-100 items): Scanner findings in the same shape as the scan response `results` array.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "target_name": "trojan_detector",
    "model": "gpt-4o-mini",
    "total": 2,
    "succeeded": 1,
    "failed": 1,
    "saved": true,
    "results": {
      "0": {
        "status": "success",
        "analysis": "1) Exploitability: ...",
        "error": "",
        "model": "gpt-4o-mini",
        "elapsed_ms": 1832
      },
      "1": {
        "status": "error",
        "analysis": "",
        "error": "Request timed out after 120s",
        "model": "",
        "elapsed_ms": 120001
      }
    }
  },
  "message": "LLM analysis complete: 1/2 succeeded"
}
```

`results` is keyed by the zero-based index of each finding in `findings`. Per-finding failures (timeout, non-200 HTTP status, unexpected response format) are reported inside `results` with `status: "error"`; `error` is `""` on success. `saved` is `false` when persistence is disabled or fails (the analysis itself still succeeds).

**Errors:**
- `404` — `SCAN_NOT_FOUND` (no stored scan report for `target_name`; run a scan first)
- `422` — Validation error (missing `target_name`, empty `findings`, or more than 100 findings)
- `429` — Rate limit exceeded (default 10 per minute)
- `503` — `LLM_NOT_CONFIGURED` (LLM feature disabled or base URL missing/malformed)

---

#### GET `/llm-results`

Retrieve stored LLM analysis results for a scanned target.

**Query Parameters:**
- `target_name` (required, 1-128 chars): Name of the scanned target.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "target_name": "trojan_detector",
    "count": 1,
    "results": [
      {
        "function_name": "strcpy",
        "containing_function": "func_401000",
        "entrypoint": "0x401000",
        "status": "success",
        "analysis": "1) Exploitability: ...",
        "error": "",
        "model_name": "gpt-4o-mini",
        "elapsed_ms": 1832,
        "modified_at": "2026-09-18T12:04:11.123456+00:00"
      }
    ]
  },
  "message": "LLM results retrieved for 'trojan_detector'"
}
```

An empty `results` list (`count: 0`) is a valid response when nothing has been saved for the target yet.

**Errors:**
- `422` — Missing or empty `target_name`

---

#### DELETE `/llm-results`

Delete the stored LLM analysis results for a target. The stored scan report is **not** affected.

**Query Parameters:**
- `target_name` (required, 1-128 chars): Name of the scanned target.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": "deleted",
  "message": "Stored LLM results deleted for 'trojan_detector'"
}
```

`data` is `not_found` when nothing was stored for the target.

**Errors:**
- `422` — Missing or empty `target_name`

---

#### GET `/scan-results`

Retrieve the last stored scan report for a target.

**Query Parameters:**
- `target_name` (required, 1-256 chars): Name of the scanned target.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "model_name": "trojan_detector",
    "total_functions_scanned": 1234,
    "total_found": 1,
    "critical_count": 0,
    "high_count": 1,
    "medium_count": 0,
    "low_count": 0,
    "results": [
      {
        "function_name": "strcpy",
        "containing_function": "func_401000",
        "entrypoint": "0x401000",
        "category": "Buffer Overflow",
        "severity": "High",
        "cwe": "CWE-120",
        "description": "...",
        "safe_alternative": "strlcpy",
        "usage_context": ["strcpy(a, b);"],
        "containing_function_code": "..."
      }
    ],
    "modified_at": "2026-09-18T12:04:11.123456+00:00"
  },
  "message": "Stored scan results retrieved for 'trojan_detector'"
}
```

`data` is `null` when the target has never been scanned (no stored report).

**Errors:**
- `422` — Missing or empty `target_name`

---

#### DELETE `/scan-results`

Delete the stored scan report **and** the stored LLM analysis results for a target. Use `DELETE /llm-results` to remove only the LLM results while keeping the scan report.

**Query Parameters:**
- `target_name` (required, 1-256 chars): Name of the scanned target.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": "deleted",
  "message": "Stored scan results and LLM results deleted for 'trojan_detector'"
}
```

`data` is `not_found` when neither a scan report nor LLM results were stored for the target.

**Errors:**
- `422` — Missing or empty `target_name`

---

### Call Graph

Base path: `/api/v1/call-graph`

#### GET `/{binary_id}/graph`

Generate a function call graph for the specified binary by parsing decompiled C code for call sites. Returns all nodes (functions) and edges (call relationships) in the graph.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "binary_id": 1,
    "nodes": [
      {
        "name": "main",
        "entrypoint": "0x401000",
        "callers": [],
        "callees": ["sub_401100"]
      }
    ],
    "edges": [
      {
        "caller": "main",
        "callee": "sub_401100",
        "call_count": 1
      }
    ],
    "total_nodes": 2,
    "total_edges": 1,
    "entry_points": ["main"]
  },
  "message": "Call graph generated successfully"
}
```

**Errors:**
- `404` — Binary not found
- `403` — Access denied (binary owned by another user)

---

#### GET `/{binary_id}/callers/{function_name}`

Get all functions that call the specified function within a binary. Generates the call graph on-demand if not cached.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "function_name": "sub_401100",
    "callers": ["main"],
    "caller_count": 1
  },
  "message": "Found 1 caller(s) for 'sub_401100'"
}
```

**Errors:**
- `404` — Binary or function not found
- `403` — Access denied (binary owned by another user)

---

#### GET `/{binary_id}/callees/{function_name}`

Get all functions called by the specified function within a binary. Generates the call graph on-demand if not cached.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "function_name": "main",
    "callees": ["sub_401100"],
    "callee_count": 1
  },
  "message": "Found 1 callee(s) for 'main'"
}
```

**Errors:**
- `404` — Binary or function not found
- `403` — Access denied (binary owned by another user)

---

### Tasks

Base path: `/api/v1/tasks`

#### POST `/execute`

Execute an analysis task on a previously uploaded binary.

**Request Body:**
```json
{
  "binary_id": 1,
  "task_type": "code_reuse",
  "task_name": "analyze_sample",
  "model_name": null,
  "ml_class_type": null
}
```

**Task Types:**
- `code_reuse` — Code reuse detection
- `dangerous_functions` — Dangerous function scanning
- `ml_training` — ML model training
- `ml_prediction` — ML model prediction
- `similarity_computation` — Binary similarity computation

**Notes:**
- `model_name` is required for `ml_training` and `ml_prediction` tasks.
- `ml_class_type` is required for `ml_training` tasks.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "code_reuse",
    "binary_id": 1,
    "status": "starting"
  },
  "message": "Task code_reuse queued successfully"
}
```

**Errors:**
- `404` — Binary not found
- `403` — Access denied (binary owned by another user)
- `400` — Missing `model_name` or `ml_class_type` for ML tasks

---

#### GET `/{task_uuid}/results`

Retrieve results for a completed task. The `result` payload structure depends on the task type.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "result": { ... }
  },
  "message": "Task results retrieved"
}
```

**Errors:**
- `404` — Task not found, or results not available yet
- `403` — Access denied (task owned by another user)

---

#### GET `/{task_uuid}/status`

Check the current status of a task.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed"
  },
  "message": "Task status retrieved"
}
```

**Errors:**
- `404` — Task not found
- `403` — Access denied (task owned by another user)

---

#### POST `/similarity-computation`

Start a new similarity computation across a set of binaries.

**Request Body:**
```json
{
  "binary_ids": [1, 2, 3],
  "task_name": "similarity_analysis",
  "match_threshold": 0.7
}
```

- `task_name` (required, 1-128 chars)
- `binary_ids` (required, min 2): IDs of the binaries to compare. All must belong to the current user.
- `match_threshold` (optional, default `0.7`, range `0.0`–`1.0`)

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "similarity_computation",
    "binary_id": 1,
    "status": "starting"
  },
  "message": "Similarity computation queued successfully"
}
```

**Errors:**
- `404` — A binary was not found
- `403` — Access denied (a binary is owned by another user)

---

#### GET `/similarity-computations`

List all saved similarity computations for the current user, ordered by creation date.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "task_name": "similarity_analysis",
      "binary_count": 3,
      "total_comparisons": 3,
      "status": "completed",
      "created_at": "2024-01-01T00:00:00+00:00"
    }
  ],
  "message": "Similarity computations retrieved"
}
```

---

#### GET `/similarity-computations/{computation_id}`

Get a specific similarity computation and its full pairwise similarity matrix.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "computation_id": 1,
    "task_name": "similarity_analysis",
    "binary_count": 3,
    "total_comparisons": 3,
    "status": "completed",
    "matrix": [
      {
        "binary_a_id": 1,
        "binary_a_name": "sample1.exe",
        "binary_b_id": 2,
        "binary_b_name": "sample2.exe",
        "overall_similarity": 0.82,
        "matched_function_count": 41,
        "total_function_comparisons": 50
      }
    ]
  },
  "message": "Similarity computation retrieved"
}
```

**Errors:**
- `404` — Computation not found
- `403` — Access denied (computation owned by another user)

---

#### DELETE `/similarity-computations/{computation_id}`

Delete a saved similarity computation and its pairwise results.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "id": "1"
  },
  "message": "Similarity computation deleted"
}
```

**Errors:**
- `404` — Computation not found
- `403` — Access denied (computation owned by another user)

---

## Rate Limiting

| Endpoint | Limit |
|---|---|
| Login | Configurable (default: 10 per minute) |
| Registration | Configurable (default: 5 per 5 minutes) |
| Password Change | Configurable (default: 5 per 5 minutes) |
| Token Refresh | Configurable (default: 10 per minute) |
| LLM Analysis (`/llm-analysis`, `/llm-test`) | Configurable (default: 10 per minute) |

Rate limits are configurable via environment variables:
- `GLYPH_RATE_LIMIT_LOGIN_MAX`
- `GLYPH_RATE_LIMIT_LOGIN_WINDOW`
- `GLYPH_RATE_LIMIT_REGISTER_MAX`
- `GLYPH_RATE_LIMIT_REGISTER_WINDOW`
- `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX`
- `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW`
- `GLYPH_RATE_LIMIT_REFRESH_MAX`
- `GLYPH_RATE_LIMIT_REFRESH_WINDOW`
- `GLYPH_RATE_LIMIT_LLM_ANALYSIS_MAX`
- `GLYPH_RATE_LIMIT_LLM_ANALYSIS_WINDOW`
