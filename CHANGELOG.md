# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Improved cookie security with path scoping and strict SameSite for refresh tokens
- Enhanced JWT secret validation with production enforcement
- Ruff workflow for linting checks

### Security
- Added HSTS header with `max-age=31536000; includeSubDomains; preload`
- Request body size limiting based on `max_file_size_mb` configuration
- Refresh token cookie scoped to `/auth/refresh` path with `SameSite=strict`
- Application refuses to start in production with default JWT secret

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

[Unreleased]: https://github.com/original-owner/glyph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/original-owner/glyph/releases/tag/v0.1.0
