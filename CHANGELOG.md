# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-02

### Added
- Health check endpoints (`/health` and `/ready`) for orchestrator integration
- Request body size limit middleware to prevent DoS attacks
- HSTS security header in CSPMiddleware
- JWT secret enforcement in production environments
- Comprehensive API reference documentation
- Contributor guide (CONTRIBUTING.md)
- Pre-commit hooks configuration
- Ruff linter and formatter configuration
- MyPy static type checking configuration
- GitHub Actions workflows for testing, dependency review, and CI
- Pytest markers for test categorization (slow, integration, e2e, auth, security)
- Coverage reporting configuration
- Environment-specific configuration support

### Changed
- Updated GitHub Actions to latest versions (checkout@v5, setup-python@v5)
- Dangerous functions table now shows a per-row "Analyzing…" spinner in each LLM cell while a finding's LLM analysis is in progress, so users can see which rows are still being processed
- Improved cookie security with path scoping and strict SameSite for refresh tokens
- Enhanced JWT secret validation with production enforcement
- Ruff workflow for linting checks
- Moved custom middleware classes (`CSPMiddleware`, `RequestSizeMiddleware`, `CachedStaticFiles`) from `main.py` to `app/core/middleware.py`
- Renamed `app/config/pipeline_configs.py` to `app/config/ml_pipeline.py` to distinguish it from `app/processing/pipeline_configs.py`
- Renamed the `UUID` type alias to `TaskUUID` in `app/api/types.py`
- Consolidated the `ACCEPT_TYPE` constant into `app/api/types.py`
- ProcessPoolExecutor worker count is now derived from `settings.cpu_cores`
- Relaxed Content-Security-Policy is now applied to `/redoc` and `/openapi.json`, matching the documented behavior
- Training and prediction requests no longer build a pandas DataFrame; only the function list is retained, skipping a pointless DataFrame build on every training/prediction task
- `close_async_session` docstring now describes it as the standard session-closing helper used across repositories, instead of labeling it legacy

### Fixed
- "Clear LLM Results" button on the dangerous functions page now updates dynamically: it becomes enabled as soon as LLM analysis results exist for the findings currently on screen (e.g., right after a scan's findings are analyzed), instead of only re-evaluating when the target is selected
- Docker image build failed because `README.md` and `license.md` were excluded by `.dockerignore` while still required by the build
- Loguru log calls that used `%s`/`%d` placeholders silently dropped their arguments (Loguru uses `{}`-style formatting)
- An empty or whitespace-only JWT secret is now treated as unset

### Removed
- Unused `oauth2_enabled` and `oauth2_session_secret` settings
- Unreachable legacy pipeline chain: `_run_pipeline_analysis` handler, `GhidraPipelineRunner`, `GhidraRequest`, and the `TRAINING_PIPELINE` / `PREDICTION_PIPELINE` compositions (the live flows use the `*_FROM_DB_PIPELINE` variants)
- Unreferenced `SimilarityComputationNotFoundError` and `SimilarityComputationAccessError` exceptions
- Test-only `BinarySimilarityService.get_similarity_color` helper (the frontend has its own JS implementation)
- Dead `DataHandler.bin_dictionary` state, unused `RequestContext` property setters, and unused `get_task_id` helper
- Unused `models/` directory from the Docker image and docker-compose volume
- `app/utils/helpers.py` (its single constant was consolidated into `app/api/types.py`)
- The `"UUID Not Found"` sentinel from the SSE terminal-status set (now handled explicitly)

### Security
- Added HSTS header with `max-age=31536000; includeSubDomains; preload`
- Request body size limiting based on `max_file_size_mb` configuration
- Refresh token cookie scoped to `/auth/refresh` path with `SameSite=strict`
- Application refuses to start in production with default JWT secret
- Production security checks are re-run when configuration is reloaded at runtime

## [0.2.0] - 2026-07-07

### Added
- Dangerous function detection and scanning with decompiled usage context
- Dashboard improvements and bug fixes across web endpoints
- Usage documentation (docs/USAGE.md) and danger function documentation
- Unit test coverage for new functionality

### Changed
- Reworked request handling and web endpoints for improved maintainability
- Updated logging configuration and utilities
- Added type stubs for PyGhidra and Ghidra/Java interop

### Fixed
- Various bug fixes across services, endpoints, and utilities

## [0.1.0] - 2024-01-01

### Added
- Initial release of Glyph binary analysis tool
- Architecture-independent binary analysis using NLP
- Function fingerprinting with TF-IDF vectorization
- ML-powered function classification using scikit-learn
- Ghidra integration via PyGhidra
- FastAPI REST API with comprehensive endpoints
- Jinja2-based web UI
- JWT authentication (HS256) with joserfc
- Argon2id password hashing
- Rate limiting with slowapi
- Structured logging with Loguru
- Pydantic-based configuration management with YAML support
- Pipeline pattern for pluggable processing steps
- Secure deserialization with class whitelist/blacklist
- SQLAlchemy ORM models for database abstraction
- Async SQLite database with WAL mode
- Dangerous function detection and scanning
- Code reuse detection across binaries
- Background task processing with queue-based service
- E2E testing with Playwright
- Comprehensive unit test suite

[0.3.0]: https://github.com/Xenios91/Glyph/releases/tag/v0.3.0
[0.2.0]: https://github.com/Xenios91/Glyph/releases/tag/v0.2.0
[0.1.0]: https://github.com/Xenios91/Glyph/releases/tag/v0.1.0
