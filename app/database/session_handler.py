"""Database session management for Glyph application."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.models import Base, Model, Prediction, Function, User, APIKey
from loguru import logger

_DEFAULT_ASYNC_DATABASE_URLS: dict[str, str] = {
    "models": "sqlite+aiosqlite:///data/models.db",
    "predictions": "sqlite+aiosqlite:///data/predictions.db",
    "functions": "sqlite+aiosqlite:///data/functions.db",
    "auth": "sqlite+aiosqlite:///data/auth.db",  # New database for auth
}

ASYNC_DATABASE_URLS: dict[str, str] = _DEFAULT_ASYNC_DATABASE_URLS.copy()


def set_database_urls(urls: dict[str, str]) -> None:
    """Override database URLs (primarily for testing)."""
    ASYNC_DATABASE_URLS.clear()
    ASYNC_DATABASE_URLS.update(urls)


def reset_database_urls() -> None:
    """Reset database URLs to defaults."""
    ASYNC_DATABASE_URLS.clear()
    ASYNC_DATABASE_URLS.update(_DEFAULT_ASYNC_DATABASE_URLS)

DB_TABLE_MAP: dict[str, list[Any]] = {
    "models": [Model.__table__],
    "predictions": [Prediction.__table__],
    "functions": [Function.__table__],
    "auth": [User.__table__, APIKey.__table__],
}

async_engines: dict[str, AsyncEngine] = {}
async_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def _configure_sqlite(dbapi_connection: Any, connection_record: Any) -> None:
    """Configure SQLite PRAGMA settings."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _create_engine(url: str) -> AsyncEngine:
    """Create an async engine for SQLite with aiosqlite."""
    engine = create_async_engine(
        url,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    return engine


async def init_async_databases() -> None:
    """Initialize all async database tables."""
    for name, url in ASYNC_DATABASE_URLS.items():
        if name not in async_engines:
            async_engines[name] = _create_engine(url)
            async_session_factories[name] = async_sessionmaker(
                bind=async_engines[name],
                autoflush=False,
                expire_on_commit=False,
            )

        target_tables = DB_TABLE_MAP.get(name)
        if target_tables:
            async with async_engines[name].begin() as conn:
                await conn.run_sync(Base.metadata.create_all, tables=target_tables)
            logger.info("Async database '{}' initialized successfully", name)


async def get_async_session(database: str = "auth") -> AsyncSession:
    """Get an async database session."""
    if database not in async_session_factories:
        raise ValueError(f"Invalid database name: {database}. Must be one of: {list(async_session_factories.keys())}")

    return async_session_factories[database]()


async def close_async_session(session: AsyncSession) -> None:
    """Close an async database session."""
    await session.close()


async def dispose_async_engines() -> None:
    """Dispose all async database engines."""
    for name, engine in async_engines.items():
        await engine.dispose()
        logger.info("Async database '{}' engine disposed", name)
    async_engines.clear()
    async_session_factories.clear()
