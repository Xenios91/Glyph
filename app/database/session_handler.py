"""Database session management for Glyph application."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from loguru import logger

# Async engines and sessions (for auth module)
ASYNC_DATABASE_URLS = {
    "models": "sqlite+aiosqlite:///models.db",
    "predictions": "sqlite+aiosqlite:///predictions.db",
    "functions": "sqlite+aiosqlite:///functions.db",
    "auth": "sqlite+aiosqlite:///auth.db",  # New database for auth
}

async_engines: dict[str, AsyncEngine] = {}
async_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


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
        logger.info(
            "Async database '{}' initialized successfully", name)


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
