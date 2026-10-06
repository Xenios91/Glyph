"""Database session management for Glyph application."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from sqlalchemy import event, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database.models import (
    APIKey,
    Base,
    Binary,
    BinaryFunction,
    Function,
    LLMAnalysisResult,
    LLMUserConfig,
    Model,
    Prediction,
    ScanReport,
    SimilarityComputation,
    SimilarityPair,
    User,
)


def _data_dir() -> str:
    """Return the data directory for the SQLite databases.

    Defaults to ``data`` (relative to the working directory) but can be
    overridden with the ``GLYPH_DATA_DIR`` environment variable. This lets
    isolated test suites (e.g. the Playwright e2e suite) point the application
    at a clean, temporary directory so state does not leak between runs.
    """
    return os.environ.get("GLYPH_DATA_DIR", "data")


def _build_default_database_urls() -> dict[str, str]:
    """Build the default per-purpose SQLite database URLs from the data dir."""
    data_dir = _data_dir()
    return {
        "models": f"sqlite+aiosqlite:///{data_dir}/models.db",
        "predictions": f"sqlite+aiosqlite:///{data_dir}/predictions.db",
        "functions": f"sqlite+aiosqlite:///{data_dir}/functions.db",
        "auth": f"sqlite+aiosqlite:///{data_dir}/auth.db",
        "binaries": f"sqlite+aiosqlite:///{data_dir}/binaries.db",
        "intelligence": f"sqlite+aiosqlite:///{data_dir}/intelligence.db",
    }


_DEFAULT_ASYNC_DATABASE_URLS: dict[str, str] = _build_default_database_urls()

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
    "auth": [User.__table__, APIKey.__table__, LLMUserConfig.__table__],
    "binaries": [Binary.__table__, BinaryFunction.__table__],
    "intelligence": [
        SimilarityComputation.__table__,
        SimilarityPair.__table__,
        LLMAnalysisResult.__table__,
        ScanReport.__table__,
    ],
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
        poolclass=NullPool,
    )
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    return engine


# Tables that gained a ``user_id`` owner column (multi-tenancy).
# (table_name, column_name) pairs for the idempotent startup migration.
_OWNER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("models", "user_id"),
    ("predictions", "user_id"),
    ("functions", "user_id"),
    ("scan_reports", "user_id"),
    ("llm_analysis_results", "user_id"),
)


async def _ensure_owner_columns(engine: AsyncEngine) -> None:
    """Add the ``user_id`` owner columns if they are missing (idempotent).

    Existing deployments have tables created before the multi-tenancy change;
    ``create_all`` never alters existing tables, so the new columns are added
    here with a raw ``ALTER TABLE`` guarded by a column-existence check.
    """
    async with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return
        for table_name, column_name in _OWNER_COLUMNS:
            rows = (await conn.execute(text(f"PRAGMA table_info({table_name})"))).fetchall()
            if not rows:
                # Table does not exist yet; create_all will build it with the column.
                continue
            existing_cols = {row[1] for row in rows}
            if column_name in existing_cols:
                continue
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} INTEGER"))
            logger.info(f"Added {column_name} column to {table_name} table")


async def _backfill_owner_columns() -> None:
    """Backfill ``user_id`` on legacy rows from the owning binary where possible.

    Runs once per startup; only touches rows whose ``user_id`` is NULL, so it
    is cheap on subsequent starts. Rows that cannot be attributed (no matching
    binary, or the binary has no uploader) remain NULL and are treated as
    unowned by the ownership dependencies.

    Backfill rules (by name match):
    - ``models``: model_name == Binary.binary_name -> Binary.uploaded_by
    - ``functions``: model_name -> owning Model.user_id (or Binary fallback)
    - ``predictions``: task_name == Binary.binary_name -> Binary.uploaded_by
    - ``scan_reports`` / ``llm_analysis_results``: target_name -> owner of the
      matching Binary / Model / Prediction / ScanReport row.
    """
    async with (
        async_session("binaries") as b_session,
        async_session("models") as m_session,
        async_session("functions") as f_session,
        async_session("predictions") as p_session,
        async_session("intelligence") as i_session,
    ):
        # Binary owner map (shared across all backfills).
        b_rows = (
            await b_session.execute(select(Binary.binary_name, Binary.uploaded_by))
        ).all()
        binary_owner: dict[str, int | None] = dict(b_rows)

        # 1) Models from their binary.
        m_rows = (
            await m_session.execute(
                select(Model.id, Model.model_name).where(Model.user_id.is_(None))
            )
        ).all()
        for model_id, model_name in m_rows:
            owner = binary_owner.get(model_name)
            if owner is not None:
                await m_session.execute(
                    update(Model).where(Model.id == model_id).values(user_id=owner)
                )
        await m_session.commit()

        # Re-read model owners (now backfilled) for dependent tables.
        m_all = (await m_session.execute(select(Model.model_name, Model.user_id))).all()
        model_owner: dict[str, int | None] = dict(m_all)

        # 2) Functions from their model (or binary fallback).
        f_rows = (
            await f_session.execute(
                select(Function.id, Function.model_name).where(Function.user_id.is_(None))
            )
        ).all()
        for fn_id, model_name in f_rows:
            owner = model_owner.get(model_name)
            if owner is None:
                owner = binary_owner.get(model_name)
            if owner is not None:
                await f_session.execute(
                    update(Function).where(Function.id == fn_id).values(user_id=owner)
                )
        await f_session.commit()

        # 3) Predictions from their task/binary.
        p_rows = (
            await p_session.execute(
                select(Prediction.id, Prediction.task_name).where(Prediction.user_id.is_(None))
            )
        ).all()
        for pred_id, task_name in p_rows:
            owner = binary_owner.get(task_name)
            if owner is not None:
                await p_session.execute(
                    update(Prediction).where(Prediction.id == pred_id).values(user_id=owner)
                )
        await p_session.commit()

        # Re-read prediction owners (now backfilled).
        p_all = (await p_session.execute(select(Prediction.task_name, Prediction.user_id))).all()
        pred_owner: dict[str, int | None] = dict(p_all)

        # 4) Scan reports from target name (binary / model / prediction owner).
        s_rows = (
            await i_session.execute(
                select(ScanReport.id, ScanReport.target_name).where(ScanReport.user_id.is_(None))
            )
        ).all()
        for report_id, target_name in s_rows:
            owner = (
                binary_owner.get(target_name)
                or model_owner.get(target_name)
                or pred_owner.get(target_name)
            )
            if owner is not None:
                await i_session.execute(
                    update(ScanReport).where(ScanReport.id == report_id).values(user_id=owner)
                )
        await i_session.commit()

        # Re-read scan report owners (now backfilled).
        s_all = (
            await i_session.execute(select(ScanReport.target_name, ScanReport.user_id))
        ).all()
        report_owner: dict[str, int | None] = dict(s_all)

        # 5) LLM results from their scan report (or target fallback).
        l_rows = (
            await i_session.execute(
                select(LLMAnalysisResult.id, LLMAnalysisResult.target_name).where(
                    LLMAnalysisResult.user_id.is_(None)
                )
            )
        ).all()
        for result_id, target_name in l_rows:
            owner = (
                report_owner.get(target_name)
                or binary_owner.get(target_name)
                or model_owner.get(target_name)
                or pred_owner.get(target_name)
            )
            if owner is not None:
                await i_session.execute(
                    update(LLMAnalysisResult)
                    .where(LLMAnalysisResult.id == result_id)
                    .values(user_id=owner)
                )
        await i_session.commit()

        # Log the count of rows that remain unowned (NULL) so operators can see
        # how much legacy data could not be attributed.
        for session, model_cls, table_name in (
            (m_session, Model, "models"),
            (f_session, Function, "functions"),
            (p_session, Prediction, "predictions"),
            (i_session, ScanReport, "scan_reports"),
            (i_session, LLMAnalysisResult, "llm_analysis_results"),
        ):
            unowned = (
                await session.execute(
                    select(func.count())
                    .select_from(model_cls)
                    .where(model_cls.user_id.is_(None))
                )
            ).scalar_one()
            if unowned:
                logger.warning(
                    f"{unowned} row(s) in {table_name} remain unowned (user_id is NULL) "
                    "after backfill"
                )


async def init_async_databases() -> None:
    """Initialize all async database tables."""
    for name, url in ASYNC_DATABASE_URLS.items():
        # Ensure the directory for file-based (SQLite) databases exists so a
        # freshly configured data directory (e.g. a temp dir for tests) works
        # without a pre-existing folder.
        if url.startswith("sqlite"):
            db_path = url.split("///", 1)[-1]
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

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

    # Multi-tenancy: add the user_id owner columns to pre-existing tables
    # (idempotent) and backfill ownership on legacy rows where possible.
    for name in async_engines:
        await _ensure_owner_columns(async_engines[name])
    try:
        await _backfill_owner_columns()
    except Exception as e:  # pragma: no cover - defensive: never block startup
        logger.error(f"Ownership backfill failed: {e}")


async def get_async_session(database: str = "auth") -> AsyncSession:
    """Get an async database session.

    Prefer using :func:`async_session` context manager for automatic cleanup.
    """
    if database not in async_session_factories:
        raise ValueError(f"Invalid database name: {database}. Must be one of: {list(async_session_factories.keys())}")

    return async_session_factories[database]()


@asynccontextmanager
async def async_session(database: str = "auth") -> AsyncIterator[AsyncSession]:
    """Async context manager for database sessions.

    Ensures the session is properly closed after use.

    Example:
        async with async_session("auth") as session:
            await session.execute(...)

    """
    session = await get_async_session(database)
    try:
        yield session
    finally:
        await session.close()


async def close_async_session(session: AsyncSession) -> None:
    """Close an async database session (legacy, prefer async_session context manager)."""
    await session.close()


async def dispose_async_engines() -> None:
    """Dispose all async database engines."""
    for name, engine in async_engines.items():
        await engine.dispose()
        logger.info("Async database '{}' engine disposed", name)
    async_engines.clear()
    async_session_factories.clear()
