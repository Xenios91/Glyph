"""Database session management for Glyph application."""

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.models import Base
from loguru import logger

# Async engines and sessions (for auth module)
ASYNC_DATABASE_URLS = {
    "models": "sqlite+aiosqlite:///data/models.db",
    "predictions": "sqlite+aiosqlite:///data/predictions.db",
    "functions": "sqlite+aiosqlite:///data/functions.db",
    "auth": "sqlite+aiosqlite:///data/auth.db",  # New database for auth
}

async_engines: dict[str, AsyncEngine] = {}
async_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def _configure_sqlite(dbapi_connection, connection_record) -> None:
    """Configure SQLite PRAGMA settings for better performance and reliability.

    Applied via SQLAlchemy's pool "connect" event to ensure all connections
    from the pool receive these settings. The callback receives the raw
    DBAPI connection and the connection record.

    Args:
        dbapi_connection: Raw DBAPI connection (sqlite3.Connection).
        connection_record: ConnectionPool_record (unused here).
    """
    # Execute PRAGMAs directly on the DBAPI connection cursor.
    # This is the standard SQLAlchemy pattern for SQLite PRAGMA setup.
    cursor = dbapi_connection.cursor()
    # Enable WAL mode for better concurrent read/write performance
    cursor.execute("PRAGMA journal_mode=WAL")
    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys=ON")
    # Set busy timeout to handle concurrent access (5 seconds)
    cursor.execute("PRAGMA busy_timeout=5000")
    # Enable synchronous mode for better performance while maintaining safety
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _create_engine(url: str) -> AsyncEngine:
    """Create an async engine optimized for SQLite with aiosqlite.

    Uses StaticPool to prevent connection multiplication issues with SQLite,
    and configures appropriate PRAGMA settings for better performance via
    SQLAlchemy's pool_connect event listener.

    Args:
        url: The database URL.

    Returns:
        Configured AsyncEngine instance.
    """
    engine = create_async_engine(
        url,
        echo=False,
        # StaticPool is recommended for SQLite to avoid connection multiplication
        poolclass=StaticPool,
        # connect_args are passed to aiosqlite.connect()
        connect_args={
            "check_same_thread": False,
        },
    )
    # Register PRAGMA configuration as a pool event listener so that
    # every new connection from the pool is properly configured.
    # This is the recommended SQLAlchemy 2.x pattern for SQLite setup.
    # Note: AsyncEngine requires listeners on engine.sync_engine since
    # asynchronous events are not yet supported by SQLAlchemy.
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    return engine


async def init_async_databases() -> None:
    """Initialize all async database tables."""
    for name, url in ASYNC_DATABASE_URLS.items():
        if name not in async_engines:
            async_engines[name] = _create_engine(url)
            # expire_on_commit=False prevents attributes from being expired
            # after commit, which is important for async patterns where
            # objects may be accessed after the transaction completes.
            # autoflush=False is recommended for explicit flush control.
            # autocommit=False is the default in SQLAlchemy 2.0 and redundant.
            async_session_factories[name] = async_sessionmaker(
                bind=async_engines[name],
                autoflush=False,
                expire_on_commit=False,
            )

        # Create tables (PRAGMAs are applied via pool_connect event)
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


async def dispose_async_engines() -> None:
    """Dispose all async database engines, releasing connections.

    Should be called during application shutdown to properly clean up resources.
    """
    for name, engine in async_engines.items():
        await engine.dispose()
        logger.info("Async database '{}' engine disposed", name)
    async_engines.clear()
    async_session_factories.clear()
