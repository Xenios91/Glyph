# Glyph Architecture Documentation

## Overview

Glyph is an architecture-independent binary analysis tool that uses NLP techniques for function fingerprinting across different system architectures. The application is built with FastAPI, uses async SQLite (via aiosqlite) for persistence, and integrates with Ghidra for binary decompilation. It includes a full authentication system with JWT tokens, OAuth2 support, and API key management.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Presentation Layer                                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │   Web UI (Jinja2)    │  │   API (FastAPI/REST) │  │  Auth Endpoints   │  │
│  │   (HTML/CSS/JS)      │  │   (JSON Responses)   │  │  (OAuth2/JWT)     │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Application Layer                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │  Request Handler     │  │  Task Service        │  │  Auth Service     │  │
│  │  (Business Logic)    │  │  (Task Queue)        │  │  (JWT/API Keys)   │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Processing Layer                                  │
│  ┌──────────────────────┐  ┌─────────────────────────────────────────────┐  │
│  │  Task Management     │  │  Processing Pipeline                        │  │
│  │  (Trainer/Predictor) │  │  (Validation → Decompile → Tokenize →       │  │
│  │  Ghidra Integration) │  │   Filter → Extract → Train/Predict)         │  │
│  └──────────────────────┘  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Layer                                      │
│  ┌──────────────────────┐  ┌─────────────────────────────────────────────┐  │
│  │  SQLAlchemy ORM      │  │  Repository (User/APIKey)                   │  │
│  │  (Async Models)      │  │  (Authentication Operations)                │  │
│  │  (Session Mgmt)      │  │                                             │  │
│  └──────────────────────┘  └─────────────────────────────────────────────┘  │
│                                      │                                       │
│                    ┌─────────────────┴─────────────────┐                     │
│                    ▼                                   ▼                     │
│          ┌─────────────────┐ ┌─────────────────────────────────┐            │
│          │   models.db     │ │ predictions.db                  │            │
│          │   functions.db  │ │ functions.db (shared)           │            │
│          │   auth.db       │ │ auth.db (Users + APIKeys)       │            │
│          └─────────────────┘ └─────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### API Layer (`app/api/`)

- **`router.py`** - Centralized API router with versioning support
- **`types.py`** - Shared API type definitions
- **`v1/endpoints/`** - Version 1 API endpoints:
  - `binaries.py` - Binary upload and management
  - `predictions.py` - Prediction task management
  - `models.py` - Model management
  - `status.py` - Task status checking
  - `config.py` - Configuration endpoints

### Authentication Layer (`app/auth/`)

- **`jwt_handler.py`** - JWT token generation and verification (HS256)
- **`dependencies.py`** - FastAPI dependency injection for authentication
- **`endpoints.py`** - Authentication API endpoints (login, register, token refresh, API key management)
- **`schemas.py`** - Pydantic schemas for authentication data
- **`security_logger.py`** - Security event logging and IP blocking

### Web Layer (`app/web/`)

- **`endpoints/web.py`** - Web UI endpoints with HTML responses
- **`templates/`** - Jinja2 templates with componentization
- **`static/`** - Static assets (CSS, JavaScript)

### Core Services (`app/core/`)

- **`lifespan.py`** - Application lifespan events (startup/shutdown)
- **`rate_limiter.py`** - Rate limiting (via slowapi) for login, registration, password changes, token refresh
- **`request_tracing.py`** - Request ID tracing via `X-Request-ID` header
- **`correlation_bridge.py`** - Request correlation bridging

### Services Layer (`app/services/`)

- **`request_handler.py`** - Business logic for processing requests (TrainingRequest, PredictionRequest, GhidraRequest)
- **`task_service.py`** - Background task queue management

### Database Layer (`app/database/`)

- **`models.py`** - SQLAlchemy ORM models (async via AsyncAttrs):
  - `Model` - Trained ML models
  - `Prediction` - Prediction tasks
  - `Function` - Extracted functions
  - `User` - User accounts (authentication)
  - `APIKey` - API keys for programmatic access
- **`session_handler.py`** - Async database session management (aiosqlite)
- **`repository.py`** - Repository for User and APIKey CRUD operations (with Argon2id password hashing)
- **`sql_service.py`** - SQL query service layer

### Processing Layer (`app/processing/`)

- **`pipeline.py`** - Pluggable processing pipeline with `PipelineStep` base class and `PipelineContext`
- **`steps.py`** - Pipeline step implementations:
  - `ValidationStep` - Binary file validation (existence, readability, size limits)
  - `DecompileStep` - Ghidra decompilation
  - `TokenizeStep` - Code tokenization from decompiled functions
  - `FilterStep` - Token filtering (normalize addresses, functions, variables, remove comments)
  - `FeatureExtractStep` - Feature extraction (token sequences for ML pipeline)
  - `TrainStep` - Model training (scikit-learn pipeline with TF-IDF)
  - `PredictStep` - Model prediction
- **`task_management.py`** - Task execution management (Trainer/Predictor)
- **`ghidra_processor.py`** - Ghidra headless decompilation integration

### Utilities (`app/utils/`)

- **`common.py`** - Code formatting and response building utilities
- **`helpers.py`** - Common constants and helper values
- **`jinja_utils.py`** - Jinja2 template configuration and filters
- **`logging_config.py`** - Loguru logging setup
- **`logging_utils.py`** - Logging decorators and utilities
- **`persistence_util.py`** - ML model and prediction persistence (joblib serialization)
- **`request_context.py`** - Async-safe request context management
- **`responses.py`** - Standardized API response models
- **`secure_deserializer.py`** - Secure pickle/joblib deserialization

### Configuration (`app/config/`)

- **`settings.py`** - Pydantic-based configuration management (YAML + environment variables)
  - `GlyphSettings` - Main settings class with YAML config source (`config.yml`)
  - `GlyphConfig` - Legacy configuration manager (backward compatibility)

## Data Flow

### Training Pipeline

```
1. Upload Binary → 2. Validate → 3. Decompile (Ghidra) →
4. Tokenize → 5. Filter → 6. Extract Features → 7. Train Model → 8. Save Model
```

### Prediction Pipeline

```
1. Upload Binary → 2. Validate → 3. Decompile (Ghidra) →
4. Tokenize → 5. Filter → 6. Extract Features → 7. Predict → 8. Save Predictions
```

## Database Schema

| Database | Tables | Purpose |
|----------|--------|---------|
| `models.db` | `models` | Stores trained ML models (serialized via joblib) |
| `predictions.db` | `predictions` | Stores prediction tasks and results |
| `functions.db` | `functions` | Stores extracted functions from binaries |
| `auth.db` | `users`, `api_keys` | Authentication and API key management |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| Database | SQLite (async via aiosqlite + SQLAlchemy ORM) |
| Template Engine | Jinja2 |
| ML Framework | scikit-learn (TF-IDF + classifiers) |
| Binary Analysis | Ghidra (headless decompilation) |
| Serialization | joblib |
| Configuration | Pydantic Settings (YAML + env vars) |
| Authentication | JWT (HS256), OAuth2, Argon2id password hashing |
| API Key Security | bcrypt |
| Rate Limiting | slowapi |
| Logging | loguru |

## Key Design Patterns

1. **Repository Pattern** - Abstracts database operations (UserRepository, APIKeyRepository)
2. **Pipeline Pattern** - Pluggable, sequential processing steps via `PipelineStep` interface
3. **Singleton Pattern** - Settings, TaskManager, TaskService
4. **Factory Pattern** - Response creation utilities
5. **Componentization** - Reusable Jinja2 UI components
6. **Dependency Injection** - FastAPI dependencies for authentication and database sessions
