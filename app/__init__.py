"""Glyph - Binary analysis powered by machine learning.

A FastAPI-based application for analyzing binary files using ML models
trained on decompiled function tokens from Ghidra. The application
provides endpoints for model training, prediction, and binary analysis.

Modules:
    api: REST API router and type definitions.
    auth: Authentication and authorization.
    config: Application settings and configuration.
    core: Core services (lifespan, rate limiting, request tracing).
    database: ORM models, repositories, and session management.
    processing: Pipeline framework and task management.
    services: Business logic services.
    utils: Shared utilities and helpers.
    web: Web UI endpoints.
"""
