# Glyph Usage Guide

This guide covers how to use Glyph for binary analysis, model training, and function prediction. It assumes you have already completed the [installation steps](../README.md#getting-started).

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
  - [Registering an Account](#registering-an-account)
  - [Logging In](#logging-in)
  - [API Keys](#api-keys)
- [Web UI Workflows](#web-ui-workflows)
  - [Uploading a Binary](#uploading-a-binary)
  - [Training a Model](#training-a-model)
  - [Making Predictions](#making-predictions)
  - [Browsing Functions](#browsing-functions)
  - [Managing Models](#managing-models)
  - [Configuration](#configuration)
- [API Reference](#api-reference)
  - [Authentication Endpoints](#authentication-endpoints)
  - [Binary Upload](#binary-upload-api)
  - [Model Management](#model-management-api)
  - [Predictions](#predictions-api)
  - [Task Status](#task-status-api)
  - [Configuration](#configuration-api)
- [Processing Pipeline](#processing-pipeline)
- [Configuration File](#configuration-file)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Overview

Glyph is an architecture-independent binary analysis tool that uses Natural Language Processing (NLP) techniques for **cross-architecture function fingerprinting**. The core workflow involves two phases:

1. **Training** — Upload one or more binaries from known sources to train an ML model that learns function signatures.
2. **Prediction** — Upload an unknown binary and use the trained model to identify and classify its functions.

The application supports both a **Web UI** and a **REST API** for all operations. All endpoints require authentication via JWT tokens or API keys.

---

## Authentication

Glyph requires user authentication for all operations. You can authenticate via the web UI login form or programmatically through the API.

### Registering an Account

**Via Web UI:**
1. Navigate to `http://localhost:8000/register`
2. Fill in your username, email, full name, and password
3. Click "Register"

**Via API:**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analyst",
    "email": "analyst@example.com",
    "full_name": "Security Analyst",
    "password": "secure-password-here"
  }'
```

**Response:**

```json
{
  "id": 1,
  "username": "analyst",
  "email": "analyst@example.com",
  "full_name": "Security Analyst",
  "is_active": true,
  "permissions": ["read"]
}
```

### Logging In

**Via Web UI:**
1. Navigate to `http://localhost:8000/login`
2. Enter your username and password
3. Click "Login" — you will be redirected to the main dashboard

**Via API:**

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=analyst&password=secure-password-here"
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

The `access_token` is a JWT token valid for 15 minutes (by default). Use it to authenticate subsequent API requests:

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/api/v1/...
```

### API Keys

API keys provide an alternative to JWT tokens for programmatic access. They are long-lived and can be managed through the API.

**Create an API Key:**

```bash
curl -X POST http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-analysis-key"}'
```

**Response:**

```json
{
  "id": 1,
  "name": "my-analysis-key",
  "key": "glyph_sk_abc123...",
  "user_id": 1,
  "created_at": "2025-01-01T00:00:00"
}
```

> **Important:** The API key secret is only shown once at creation. Store it securely.

**Use an API Key:**

```bash
curl -H "X-API-Key: glyph_sk_abc123..." \
  http://localhost:8000/api/v1/models/getModels
```

**List API Keys:**

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/auth/api-keys
```

**Delete an API Key:**

```bash
curl -X DELETE http://localhost:8000/auth/api-keys/1 \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Web UI Workflows

### Uploading a Binary

1. Navigate to the **Upload** page from the main dashboard
2. Fill in the form fields:
   - **Binary File** — Select an ELF binary file (32-bit or 64-bit)
   - **Model Name** — The name of the ML model to associate with this binary
   - **ML Class Type** — The classification label for this binary (e.g., "malware", "legitimate", "rootkit")
   - **Name** — A human-readable name for this analysis task
   - **Training Data** — Toggle whether this binary is for training (`true`) or prediction (`false`)
3. Click **Upload** to submit the binary for analysis

The upload initiates a background task. You can monitor its status from the dashboard.

### Training a Model

Training requires uploading one or more binaries with the `training_data` flag set to `true`:

1. Upload binaries from known sources (e.g., confirmed malware samples, legitimate binaries)
2. Each binary should be tagged with the same **Model Name** and appropriate **ML Class Type**
3. After all binaries are processed, the model is automatically trained
4. Check the **Models** page to see trained models and their associated functions

**Example Training Workflow:**

| Binary | Model Name | ML Class Type | Training Data |
|--------|-----------|---------------|---------------|
| `malware_sample1.elf` | `malware_detector` | `malware` | `true` |
| `malware_sample2.elf` | `malware_detector` | `malware` | `true` |
| `legit_binary1.elf` | `malware_detector` | `legitimate` | `true` |
| `legit_binary2.elf` | `malware_detector` | `legitimate` | `true` |

After processing, the `malware_detector` model can classify functions in unknown binaries as either `malware` or `legitimate`.

### Making Predictions

1. Upload an unknown binary with `training_data` set to `false`
2. Specify the **Model Name** of a previously trained model
3. Provide a unique **Task Name** for the prediction job
4. After processing, view the prediction results on the **Predictions** page

Each function in the analyzed binary will be classified with a probability score. Functions exceeding the configured `prediction_probability_threshold` (default: 50%) will be highlighted.

### Browsing Functions

1. Navigate to the **Models** page
2. Select a trained model to view its associated functions
3. Click on any function to view its decompiled code, entry point, and token information

### Managing Models

- **View Models** — The Models page lists all trained models with their function counts
- **Delete a Model** — Select a model and click delete (this also removes associated predictions)
- **Delete Multiple Models** — Select multiple models and delete them in batch

### Configuration

1. Navigate to the **Config** page
2. Adjust the following settings:
   - **Max File Size (MB)** — Maximum allowed upload size (1–2048 MB)
   - **CPU Cores** — Number of CPU cores for processing (1–32)
3. Click **Save** to persist changes

---

## API Reference

All API endpoints are prefixed with `/api/v1/` and require authentication unless stated otherwise.

The interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/token` | Login and obtain JWT tokens |
| `POST` | `/auth/refresh` | Refresh an access token |
| `POST` | `/auth/change-password` | Change user password |
| `GET` | `/auth/me` | Get current user profile |
| `PUT` | `/auth/me` | Update user profile |
| `POST` | `/auth/api-keys` | Create an API key |
| `GET` | `/auth/api-keys` | List API keys |
| `DELETE` | `/auth/api-keys/{id}` | Delete an API key |

### Binary Upload API

#### Upload a Binary

```
POST /api/v1/uploadBinary
```

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | The binary file (ELF format) |
| `training_data` | String | No | `"true"` for training, `"false"` for prediction (default: `"false"`) |
| `model_name` | String | Yes | Name of the ML model |
| `ml_class_type` | String | Yes | Classification label |
| `name` | String | Yes | Human-readable task name |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/uploadBinary \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/binary.elf" \
  -F "training_data=true" \
  -F "model_name=malware_detector" \
  -F "ml_class_type=malware" \
  -F "name=sample_analysis_1"
```

**Response:**

```json
{
  "success": true,
  "message": "Binary uploaded successfully",
  "data": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

### Model Management API

#### List All Models

```
GET /api/v1/models/getModels
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/v1/models/getModels
```

#### Get Functions for a Model

```
GET /api/v1/models/getFunctions?model_name={model_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/models/getFunctions?model_name=malware_detector"
```

#### Get a Specific Function

```
GET /api/v1/models/getFunction?model_name={model_name}&function_name={function_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/models/getFunction?model_name=malware_detector&function_name=entry_0x401000"
```

#### Delete a Model

```
DELETE /api/v1/models/deleteModel?model_name={model_name}
```

```bash
curl -X DELETE -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/models/deleteModel?model_name=malware_detector"
```

#### Delete Multiple Models

```
DELETE /api/v1/models/deleteModels?model_names={comma_separated_names}
```

```bash
curl -X DELETE -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/models/deleteModels?model_names=model1,model2,model3"
```

### Predictions API

#### Submit a Prediction Task

```
POST /api/v1/predictions/predict
```

```bash
curl -X POST http://localhost:8000/api/v1/predictions/predict \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "modelName": "malware_detector",
    "taskName": "unknown_binary_analysis"
  }'
```

**Response:**

```json
{
  "success": true,
  "message": "Prediction task created successfully",
  "data": {
    "uuid": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
  }
}
```

#### Get All Predictions

```
GET /api/v1/predictions/getPredictions
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/v1/predictions/getPredictions
```

#### Get Prediction Details

```
GET /api/v1/predictions/getPrediction?task_name={task_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/getPrediction?task_name=unknown_binary_analysis"
```

#### Get Prediction Function Details

```
GET /api/v1/predictions/getPredictionFunction?task_name={task_name}&function_name={function_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/getPredictionFunction?task_name=unknown_binary_analysis&function_name=entry_0x401000"
```

### Task Status API

#### Check Task Status

```
GET /api/v1/status/getStatus?uuid={uuid}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/status/getStatus?uuid=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

**Response:**

```json
{
  "success": true,
  "message": "Task status retrieved successfully",
  "data": {
    "status": "completed"
  }
}
```

Possible status values:
- `pending` — Task is queued
- `running` — Task is being processed
- `completed` — Task finished successfully
- `failed` — Task encountered an error
- `UUID Not Found` — The UUID does not exist

#### Update Task Status

```
POST /api/v1/status/statusUpdate
```

```bash
curl -X POST http://localhost:8000/api/v1/status/statusUpdate \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "completed"
  }'
```

### Configuration API

#### Get Current Configuration

```
GET /api/v1/config
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8000/api/v1/config
```

#### Save Configuration

```
POST /api/v1/config/save
```

```bash
curl -X POST http://localhost:8000/api/v1/config/save \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_file_size_mb": 1024,
    "cpu_cores": 4
  }'
```

---

## Processing Pipeline

Glyph processes binaries through a pluggable pipeline architecture. The pipeline steps differ between training and prediction modes.

### Training Pipeline

```
Upload → Validate → Decompile (Ghidra) → Tokenize → Filter → Extract Features → Train Model → Save
```

| Step | Description |
|------|-------------|
| **ValidationStep** | Validates file existence, readability, and size limits |
| **DecompileStep** | Uses Ghidra headless mode to decompile the binary |
| **TokenizeStep** | Extracts code tokens from decompiled functions |
| **FilterStep** | Normalizes addresses, function names, and variable names; removes comments |
| **FeatureExtractStep** | Converts token sequences into ML features using TF-IDF |
| **TrainStep** | Trains a scikit-learn classifier on the extracted features |
| **Save** | Persists the trained model using joblib serialization |

### Prediction Pipeline

```
Upload → Validate → Decompile (Ghidra) → Tokenize → Filter → Extract Features → Predict → Save
```

The prediction pipeline replaces `TrainStep` with `PredictStep`, which classifies each function using the trained model.

---

## Configuration File

Glyph is configured via [`config.yml`](../config.yml). The following settings are available:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `cpu_cores` | int | `2` | Number of CPU cores for processing (1–32) |
| `max_file_size_mb` | int | `512` | Maximum upload file size in MB (1–2048) |
| `prediction_probability_threshold` | float | `50.0` | Minimum confidence threshold for predictions (0–100) |
| `jwt_secret_key` | string | `change-me-in-production` | Secret key for JWT token signing |
| `jwt_algorithm` | string | `HS256` | JWT signing algorithm |
| `access_token_expire_minutes` | int | `15` | Access token lifetime in minutes |
| `refresh_token_expire_days` | int | `7` | Refresh token lifetime in days |
| `use_https` | bool | `false` | Enable HTTPS/TLS mode |
| `auth_enabled` | bool | `true` | Enable/disable authentication |

### Logging Configuration

```yaml
logging:
  level: INFO                          # Global log level
  format: json                         # "json" or "text"
  console:
    enabled: true
    level: INFO
    colorize: true
  file:
    path: logs/glyph.log
    rotation: 50 MB
    retention: 10 days
  request_tracing:
    enabled: true
    header_name: X-Request-ID
  module_levels:                       # Per-module log levels
    app.auth: INFO
    app.database: WARNING
    app.processing: DEBUG
    uvicorn: INFO
```

---

## Environment Variables

All configuration settings can be overridden via environment variables using the `GLYPH_` prefix:

| Environment Variable | Config Key | Description |
|---------------------|------------|-------------|
| `GLYPH_CPU_CORES` | `cpu_cores` | Override CPU cores |
| `GLYPH_MAX_FILE_SIZE_MB` | `max_file_size_mb` | Override max file size |
| `GLYPH_JWT_SECRET_KEY` | `jwt_secret_key` | Override JWT secret |
| `GLYPH_ACCESS_TOKEN_EXPIRE_MINUTES` | `access_token_expire_minutes` | Override token expiry |
| `GLYPH_USE_HTTPS` | `use_https` | Enable HTTPS mode |
| `GLYPH_AUTH_ENABLED` | `auth_enabled` | Enable/disable auth |

**Example:**

```bash
export GLYPH_JWT_SECRET_KEY="your-strong-random-secret-key"
export GLYPH_CPU_CORES=4
export GLYPH_MAX_FILE_SIZE_MB=1024
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### Common Issues

#### Ghidra Not Found

**Error:** `GHIDRA_INSTALL_DIR not set` or `Ghidra installation not found`

**Solution:** Ensure the `GHIDRA_INSTALL_DIR` environment variable points to a valid Ghidra installation directory:

```bash
export GHIDRA_INSTALL_DIR=/opt/ghidra/ghidra_11.0_PUBLIC
```

The directory should contain `support/`, `GhidraRun`, and other Ghidra runtime files.

#### JWT Token Expired

**Error:** `401 Unauthorized` — `Token has expired`

**Solution:** Use the refresh token to obtain a new access token:

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your-refresh-token"}'
```

Or log in again to obtain fresh tokens.

#### File Upload Rejected

**Error:** `File type 'application/...' not allowed`

**Solution:** Glyph only accepts binary/ELF formats. Ensure the uploaded file is a valid ELF binary (32-bit or 64-bit). Supported MIME types include:

- `application/x-executable`
- `application/x-elf`
- `application/x-object`
- `application/x-dosexec`
- `application/x-sharedlib`
- `application/octet-stream`

#### Task Stuck in "pending" Status

**Solution:** Check the application logs for errors:

```bash
# Check the log file
cat logs/glyph.log | tail -50

# Or check console output if running in the foreground
```

Common causes include Ghidra process failures, insufficient disk space, or the binary being too large.

#### Database Errors

**Error:** `database is locked` or similar SQLite errors

**Solution:** This may occur during concurrent operations. The application uses async SQLite (aiosqlite) which handles concurrency, but ensure you are not running multiple instances of Glyph against the same database files.

#### Default JWT Secret Warning

**Warning:** `Using default JWT secret key`

**Solution:** Set a strong JWT secret key in production:

```bash
# Generate a random secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set it in config.yml or via environment variable
export GLYPH_JWT_SECRET_KEY="your-generated-secret-here"
```

### Rate Limiting

Glyph applies rate limiting to authentication endpoints to prevent brute-force attacks:

| Endpoint | Limit |
|----------|-------|
| Login | 5 requests per minute |
| Registration | 3 requests per minute |
| Password Change | 3 requests per minute |
| Token Refresh | 10 requests per minute |

If you receive a `429 Too Many Requests` response, wait before retrying.

### Security Headers

Glyph applies strict Content Security Policy (CSP) headers. If custom scripts or external resources fail to load, this is expected behavior. The CSP policy is:

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
img-src 'self' data:;
font-src 'self' https://fonts.gstatic.com;
object-src 'none';
frame-ancestors 'none';
base-uri 'self';
form-action 'self'
```

---

## Running Tests

Glyph includes a comprehensive test suite. Run tests with:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_pipeline.py

# Run with verbose output
pytest -v

# Run end-to-end tests (requires Playwright browsers)
pytest tests/e2e/
```

Install Playwright browsers for e2e tests:

```bash
playwright install
```
