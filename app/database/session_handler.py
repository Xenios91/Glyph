"""Database session management for Glyph application."""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base

DATABASE_URLS = {
    "models": "sqlite:///models.db",
    "predictions": "sqlite:///predictions.db",
    "functions": "sqlite:///functions.db",
}

engines = {name: create_engine(url, echo=False, future=True) for name, url in DATABASE_URLS.items()}

session_factories = {
    name: sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    for name, engine in engines.items()
}

logger = logging.getLogger(__name__)


def init_databases() -> None:
    """Initialize all database tables."""
    for name, engine in engines.items():
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database '%s' initialized successfully", name)
        except Exception as exc:
            logger.error("Failed to initialize database '%s': %s", name, exc)


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
