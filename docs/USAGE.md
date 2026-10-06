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
  - [Task Execution](#task-execution-api)
  - [Model Management](#model-management-api)
  - [Predictions](#predictions-api)
  - [Task Status](#task-status-api)
  - [Configuration](#configuration-api)
- [Processing Pipeline](#processing-pipeline)
- [Configuration File](#configuration-file)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Running Tests](#running-tests)

---

## Overview

Glyph is an architecture-independent binary analysis tool that uses Natural Language Processing (NLP) techniques for **cross-architecture function fingerprinting**. The core workflow involves two phases:

1. **Training** — Upload one or more binaries from known sources, then run an ML training task to teach a model function signatures.
2. **Prediction** — Upload an unknown binary and run an ML prediction task with a trained model to classify its functions.

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
  "created_at": "2025-01-01T00:00:00"
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
  "key_prefix": "glp_abc1",
  "permissions": ["read"],
  "expires_at": null,
  "is_active": true,
  "last_used_at": null,
  "created_at": "2025-01-01T00:00:00",
  "secret": "glp_abc123..."
}
```

> **Important:** The API key secret is only shown once at creation. Store it securely.

**Use an API Key:**

API keys are sent in the `Authorization` header (the same header used for JWT tokens); the server falls back to an API-key lookup when the token is not a valid JWT:

```bash
curl -H "Authorization: Bearer glp_abc123..." \
  http://localhost:8000/api/v1/predictions/getPredictionsList
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
2. Choose the mode with the **Generate Model** checkbox:
   - **Checked (training mode)** — Shows **Model Configuration**:
     - **Name** — The name of the ML model to associate with this binary
     - **ML Class Type** — The classification label for this binary (e.g., "malware", "legitimate", "rootkit")
   - **Unchecked (prediction mode)** — Shows **Prediction Configuration**:
     - **Name** — A human-readable name for this analysis task
     - **Select Model** — A previously trained model to run predictions with
     - **ML Class Type** — The classification label for this binary
3. Select or drag-and-drop an ELF binary file (32-bit or 64-bit)
4. Submit the form to upload the binary

The upload initiates a background task that validates, decompiles (Ghidra), and stores the raw functions of the binary. You can monitor its status from the dashboard.

### Training a Model

Training is a two-step process: upload the binary, then run an ML training task on it:

1. Upload binaries from known sources (e.g., confirmed malware samples, legitimate binaries) with the **Generate Model** checkbox checked
2. Navigate to the **Create Model** page
3. Select the uploaded binary, enter the **Model Name** and **ML Class Type**, and submit — this queues an `ml_training` task
4. Check the **Models** page to see trained models and their associated functions

**Example Training Workflow:**

| Binary | Model Name | ML Class Type |
|--------|-----------|---------------|
| `malware_sample1.elf` | `malware_detector` | `malware` |
| `malware_sample2.elf` | `malware_detector` | `malware` |
| `legit_binary1.elf` | `malware_detector` | `legitimate` |
| `legit_binary2.elf` | `malware_detector` | `legitimate` |

After the training task completes, the `malware_detector` model can classify functions in unknown binaries as either `malware` or `legitimate`.

### Making Predictions

1. Upload an unknown binary with the **Generate Model** checkbox unchecked (select a previously trained model in the prediction configuration)
2. Navigate to the **Create Prediction** page
3. Select the uploaded binary and the **Model Name** of a previously trained model, enter a **Task Name** for the prediction task, then submit — this queues an `ml_prediction` task
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
   - **CPU Cores** — Number of CPU cores for processing (1 up to the machine's core count)
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
| `POST` | `/auth/update-profile` | Update user profile |
| `GET`/`POST` | `/auth/logout` | Log out (clears the `access_token_cookie` and `refresh_token_cookie` cookies) |
| `POST` | `/auth/api-keys` | Create an API key |
| `GET` | `/auth/api-keys` | List API keys |
| `DELETE` | `/auth/api-keys/{id}` | Delete an API key |

### Binary Upload API

#### Upload a Binary

```
POST /api/v1/binaries/uploadBinary
```

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `binary_file` | File | Yes | The binary file (ELF format) |
| `name` | String | Yes | Human-readable name for this analysis |

**Example:**

```bash
curl -X POST http://localhost:8000/api/v1/binaries/uploadBinary \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "binary_file=@/path/to/binary.elf" \
  -F "name=sample_analysis_1"
```

**Response:**

```json
{
  "success": true,
  "message": "Binary uploaded successfully",
  "data": {
    "binary_id": 1,
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }
}
```

The `uuid` can be used to track the background decompilation task via the Task Status API. Once the upload task completes, the binary's raw functions are stored and the binary can be used for training or prediction tasks.

### Task Execution API

#### Execute a Task

```
POST /api/v1/tasks/execute
```

Queues an analysis task on a previously uploaded binary. The task runs in the background; track it with the returned `task_uuid`.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `binary_id` | int | Yes | Database id of the uploaded binary |
| `task_type` | string | Yes | One of: `ml_training`, `ml_prediction`, `code_reuse`, `dangerous_functions`, `similarity_computation` |
| `task_name` | string | Yes | Human-readable name for the task (1–128 chars) |
| `model_name` | string | For ML tasks | Name of the model (required for `ml_training` and `ml_prediction`) |
| `ml_class_type` | string | For training | Classification label (required for `ml_training`) |

**Example (ML training):**

```bash
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "binary_id": 1,
    "task_type": "ml_training",
    "task_name": "malware_detector",
    "model_name": "malware_detector",
    "ml_class_type": "malware"
  }'
```

**Example (ML prediction):**

```bash
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "binary_id": 2,
    "task_type": "ml_prediction",
    "task_name": "unknown_binary_analysis",
    "model_name": "malware_detector"
  }'
```

**Response:**

```json
{
  "success": true,
  "message": "Task ml_training queued successfully",
  "data": {
    "task_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "task_type": "ml_training",
    "binary_id": 1,
    "status": "starting"
  }
}
```

#### Get Task Status

```
GET /api/v1/tasks/{task_uuid}/status
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890/status"
```

#### Get Task Results

```
GET /api/v1/tasks/{task_uuid}/results
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890/results"
```

### Model Management API

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

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `modelName` | string | Yes | Name of the trained model to use |
| `taskName` | string | Yes | Unique name for the prediction task |
| `uuid` | string | No | Optional custom UUID for the task |

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
GET /api/v1/predictions/getPredictionsList?page={page}&page_size={page_size}
```

Returns a paginated list of prediction tasks (default: `page=1`, `page_size=50`, max `page_size=200`).

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/getPredictionsList?page=1&page_size=50"
```

#### Get Prediction Details

```
GET /api/v1/predictions/getPrediction?model_name={model_name}&task_name={task_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/getPrediction?model_name=malware_detector&task_name=unknown_binary_analysis"
```

#### Get Prediction Function Details

```
GET /api/v1/predictions/getPredictionDetails?model_name={model_name}&task_name={task_name}&function_name={function_name}
```

```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/getPredictionDetails?model_name=malware_detector&task_name=unknown_binary_analysis&function_name=entry_0x401000"
```

#### Delete a Prediction

```
DELETE /api/v1/predictions/deletePrediction?task_name={task_name}
```

```bash
curl -X DELETE -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/deletePrediction?task_name=unknown_binary_analysis"
```

#### Delete Multiple Predictions

```
DELETE /api/v1/predictions/deletePredictions?task_names={comma_separated_names}
```

```bash
curl -X DELETE -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/predictions/deletePredictions?task_names=task1,task2,task3"
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
- `starting` — Task has been queued
- `processing` — Task is being processed
- `completed` — Task finished successfully
- `error` — Task encountered an error
- `failed` / `cancelled` — Terminal states that stop SSE streaming

If the UUID does not exist, the endpoint returns a `404` with error code `UUID_NOT_FOUND`.

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

#### Stream Task Status (SSE)

```
GET /api/v1/status/streamStatus?uuid={uuid}&interval={interval}&timeout={timeout}
```

Streams real-time status updates using Server-Sent Events until the task reaches a terminal state or the timeout is exceeded.

| Query Param | Type | Default | Description |
|-------------|------|---------|-------------|
| `uuid` | string | — | UUID of the task to monitor |
| `interval` | float | 2.0 | Polling interval in seconds (0.5–30) |
| `timeout` | int | 600 | Maximum streaming duration in seconds (10–3600) |

```bash
curl -N -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8000/api/v1/status/streamStatus?uuid=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### Configuration API

#### Save Configuration

```
POST /api/v1/config/save
```

All fields are optional; only provided fields are updated. Changes are persisted to `config.yml`.

| Field | Type | Description |
|-------|------|-------------|
| `max_file_size_mb` | int | Maximum upload file size in MB (1–2048) |
| `cpu_cores` | int | Number of CPU cores for processing (1 up to the machine's core count) |
| `llm` | object | Optional per-user LLM endpoint configuration (`enabled`, `base_url`, `port`, `api_path`, `model`, `api_key`, `timeout_seconds`, `temperature`, `max_tokens`, `max_concurrent`) |

```bash
curl -X POST http://localhost:8000/api/v1/config/save \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_file_size_mb": 1024,
    "cpu_cores": 4
  }'
```

#### Test LLM Endpoint

```
POST /api/v1/config/llm-test
```

Sends a minimal prompt to the configured OpenAI-compatible endpoint to verify connectivity. Returns `ok`/`model`/`elapsed_ms` on success, or `ok`/`error` when the endpoint is reachable but misbehaves. Returns `503` with error code `LLM_NOT_CONFIGURED` when the endpoint cannot be built from the current configuration.

```bash
curl -X POST http://localhost:8000/api/v1/config/llm-test \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Processing Pipeline

Glyph processes binaries through a pluggable pipeline architecture. The pipeline steps differ between upload, training, and prediction modes.

### Upload Pipeline

```
Upload → Validate → Decompile (Ghidra) → Save Raw Functions
```

| Step | Description |
|------|-------------|
| **ValidationStep** | Validates file existence, readability, and size limits |
| **DecompileStep** | Uses Ghidra headless mode to decompile the binary |
| **SaveRawFunctionsStep** | Persists raw decompiled functions to the database |

### Training Pipeline

```
Upload → Validate → Decompile (Ghidra) → Tokenize → Filter → Extract Features → Train Model
```

| Step | Description |
|------|-------------|
| **ValidationStep** | Validates file existence, readability, and size limits |
| **DecompileStep** | Uses Ghidra headless mode to decompile the binary |
| **TokenizeStep** | Extracts code tokens from decompiled functions |
| **FilterStep** | Normalizes addresses, function names, and variable names; removes comments |
| **FeatureExtractStep** | Extracts token sequences from filtered functions and stores them in the context for the ML pipeline |
| **TrainStep** | Trains a scikit-learn classifier on the extracted features and persists the model using joblib serialization |

### Prediction Pipeline

```
Upload → Validate → Decompile (Ghidra) → Tokenize → Filter → Extract Features → Predict
```

The prediction pipeline replaces `TrainStep` with `PredictStep`, which classifies each function using the trained model. When functions are already stored in the database (from a previous upload), the pipeline skips validation and decompilation and loads the stored functions instead.

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
| `upload_folder` | path | `./binaries` | Directory where uploaded binaries are stored |
| `use_https` | bool | `false` | Enable HTTPS/TLS mode |
| `trusted_proxies` | list | `[]` | Trusted proxy IPs/CIDRs for `X-Forwarded-For` |
| `auth_enabled` | bool | `true` | Enable/disable authentication |
| `oauth2_enabled` | bool | `false` | Enable the OAuth2 authorization-code flow |
| `oauth2_session_secret` | string | *(random per start)* | Secret for OAuth2 session state |
| `llm` | object | *(see below)* | LLM-assisted analysis settings (nested block) |

### LLM Configuration

The optional `llm` block configures the OpenAI-compatible endpoint used for LLM-assisted analysis of dangerous function findings. It is disabled by default; individual users can override these global defaults from the **Profile → LLM** tab.

```yaml
llm:
  enabled: false
  base_url: https://api.openai.com
  port: null                    # explicit port; scheme default (80/443) when omitted
  api_path: /v1/chat/completions
  model: your-model
  api_key: ""
  timeout_seconds: 900.0        # 60–600+ per-request timeout
  temperature: 0.1              # 0.0–2.0
  max_tokens: null              # optional cap on generated tokens
  max_concurrent: 5             # 1–20 parallel analysis requests
```

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `false` | Enable LLM-assisted analysis |
| `base_url` | `https://your.model.url` | Base URL of the endpoint (scheme + host) |
| `port` | *(scheme default)* | Explicit port; 443 for HTTPS and 80 for HTTP are omitted from the URL |
| `api_path` | `/v1/chat/completions` | Path of the chat completions endpoint |
| `model` | `your model here` | Model name sent in each request |
| `api_key` | *(empty)* | Sent as `Authorization: Bearer <key>` |
| `timeout_seconds` | `900.0` | Per-request timeout (seconds) |
| `temperature` | `0.1` | Sampling temperature, 0.0–2.0 |
| `max_tokens` | *(none)* | Maximum tokens to generate per completion |
| `max_concurrent` | `5` | Maximum parallel analysis requests, 1–20 |

Each `llm` field can also be overridden with a `GLYPH_LLM_`-prefixed environment variable (nested settings use `_` as the delimiter), e.g. `GLYPH_LLM_ENABLED=true` or `GLYPH_LLM_BASE_URL=https://api.openai.com`. As with all settings, a value present in `config.yml` takes precedence over the environment.

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

Configuration is loaded from `config.yml` first. Environment variables with the `GLYPH_` prefix are consulted **only for keys that are absent from `config.yml`** — if the file already defines a key, the file value takes precedence (see `settings_customise_sources` in [`app/config/settings.py`](../app/config/settings.py)).

| Environment Variable | Config Key | Description |
|---------------------|------------|-------------|
| `GLYPH_CPU_CORES` | `cpu_cores` | CPU cores (used only if not set in `config.yml`) |
| `GLYPH_MAX_FILE_SIZE_MB` | `max_file_size_mb` | Max file size (used only if not set in `config.yml`) |
| `GLYPH_JWT_SECRET_KEY` | `jwt_secret_key` | JWT secret (used only if not set in `config.yml`) |
| `GLYPH_ACCESS_TOKEN_EXPIRE_MINUTES` | `access_token_expire_minutes` | Token expiry (used only if not set in `config.yml`) |
| `GLYPH_USE_HTTPS` | `use_https` | Enable HTTPS mode (used only if not set in `config.yml`) |
| `GLYPH_AUTH_ENABLED` | `auth_enabled` | Enable/disable auth (used only if not set in `config.yml`) |
| `GLYPH_UPLOAD_FOLDER` | `upload_folder` | Binary storage directory |
| `GLYPH_TRUSTED_PROXIES` | `trusted_proxies` | Trusted proxy IPs/CIDRs (comma-separated) |
| `GLYPH_OAUTH2_ENABLED` | `oauth2_enabled` | Enable the OAuth2 flow |
| `GLYPH_OAUTH2_SESSION_SECRET` | `oauth2_session_secret` | OAuth2 session secret |
| `GLYPH_LLM_ENABLED` | `llm.enabled` | Enable LLM analysis (nested, `_`-delimited) |
| `GLYPH_LLM_BASE_URL` | `llm.base_url` | LLM endpoint base URL |
| `GLYPH_LLM_API_PATH` | `llm.api_path` | LLM chat completions path |
| `GLYPH_LLM_MODEL` | `llm.model` | LLM model name |
| `GLYPH_LLM_API_KEY` | `llm.api_key` | LLM API key |
| `GLYPH_LLM_TIMEOUT_SECONDS` | `llm.timeout_seconds` | LLM per-request timeout |
| `GLYPH_LLM_TEMPERATURE` | `llm.temperature` | LLM sampling temperature |
| `GLYPH_LLM_MAX_TOKENS` | `llm.max_tokens` | LLM max generated tokens |
| `GLYPH_LLM_MAX_CONCURRENT` | `llm.max_concurrent` | LLM max parallel requests |

A few more values are read directly from the environment, independent of `config.yml`:

| Environment Variable | Description |
|---------------------|-------------|
| `GLYPH_DATA_DIR` | Data directory for the SQLite databases (default: `data`) |
| `GLYPH_RATE_LIMIT_LOGIN_MAX` / `GLYPH_RATE_LIMIT_LOGIN_WINDOW` | Override the login rate limit |
| `GLYPH_RATE_LIMIT_REGISTER_MAX` / `GLYPH_RATE_LIMIT_REGISTER_WINDOW` | Override the registration rate limit |
| `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX` / `GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW` | Override the password-change rate limit |
| `GLYPH_RATE_LIMIT_REFRESH_MAX` / `GLYPH_RATE_LIMIT_REFRESH_WINDOW` | Override the token-refresh rate limit |

**Example (setting values that are not defined in `config.yml`):**

```bash
export GLYPH_USE_HTTPS=true
export GLYPH_AUTH_ENABLED=false
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### Common Issues

#### Ghidra Not Found

**Error:** `GHIDRA_INSTALL_DIR not set` or `Ghidra installation not found`

**Solution:** Ensure the `GHIDRA_INSTALL_DIR` environment variable points to a valid Ghidra installation directory:

```bash
export GHIDRA_INSTALL_DIR=/opt/ghidra/ghidra_12.0_PUBLIC
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

#### Task Stuck in "starting" Status

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

**Solution:** Set a strong JWT secret key in production. Because `config.yml` takes precedence over environment variables, the reliable fix is to set `jwt_secret_key` directly in `config.yml` (or remove the key from the file so the `GLYPH_JWT_SECRET_KEY` environment variable is used):

```bash
# Generate a random secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```yaml
# config.yml
jwt_secret_key: your-generated-secret-here
```

### Rate Limiting

Glyph applies rate limiting to authentication endpoints and LLM analysis to prevent brute-force attacks and excessive LLM usage:

| Endpoint | Limit |
|----------|-------|
| Login | 10 requests per minute |
| Registration | 5 requests per 5 minutes |
| Password Change | 5 requests per 5 minutes |
| Token Refresh | 10 requests per minute |
| LLM Analysis (`/llm-analysis`, `/llm-test`) | 10 requests per minute |

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
