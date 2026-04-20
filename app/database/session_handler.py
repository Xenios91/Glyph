"""Database session management for Glyph application."""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base

DATABASE_URLS = {
    "models": "sqlite:///models.db",
    "predictions": "sqlite:///predictions.db",
    "functions": "sqlite:///functions.db",
}

# Synchronous engines and sessions (existing)
engines = {name: create_engine(url, echo=False, future=True) for name, url in DATABASE_URLS.items()}

session_factories = {
    name: sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    for name, engine in engines.items()
}

# Async engines and sessions (for auth module)
ASYNC_DATABASE_URLS = {
    "models": "sqlite+aiosqlite:///models.db",
    "predictions": "sqlite+aiosqlite:///predictions.db",
    "functions": "sqlite+aiosqlite:///functions.db",
    "auth": "sqlite+aiosqlite:///auth.db",  # New database for auth
}

async_engines: dict[str, AsyncEngine] = {}
async_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}

logger = logging.getLogger(__name__)


def init_databases() -> None:
    """Initialize all database tables."""
    for name, engine in engines.items():
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database '%s' initialized successfully", name)
        except Exception as exc:
            logger.error("Failed to initialize database '%s': %s", name, exc)


async def init_async_databases() -> None:
    """Initialize all async database tables."""
    for name, url in ASYNC_DATABASE_URLS.items():
        if name not in async_engines:
            async_engines[name] = create_async_engine(url, echo=False, future=True)
            async_session_factories[name] = async_sessionmaker(
                bind=async_engines[name], autoflush=False, autocommit=False
            )
        
        async with async_engines[name].begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Async database '%s' initialized successfully", name)


@contextmanager
def get_session(database: str = "models") -> Generator[Session, None, None]:
    """Get a database session context manager.

    Args:
        database: The database name ('models', 'predictions', or 'functions').

    Yields:
        A SQLAlchemy Session object.

    Raises:
        ValueError: If the database name is invalid.
    """
    if database not in session_factories:
        raise ValueError(f"Invalid database name: {database}. Must be one of: {list(session_factories.keys())}")

    session = session_factories[database]()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Database error in '%s': %s", database, exc)
        raise
    finally:
        session.close()


async def get_async_session(database: str = "auth") -> AsyncSession:
    """Get an async database session.

    Args:
        database: The database name ('auth', 'models', 'predictions', or 'functions').

    Returns:
        An AsyncSession object.

    Raises:
        ValueError: If the database name is invalid.
    """
    if database not in async_session_factories:
        raise ValueError(f"Invalid database name: {database}. Must be one of: {list(async_session_factories.keys())}")

    return async_session_factories[database]()


async def close_async_session(session: AsyncSession) -> None:
    """Close an async database session.

    Args:
        session: The AsyncSession to close.
    """
    await session.close()


@contextmanager
def get_db(database: str = "models") -> Generator[Session, None, None]:
    """Get a synchronous database session (for FastAPI dependency injection).

    Args:
        database: The database name.

    Yields:
        A SQLAlchemy Session object.
    """
    session = session_factories[database]()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
