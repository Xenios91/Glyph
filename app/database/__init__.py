"""Database package for Glyph application.

Provides SQLAlchemy ORM models, session management, and repository pattern
for database operations.

Submodules:
- models: SQLAlchemy ORM models
- session_handler: Async engine/session management
- repository: User and API key repositories, password hashing
- binary_repository: Binary upload metadata operations
- function_repository: Model function persistence
- model_repository: Trained model persistence
- prediction_repository: Prediction result persistence
- similarity_repository: Similarity computation persistence
- scan_report_repository: Dangerous function scan report persistence
- llm_result_repository: LLM analysis result persistence
- llm_user_config_repository: Per-user LLM configuration

Import from the submodules directly (e.g. ``app.database.models``).
"""
