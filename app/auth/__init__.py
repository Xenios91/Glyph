"""Authentication module for Glyph.

This module provides authentication functionality using authlib for JWT tokens
and Argon2id for password hashing.

Components:
- jwt_handler: JWT token generation and verification
- dependencies: FastAPI dependency injection for authentication
- endpoints: Authentication API endpoints
- schemas: Pydantic schemas for authentication data
- security_logger: Login failure tracking and security event logging

Import from the submodules directly (e.g. ``app.auth.dependencies``).
"""
