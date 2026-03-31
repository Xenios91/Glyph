# Glyph Architecture Documentation

## Overview

Glyph is an architecture-independent binary analysis tool that uses NLP techniques for function fingerprinting across different system architectures. The application is built with FastAPI, uses SQLite for persistence, and integrates with Ghidra for binary decompilation.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                      │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │   Web UI (Jinja2)    │  │   API Endpoints (FastAPI)    │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  Request Handlers    │  │  Task Service                │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Processing Layer                        │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  Task Management     │  │  Processing Pipeline         │ │
│  │  (Trainer/Predictor) │  │  (Validation/Decompile/      │ │
│  │  Ghidra Integration) │  │   Tokenize/Filter/Extract)   │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  SQLAlchemy ORM      │  │  Repository Pattern          │ │
│  │  (Models/Sessions)   │  │  (Model/Prediction/Function) │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
│                              │                               │
│                    ┌─────────┴─────────┐                     │
│                    ▼                   ▼                     │
│          ┌─────────────────┐ ┌─────────────────┐            │
│          │   models.db     │ │ predictions.db  │            │
│          │   functions.db  │ │                 │            │
│          └─────────────────┘ └─────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### API Layer (`app/api/`)

- **`router.py`** - Centralized API router with versioning support
- **`v1/endpoints/`** - Version 1 API endpoints:
  - `binaries.py` - Binary upload and management
  - `predictions.py` - Prediction task management
  - `models.py` - Model management
  - `status.py` - Task status checking
  - `config.py` - Configuration endpoints

### Web Layer (`app/web/`)

- **`endpoints/web.py`** - Web UI endpoints with HTML responses
- **`templates/`** - Jinja2 templates with componentization
- **`static/`** - Static assets (CSS, JavaScript)

### Database Layer (`app/database/`)

- **`models.py`** - SQLAlchemy ORM models:
  - `Model` - Trained ML models
  - `Prediction` - Prediction tasks
  - `Function` - Extracted functions
- **`session_handler.py`** - Database session management
- **`repositories/`** - Repository pattern implementations:
  - `model_repository.py` - Model CRUD operations
  - `prediction_repository.py` - Prediction CRUD operations
  - `function_repository.py` - Function CRUD operations

### Processing Layer (`app/processing/`)

- **`pipeline.py`** - Pluggable processing pipeline
- **`steps.py`** - Pipeline step implementations:
  - `ValidationStep` - Binary validation
  - `DecompileStep` - Ghidra decompilation
  - `TokenizeStep` - Code tokenization
  - `FilterStep` - Token filtering
  - `FeatureExtractStep` - Feature extraction
  - `TrainStep` - Model training
  - `PredictStep` - Model prediction
- **`task_management.py`** - Task execution management
- **`ghidra_processor.py`** - Ghidra integration

### Configuration (`app/config/`)

- **`settings.py`** - Pydantic-based configuration management

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

## Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| Database | SQLite (via SQLAlchemy ORM) |
| Template Engine | Jinja2 |
| ML Framework | scikit-learn |
| Binary Analysis | Ghidra |
| Serialization | joblib |
| Configuration | Pydantic Settings |

## Key Design Patterns

1. **Repository Pattern** - Abstracts database operations
2. **Pipeline Pattern** - Pluggable processing steps
3. **Singleton Pattern** - TaskManager, TaskService
4. **Factory Pattern** - Response creation utilities
5. **Componentization** - Reusable UI components
