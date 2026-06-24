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

## Response Format

Successful responses are wrapped in a standard envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed"
}
```

Error responses follow this format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description"
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
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

---

## Endpoints

### Binaries

Base path: `/api/v1/binaries`

#### POST `/uploadBinary`

Upload a binary file for analysis.

**Request:** `multipart/form-data` with `file` field.

**Response:** `200 OK` (file uploaded and persisted)

---

#### GET `/list`

List all uploaded binaries with structured response.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "binaries": [
      {
        "id": 1,
        "name": "malware_sample.exe",
        "file_size": 1234567,
        "md5": "d41d8cd98f00b204e9800998ecf8427e",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb924..."
      }
    ]
  },
  "message": "Binaries retrieved"
}
```

---

#### GET `/listBins`

List binary names (legacy format).

**Response:** `200 OK`

---

#### GET `/binaries/{binary_id}`

Get details for a specific binary.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "malware_sample.exe",
    "file_size": 1234567,
    "md5": "d41d8cd98f00b204e9800998ecf8427e",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb924...",
    "uploaded_by": 1,
    "created_at": "2024-01-01T00:00:00"
  },
  "message": "Binary detail retrieved"
}
```

---

#### GET `/functions/{binary_id}`

List extracted functions for a specific binary.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "functions": [
      {
        "name": "func_1234",
        "entrypoint": "0x10000",
        "decompiled_code": "int func_1234() { ... }"
      }
    ]
  },
  "message": "Functions retrieved"
}
```

---

#### DELETE `/binaries/{binary_id}`

Delete a binary and associated data.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "message": "Binary deleted successfully"
  },
  "message": "Binary deleted"
}
```

---

### Models

Base path: `/api/v1/models`

#### DELETE `/deleteModel`

Delete a single model by name.

**Query Parameters:**
- `modelName` (required): Name of the model to delete.

**Response:** `200 OK`

---

#### DELETE `/deleteModels`

Delete multiple models.

**Query Parameters:**
- `modelNames` (required): Comma-separated list of model names.

**Response:** `200 OK`

---

#### GET `/getFunction`

Get a single function's decompiled code (renders HTML template).

**Query Parameters:**
- `modelName` (required): Model name.
- `functionName` (required): Function name.

**Response:** `200 OK` (HTML)

---

#### GET `/getFunctions`

List all functions for a model (renders HTML template).

**Query Parameters:**
- `modelName` (required): Model name.

**Response:** `200 OK` (HTML)

---

#### GET `/getPredictionDetails`

Get prediction details for a model (renders HTML template).

**Query Parameters:**
- `modelName` (required): Model name.

**Response:** `200 OK` (HTML)

---

### Predictions

Base path: `/api/v1/predictions`

#### POST `/predict`

Run a prediction on a binary using a trained model.

**Request Body:**
```json
{
  "modelName": "trojan_detector",
  "binaryId": 1
}
```

**Response:** `201 Created`

---

#### GET `/getPredictionsList`

List all predictions.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "task_name": "predict_001",
      "model_name": "trojan_detector",
      "status": "completed"
    }
  ],
  "message": "Predictions retrieved"
}
```

---

#### GET `/getPrediction`

Get prediction details (renders HTML template).

**Query Parameters:**
- `predictionName` (required): Prediction task name.

**Response:** `200 OK` (HTML)

---

#### DELETE `/deletePrediction`

Delete a single prediction.

**Query Parameters:**
- `predictionName` (required): Prediction task name.

**Response:** `200 OK`

---

#### DELETE `/deletePredictions`

Delete multiple predictions.

**Query Parameters:**
- `predictionNames` (required): Comma-separated list of prediction names.

**Response:** `200 OK`

---

#### GET `/getPredictionDetails`

Get prediction function details (renders HTML template).

**Query Parameters:**
- `predictionName` (required): Prediction task name.
- `functionName` (required): Function name.

**Response:** `200 OK` (HTML)

---

### Status

Base path: `/api/v1/status`

#### GET `/getStatus`

Get the current status of a task.

**Query Parameters:**
- `taskUuid` (required): Task UUID.

**Response:** `200 OK`

---

#### POST `/statusUpdate`

Update task status.

**Request Body:**
```json
{
  "taskUuid": "uuid-string",
  "status": "completed"
}
```

**Response:** `200 OK`

---

### Config

Base path: `/api/v1/config`

#### POST `/save`

Save application configuration.

**Request Body:**
```json
{
  "settings": {
    "key": "value"
  }
}
```

**Response:** `200 OK`

---

### Dangerous Functions

Base path: `/api/v1/dangerous-functions`

#### GET `/catalog`

List all known dangerous functions from the catalog.

**Query Parameters:**
- `category` (optional): Filter by category.

**Response:** `200 OK`

---

#### GET `/catalog/{function_name}`

Get details for a specific dangerous function entry.

**Response:** `200 OK`

---

#### GET `/available-models`

List available models for dangerous function scanning.

**Response:** `200 OK`

---

#### POST `/scan`

Scan a model, prediction task, or binary for dangerous functions.

**Request Body:**
```json
{
  "modelName": "trojan_detector",
  "taskName": null,
  "binaryId": null
}
```

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
        "severity": "high",
        "cwe": "CWE-120",
        "description": "Buffer overflow via unbounded string copy",
        "safe_alternative": "strncpy",
        "usage_context": ["char buf[64];", "strcpy(buf, input);"],
        "containing_function_code": "..."
      }
    ]
  },
  "message": "Scan completed"
}
```

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

---

#### GET `/{task_uuid}/results`

Retrieve results for a completed task.

**Response:** `200 OK`

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

**Response:** `200 OK`

---

#### GET `/similarity-computations`

List all saved similarity computations for the current user.

**Response:** `200 OK`

---

#### GET `/similarity-computations/{computation_id}`

Get a specific similarity computation and its pairwise results.

**Response:** `200 OK`

---

#### DELETE `/similarity-computations/{computation_id}`

Delete a saved similarity computation and its pairwise results.

**Response:** `200 OK`

---

## Rate Limiting

| Endpoint | Limit |
|---|---|
| Login | Configurable (default: 5 per minute) |
| Registration | Configurable (default: 3 per minute) |
| Password Change | Configurable (default: 5 per minute) |
| Token Refresh | Configurable (default: 10 per minute) |

Rate limits are configurable via environment variables:
- `GLYPH_RATE_LIMIT_LOGIN_MAX`
- `GLYPH_RATE_LIMIT_LOGIN_WINDOW`
- `GLYPH_RATE_LIMIT_REGISTER_MAX`
- `GLYPH_RATE_LIMIT_REGISTER_WINDOW`
- `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX`
- `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW`
- `GLYPH_RATE_LIMIT_REFRESH_MAX`
- `GLYPH_RATE_LIMIT_REFRESH_WINDOW`
