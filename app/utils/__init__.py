"""Utilities module for Glyph application.

Shared utility functions and helpers used across the application.

Submodules:
    background_tasks: Fire-and-forget background task helpers.
    common: Code formatting and response building utilities.
    logging_config: Loguru logging setup.
    logging_utils: Logging decorators and utilities.
    request_context: Async-safe request context management.
    responses: Standardized API response models.
    secret_cipher: Fernet-based encryption for secrets at rest.
    secure_deserializer: Secure pickle/joblib deserialization.
    ssrf_guard: SSRF protection for outbound server-side requests.
"""
