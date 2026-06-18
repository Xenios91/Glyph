# Glyph Project Improvement Recommendations

## Executive Summary

Glyph is a well-architected binary analysis tool with strong security foundations, comprehensive test coverage (300+ tests), and clean layering. This document provides actionable recommendations organized by priority area.

## Decision Summary

| # | Section | Status |
|---|---------|--------|
| 1 | CI/CD & GitHub Actions | ✅ APPROVED (all items) |
| 2 | Dependency Management | ✅ APPROVED (all items) |
| 3 | Testing | ✅ APPROVED (all items) |
| 4 | Code Quality & Static Analysis | ✅ APPROVED (all items) |
| 5 | Security | ✅ APPROVED (all items) |
| 6 | Database | ❌ DENIED |
| 7 | Performance | ✅ APPROVED (all items) |
| 8 | Documentation | ✅ APPROVED (all items) |
| 9 | Deployment & DevOps | ✅ APPROVED (all items) |
| 10 | Frontend | ⚠️ PARTIAL (10.3 error handling, 10.4 accessibility only) |
| 11 | Observability | ❌ DENIED |
| 12 | Project Structure | ✅ APPROVED (all items) |

---

## 1. CI/CD & GitHub Actions

### 1.1 Update Outdated Action Versions (High Priority)

Both [`.github/workflows/codeql.yml`](.github/workflows/codeql.yml) and [`.github/workflows/pylint.yml`](.github/workflows/pylint.yml) use deprecated action versions:

| Current | Recommended |
|---------|-------------|
| `actions/checkout@v3` | `actions/checkout@v5` |
| `actions/setup-python@v3` | `actions/setup-python@v5` |
| `github/codeql-action/init@v2` | `github/codeql-action/init@v3` |
| `github/codeql-action/analyze@v2` | `github/codeql-action/analyze@v4` |

### 1.2 Add Missing CI Workflows

**Missing workflows that would improve quality:**

- **Test workflow** — Run pytest with coverage reporting on push/PR
- **Type checking workflow** — Add mypy/pyright for static type validation
- **Docker build workflow** — Build and push container images
- **Dependency review** — Use `dependency-review-action` to catch vulnerable deps
- **Scorecard** — GitHub security scorecard for supply chain security

**Suggested test workflow structure:**
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4
```

### 1.3 Pylint Workflow Incomplete

[`.github/workflows/pylint.yml`](.github/workflows/pylint.yml:18) installs dependencies but never actually runs pylint. Add:
```yaml
- name: Run Pylint
  run: |
    pip install pylint
    pylint app/
```

---

## 2. Dependency Management

### 2.1 Migrate to pyproject.toml (High Priority)

The project currently uses [`requirements.txt`](requirements.txt) with fully pinned versions. This approach has several drawbacks:

- **No project metadata** — Missing name, version, description, authors
- **No build system specification** — Cannot be installed as a package
- **Difficult to maintain** — Manual pinning of transitive dependencies
- **No optional dependency groups** — Cannot separate dev/test/production deps

**Recommended structure:**
```toml
[project]
name = "glyph"
version = "0.1.0"
description = "Architecture-independent binary analysis tool for function fingerprinting"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115,<1.0",
    "uvicorn>=0.30,<1.0",
    "sqlalchemy>=2.0,<3.0",
    # ... core deps with loose version bounds
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov", "mypy", "ruff", "playwright"]
```

### 2.2 Use a Dependency Lock File

Adopt either:
- **uv** — Fast resolver with `uv.lock`
- **pip-tools** — Generates `requirements.lock` from `requirements.in`
- **pdm** — Full PEP 621 compliance with locking

### 2.3 Loose Version Bounds in requirements.txt

Currently most deps are fully pinned (e.g., `fastapi==0.136.1`). Use minimum versions with upper bounds instead:
```
# Current
fastapi==0.136.1
uvicorn==0.46.0

# Recommended
fastapi>=0.115,<1.0
uvicorn>=0.30,<1.0
```

---

## 3. Testing

### 3.1 Add Coverage Reporting

Add coverage to [`pytest.ini`](pytest.ini):
```ini
addopts = -v --tb=short --strict-markers --ignore=tests/e2e --cov=app --cov-report=term-missing --cov-report=html
```

Install `pytest-cov` and set a minimum coverage threshold:
```ini
cov-fail-under = 80
```

### 3.2 Include E2E Tests in CI

E2e tests are currently excluded by default ([`pytest.ini:6`](pytest.ini:6)). Add a separate CI job:
```yaml
e2e-test:
  runs-on: ubuntu-latest
  steps:
    - run: playwright install --with-deps
    - run: pytest tests/e2e/
```

### 3.3 Add Integration Test Markers

Use pytest markers to categorize tests:
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_ghidra_decompilation():
    ...
```

Then control which run with `-m "not integration"` in CI.

### 3.4 Add Property-Based Testing

For the pipeline and filtering logic, consider adding `hypothesis`-based tests:
```python
from hypothesis import given
from hypothesis.strategies import text

@given(text(alphabet=characters.printable))
def test_filter_tokens_idempotent(code):
    """Filtering tokens twice should produce same result as once."""
    result1 = filter_tokens(tokenize(code))
    result2 = filter_tokens(result1)
    assert result1 == result2
```

---

## 4. Code Quality & Static Analysis

### 4.1 Add Type Checking

The codebase uses type hints extensively but has no CI-enforced type checking. Add **mypy** or **pyright**:

```yaml
# .github/workflows/type-check.yml
- run: pip install mypy
- run: mypy app/ --ignore-missing-imports
```

### 4.2 Replace Pylint with Ruff

Ruff is faster and more modern:
```yaml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
```

### 4.3 Add Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
```

---

## 5. Security

### 5.1 Enforce JWT Secret at Startup (High Priority)

[`config.yml`](config.yml:2) has `jwt_secret_key: change-me-in-production`. The current warning log in [`app/config/settings.py:135`](app/config/settings.py:135) is insufficient. Consider:

```python
if _settings.jwt_secret_key == _DEFAULT_JWT_SECRET and os.environ.get("GLYPH_ENV") == "production":
    raise RuntimeError("JWT secret key must be set for production. Set GLYPH_JWT_SECRET_KEY.")
```

### 5.2 Add HSTS Header

[`CSPMiddleware`](main.py:40) sets good security headers but is missing `Strict-Transport-Security`:
```python
(b"strict-transport-security", b"max-age=31536000; includeSubDomains")
```

### 5.3 Add Content-Length Limits

FastAPI doesn't enforce request body size by default. Add middleware:
```python
class RequestSizeLimit:
    def __init__(self, app, max_size=100*1024*1024):
        self.app = app
        self.max_size = max_size
```

### 5.4 Secure Cookie Flags

When `use_https` is enabled, ensure cookies have `Secure` and `SameSite` flags. Check [`app/auth/endpoints.py`](app/auth/endpoints.py) for cookie setting code.

### 5.5 Add OpenTelemetry for Security Observability

Integrate OpenTelemetry for distributed tracing of security events:
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)
```

---

## 6. Database

### 6.1 Add Database Migrations (High Priority)

Currently tables are created with `Base.metadata.create_all()` ([`app/database/session_handler.py:82`](app/database/session_handler.py:82)). This doesn't support schema evolution. Adopt **Alembic**:

```bash
alembic init alembic
# Configure alembic.ini to use async SQLAlchemy
```

Benefits:
- Version-controlled schema changes
- Rollback capability
- Team collaboration on schema changes

### 6.2 Add Database Indexes

Review queries and add indexes for frequently filtered columns:
```python
# In models.py
__table_args__ = (
    Index("idx_functions_model_name", "model_name"),
    Index("idx_predictions_model_name", "model_name"),
)
```

### 6.3 Consider PostgreSQL for Production

SQLite has limitations:
- No concurrent writes (WAL helps but not ideal)
- No row-level security
- Limited connection pooling

Add PostgreSQL support via conditional connection string:
```python
if settings.database_url.startswith("postgresql"):
    engine = create_async_engine(url, pool_size=10, max_overflow=20)
```

### 6.4 Add Database Backup Strategy

Document and implement automated backups for the SQLite databases in `data/` directory.

---

## 7. Performance

### 7.1 Add Response Caching

For endpoints that return frequently-accessed, rarely-changing data:
```python
from fastapi-cache2 import FastAPICache, SimpleCacheBackend

FastAPICache.init(SimpleCacheBackend())

@cache(expire=300)  # 5 minute cache
@router.get("/api/v1/models")
async def list_models():
    ...
```

### 7.2 Add Request Body Streaming for Large Uploads

For binary uploads, consider streaming to disk instead of loading entirely into memory:
```python
async def upload_binary(file: UploadFile = File(...)):
    with open(target_path, "wb") as f:
        while chunk := await file.read(8192):
            f.write(chunk)
```

### 7.3 Add Connection Pool Monitoring

Monitor SQLite WAL file size and database file growth. Add health check endpoint:
```python
@router.get("/health")
async def health_check():
    db_stats = await check_database_health()
    return {"status": "healthy", "databases": db_stats}
```

---

## 8. Documentation

### 8.1 Add API Reference Documentation

Currently relies on FastAPI auto-generated Swagger UI. Add:
- **OpenAPI specification export** — `python -c "from main import app; import json; print(json.dumps(app.openapi()))" > openapi.json`
- **Markdown API docs** in `docs/` for offline reference
- **Example requests/responses** for each endpoint

### 8.2 Add Contributing Guide

Create `CONTRIBUTING.md` with:
- Development setup instructions
- Coding standards
- Pull request template
- Test writing guidelines

### 8.3 Add CHANGELOG

Create `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format:
```markdown
## [0.1.0] - 2025-01-01
### Added
- PyGhidra integration
- FastAPI-based server
### Changed
- New UI theme
### Fixed
- Bug fixes and improved Dockerization
```

### 8.4 Improve Architecture Documentation

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is excellent. Consider adding:
- **Sequence diagrams** for key flows (upload, train, predict)
- **Data flow diagrams** showing inter-component communication
- **Deployment diagram** for production topology

---

## 9. Deployment & DevOps

### 9.1 Add Docker Compose Configuration

Create `docker-compose.yml` for local development:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GLYPH_JWT_SECRET_KEY=${JWT_SECRET}
      - GLYPH_CPU_CORES=4
    volumes:
      - ./data:/app/data
      - ./binaries:/app/binaries
    depends_on:
      - ghidra

  ghidra:
    image: ghidra-server:latest
    volumes:
      - ghidra_data:/ghidra_data

volumes:
  ghidra_data:
```

### 9.2 Add Production Dockerfile

The current Dockerfile is in [`.devcontainer/Dockerfile`](.devcontainer/Dockerfile). Create a separate production-optimized `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.3 Add Environment-Specific Configs

Create separate config files:
- `config.dev.yml` — Development settings
- `config.prod.yml` — Production settings
- `config.test.yml` — Test settings

### 9.4 Add Health Check Endpoint

Add `/health` and `/ready` endpoints:
```python
@router.get("/health")
async def liveness_probe():
    return {"status": "ok"}

@router.get("/ready")
async def readiness_probe():
    # Check database connectivity, Ghidra availability
    return {"status": "ready"}
```

---

## 10. Frontend

### 10.1 Add Frontend Build Tool

Current static JS/CSS files are served directly. Consider:
- **Vite** or **esbuild** for bundling and minification
- **Sass** for CSS preprocessing
- Tree-shaking to reduce bundle size

### 10.2 Add Frontend Linting

Add ESLint and Stylelint:
```json
{
  "eslintConfig": {
    "extends": ["eslint:recommended"],
    "env": { "browser": true, "es2021": true }
  }
}
```

### 10.3 Improve Error Handling in JavaScript

Review JS files in [`static/js/`](static/js/) for consistent error handling. Add:
- Global error interceptor for fetch/XHR
- User-friendly error messages
- Retry logic for failed requests

### 10.4 Add Accessibility Improvements

- Add ARIA labels to interactive elements
- Ensure keyboard navigation works for all UI components
- Add focus management for modal dialogs

---

## 11. Observability

### 11.1 Add Structured Logging Enhancement

Current logging uses Loguru with JSON format. Enhance with:
- **Correlation ID** in all log entries (already partially implemented)
- **Request duration** metrics
- **Error stack traces** in structured format

### 11.2 Add Metrics Endpoint

Expose Prometheus-compatible metrics:
```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration")

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 11.3 Add Sentry Integration

[`sentry-sdk`](requirements.txt:44) is installed but verify it's configured:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[FastAPIIntegration()],
    traces_sample_rate=0.1,
)
```

---

## 12. Project Structure

### 12.1 Clean Up Truncated Files in Root

The root directory contains `file:mem_*` files which appear to be SQLite in-memory database artifacts from tests. Add to [`.gitignore`](.gitignore):
```
file:mem_*
*.db
data/
binaries/
logs/
```

### 12.2 Remove glyph_venv from Repository

[`glyph_venv/`](glyph_venv/) should not be committed. Already in `.gitignore` but verify it's not tracked:
```bash
git rm -r --cached glyph_venv/
```

### 12.3 Consolidate Duplicate Environments

Both `glyph_venv/` and `glyph_env/` directories exist. Clean up the unused one.

### 12.4 Add Package `__init__.py` Versions

[`app/_version.py`](app/_version.py) exists but consider using `importlib.metadata`:
```python
from importlib.metadata import version
__version__ = version("glyph")
```

---

## Priority Matrix

| Priority | Area | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Fix Pylint workflow | Low | High |
| **P0** | Enforce JWT secret in prod | Low | High |
| **P1** | Migrate to pyproject.toml | Medium | High |
| **P1** | Add database migrations (Alembic) | Medium | High |
| **P1** | Add test coverage reporting | Low | High |
| **P2** | Update GitHub Actions versions | Low | Medium |
| **P2** | Add type checking (mypy) | Medium | Medium |
| **P2** | Add Docker Compose | Medium | Medium |
| **P3** | Add response caching | Medium | Medium |
| **P3** | Add contributing guide | Low | Medium |
| **P3** | Add CHANGELOG | Low | Medium |
| **P4** | Frontend build tooling | High | Low |
| **P4** | PostgreSQL support | High | Low |

---

## Implementation Roadmap

### Phase 1: Foundation (Quick Wins)
1. Fix Pylint workflow to actually run
2. Update GitHub Actions to latest versions
3. Add test coverage reporting
4. Enforce JWT secret validation in production
5. Clean up repository (remove venv, add gitignore entries)

### Phase 2: Quality & Reliability
1. Migrate to pyproject.toml
2. Add database migrations with Alembic
3. Add type checking with mypy
4. Add Ruff for linting
5. Add pre-commit hooks

### Phase 3: Operations & Deployment
1. Create production Dockerfile
2. Add Docker Compose configuration
3. Add health check endpoints
4. Add environment-specific configs
5. Set up Sentry integration

### Phase 4: Documentation & Polish
1. Write CONTRIBUTING.md
2. Create CHANGELOG.md
3. Add API reference docs
4. Improve architecture diagrams
5. Add frontend linting
