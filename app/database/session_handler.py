"""Database session management for Glyph application."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from sqlalchemy import event, func, or_, select, text, update
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database.models import (
    APIKey,
    Base,
    BehavioralScanReport,
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
        BehavioralScanReport.__table__,
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
# (table_name, column_name, sql_type) triples for the idempotent startup
# migration.
_OWNER_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("models", "user_id", "INTEGER"),
    ("predictions", "user_id", "INTEGER"),
    ("functions", "user_id", "INTEGER"),
    ("scan_reports", "user_id", "INTEGER"),
    ("llm_analysis_results", "user_id", "INTEGER"),
)


async def _ensure_columns(engine: AsyncEngine, columns: tuple[tuple[str, str, str], ...]) -> None:
    """Add missing columns to pre-existing tables (idempotent).

    ``create_all`` never alters existing tables, so deployments that already
    have a table get the new columns here with a raw ``ALTER TABLE`` guarded
    by a column-existence check.

    Args:
        engine: The async engine to migrate.
        columns: (table_name, column_name, sql_type) triples to add.

    """
    async with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return
        for table_name, column_name, column_type in columns:
            rows = (await conn.execute(text(f"PRAGMA table_info({table_name})"))).fetchall()
            if not rows:
                # Table does not exist yet; create_all will build it with the column.
                continue
            existing_cols = {row[1] for row in rows}
            if column_name in existing_cols:
                continue
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
            logger.info(f"Added {column_name} column to {table_name} table")


async def _ensure_owner_columns(engine: AsyncEngine) -> None:
    """Add the ``user_id`` owner columns if they are missing (idempotent).

    Existing deployments have tables created before the multi-tenancy change;
    ``create_all`` never alters existing tables, so the new columns are added
    here with a raw ``ALTER TABLE`` guarded by a column-existence check.
    """
    await _ensure_columns(engine, _OWNER_COLUMNS)


# (table_name, column_name, sql_type) triples for the LLM verdict columns added
# after the initial llm_analysis_results schema.
_LLM_VERDICT_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("llm_analysis_results", "is_vulnerability", "BOOLEAN"),
    ("llm_analysis_results", "confidence", "VARCHAR(16) DEFAULT ''"),
    ("llm_analysis_results", "verdict", "VARCHAR(32) DEFAULT ''"),
)


async def _ensure_llm_verdict_columns(engine: AsyncEngine) -> None:
    """Add the LLM verdict columns to pre-existing llm_analysis_results tables.

    ``create_all`` never alters existing tables, so deployments that already
    have the table (from before the verdict feature) get the new columns here
    with a raw ``ALTER TABLE`` guarded by a column-existence check.
    """
    await _ensure_columns(engine, _LLM_VERDICT_COLUMNS)


# (table_name, column_name, sql_type) for the denormalized prediction function
# count added after the initial predictions schema.
_PREDICTION_COUNT_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("predictions", "function_count", "INTEGER NOT NULL DEFAULT 0"),
)


async def _ensure_prediction_count_columns(engine: AsyncEngine) -> None:
    """Add the ``function_count`` column to pre-existing predictions tables.

    ``create_all`` never alters existing tables, so deployments that already
    have the table (from before the lightweight-list feature) get the new
    column here with a raw ``ALTER TABLE`` guarded by a column-existence check.
    """
    await _ensure_columns(engine, _PREDICTION_COUNT_COLUMNS)


# The per-user prediction unique constraint. Older schemas have
# UNIQUE(task_name, model_name); current schemas have
# UNIQUE(task_name, model_name, user_id). Detected via PRAGMA index_info.
_PREDICTION_OLD_UNIQUE_COLS = ("task_name", "model_name")
_PREDICTION_NEW_UNIQUE_COLS = ("task_name", "model_name", "user_id")


def _unique_columns_for(conn: Any, table: str, candidates: tuple[tuple[str, ...], ...]) -> tuple[str, ...] | None:
    """Return the column tuple of a table's unique index, or None.

    Inspects the table's unique indexes via PRAGMA and returns the column
    ordering of the one whose columns match one of *candidates*.

    Args:
        conn: A synchronous connection.
        table: The table name to inspect.
        candidates: Column tuples identifying the expected unique index.

    """
    rows = conn.execute(text(f"PRAGMA index_list({table})")).fetchall()
    for row in rows:
        # row: (seq, name, unique, origin, partial)
        name, unique = row[1], row[2]
        if not unique:
            continue
        cols = tuple(r[2] for r in conn.execute(text(f"PRAGMA index_info({name})")).fetchall())
        if cols in candidates:
            return cols
    return None


def _prediction_unique_columns(conn: Any) -> tuple[str, ...] | None:
    """Return the column tuple of the predictions unique index, or None.

    Inspects the table's unique indexes via PRAGMA and returns the column
    ordering of the one that covers (task_name, model_name[, user_id]).
    """
    return _unique_columns_for(conn, "predictions", (_PREDICTION_OLD_UNIQUE_COLS, _PREDICTION_NEW_UNIQUE_COLS))


_PREDICTION_COLUMNS: tuple[str, ...] = (
    "id",
    "task_name",
    "model_name",
    "functions_data",
    "created_at",
    "modified_at",
    "user_id",
    "function_count",
)

_PREDICTION_NEW_DDL = (
    "CREATE TABLE predictions ("
    "id INTEGER NOT NULL, "
    "task_name VARCHAR(64) NOT NULL, "
    "model_name VARCHAR(64) NOT NULL, "
    "functions_data BLOB NOT NULL, "
    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
    "modified_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
    "user_id INTEGER, "
    "function_count INTEGER NOT NULL DEFAULT 0, "
    "PRIMARY KEY (id), "
    "CONSTRAINT uq_predictions_task_model_user UNIQUE (task_name, model_name, user_id)"
    ")"
)


async def _rebuild_with_per_user_constraint(
    conn: Any,
    *,
    table: str,
    columns: tuple[str, ...],
    new_ddl: str,
    old_unique: tuple[str, ...],
    new_unique: tuple[str, ...],
    secondary_indexes: tuple[str, ...] = (),
) -> None:
    """Rebuild *table* to add ``user_id`` to its unique constraint (SQLite).

    SQLite cannot ALTER a unique constraint, so the table is rebuilt: rename,
    recreate with the new constraint, copy rows, drop the old table, and
    recreate the secondary indexes. This is safe without deduplication because
    the old (tighter) constraint guarantees at most one row per old key, which
    trivially satisfies the new (looser) per-user constraint.

    Args:
        conn: An open async connection (caller manages the transaction).
        table: The table to rebuild.
        columns: All columns of the table, in order (used for the row copy).
        new_ddl: The ``CREATE TABLE`` statement for the rebuilt table.
        old_unique: The old unique-constraint columns (already detected).
        new_unique: The new (per-user) unique-constraint columns.
        secondary_indexes: Optional ``CREATE INDEX`` statements to re-run.

    """
    await conn.execute(text(f"ALTER TABLE {table} RENAME TO {table}_old"))
    await conn.execute(text(new_ddl))
    col_list = ", ".join(columns)
    await conn.execute(text(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"))
    await conn.execute(text(f"DROP TABLE {table}_old"))
    for index_sql in secondary_indexes:
        await conn.execute(text(index_sql))
    logger.info(
        "Migrated {} unique constraint to per-user scope ({} -> {})",
        table,
        ", ".join(old_unique),
        ", ".join(new_unique),
    )


async def _ensure_prediction_per_user_constraint(engine: AsyncEngine) -> None:
    """Migrate the predictions unique constraint to per-user scope (idempotent).

    Older deployments carry ``UNIQUE(task_name, model_name)``. The multi-tenant
    design scopes task-name uniqueness per user, so the constraint becomes
    ``UNIQUE(task_name, model_name, user_id)``. SQLite cannot ALTER a unique
    constraint, so the table is rebuilt (see
    :func:`_rebuild_with_per_user_constraint`).
    """
    async with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return
        rows = (await conn.execute(text("PRAGMA table_info(predictions)"))).fetchall()
        if not rows:
            # Table does not exist yet; create_all builds it with the new constraint.
            return
        cols = await conn.run_sync(lambda sync_conn: _prediction_unique_columns(sync_conn))
        if cols is None or cols == _PREDICTION_NEW_UNIQUE_COLS:
            # Already on the per-user constraint (or no recognizable index).
            return
        await _rebuild_with_per_user_constraint(
            conn,
            table="predictions",
            columns=_PREDICTION_COLUMNS,
            new_ddl=_PREDICTION_NEW_DDL,
            old_unique=cols,
            new_unique=_PREDICTION_NEW_UNIQUE_COLS,
            secondary_indexes=("CREATE INDEX IF NOT EXISTS ix_predictions_user_id ON predictions (user_id)",),
        )


_LLM_RESULT_OLD_UNIQUE_COLS = ("target_name", "function_name", "containing_function", "entrypoint")
_LLM_RESULT_NEW_UNIQUE_COLS = (
    "target_name",
    "function_name",
    "containing_function",
    "entrypoint",
    "user_id",
)

# All llm_analysis_results columns, in order (used for the row copy during the
# per-user-constraint rebuild). The verdict columns are guaranteed present by
# the time the rebuild runs (see the init ordering).
_LLM_RESULT_COLUMNS: tuple[str, ...] = (
    "id",
    "target_name",
    "user_id",
    "function_name",
    "containing_function",
    "entrypoint",
    "status",
    "analysis",
    "error",
    "model_name",
    "elapsed_ms",
    "is_vulnerability",
    "confidence",
    "verdict",
    "created_at",
    "modified_at",
)

_LLM_RESULT_NEW_DDL = (
    "CREATE TABLE llm_analysis_results ("
    "id INTEGER NOT NULL, "
    "target_name VARCHAR(256) NOT NULL, "
    "user_id INTEGER, "
    "function_name VARCHAR(256) NOT NULL, "
    "containing_function VARCHAR(256) NOT NULL, "
    "entrypoint VARCHAR(32) NOT NULL, "
    "status VARCHAR(16) NOT NULL, "
    "analysis TEXT NOT NULL DEFAULT '', "
    "error TEXT NOT NULL DEFAULT '', "
    "model_name VARCHAR(128) NOT NULL DEFAULT '', "
    "elapsed_ms INTEGER NOT NULL DEFAULT 0, "
    "is_vulnerability BOOLEAN, "
    "confidence VARCHAR(16) NOT NULL DEFAULT '', "
    "verdict VARCHAR(32) NOT NULL DEFAULT '', "
    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
    "modified_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
    "PRIMARY KEY (id), "
    "CONSTRAINT uq_llm_analysis_target_function "
    "UNIQUE (target_name, function_name, containing_function, entrypoint, user_id)"
    ")"
)


def _llm_result_unique_columns(conn: Any) -> tuple[str, ...] | None:
    """Return the column tuple of the llm_analysis_results unique index, or None.

    Inspects the table's unique indexes via PRAGMA and returns the column
    ordering of the one that covers the (old or new) unique key.
    """
    return _unique_columns_for(conn, "llm_analysis_results", (_LLM_RESULT_OLD_UNIQUE_COLS, _LLM_RESULT_NEW_UNIQUE_COLS))


async def _ensure_llm_result_per_user_constraint(engine: AsyncEngine) -> None:
    """Migrate the llm_analysis_results unique constraint to per-user scope (idempotent).

    Older deployments carry ``UNIQUE(target_name, function_name,
    containing_function, entrypoint)``. The multi-tenant design scopes stored
    LLM results per user, so the constraint becomes
    ``UNIQUE(target_name, function_name, containing_function, entrypoint,
    user_id)``. SQLite cannot ALTER a unique constraint, so the table is
    rebuilt (see :func:`_rebuild_with_per_user_constraint`).
    """
    async with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return
        rows = (await conn.execute(text("PRAGMA table_info(llm_analysis_results)"))).fetchall()
        if not rows:
            # Table does not exist yet; create_all builds it with the new constraint.
            return
        cols = await conn.run_sync(lambda sync_conn: _llm_result_unique_columns(sync_conn))
        if cols is None or cols == _LLM_RESULT_NEW_UNIQUE_COLS:
            # Already on the per-user constraint (or no recognizable index).
            return
        await _rebuild_with_per_user_constraint(
            conn,
            table="llm_analysis_results",
            columns=_LLM_RESULT_COLUMNS,
            new_ddl=_LLM_RESULT_NEW_DDL,
            old_unique=cols,
            new_unique=_LLM_RESULT_NEW_UNIQUE_COLS,
            secondary_indexes=(
                "CREATE INDEX IF NOT EXISTS ix_llm_analysis_results_target_name ON llm_analysis_results (target_name)",
                "CREATE INDEX IF NOT EXISTS ix_llm_analysis_results_user_id ON llm_analysis_results (user_id)",
            ),
        )


async def _backfill_prediction_function_count() -> None:
    """Backfill ``function_count`` on prediction rows where it is unset.

    Runs once per startup; only touches rows whose ``function_count`` is 0 or
    NULL, so it is cheap on subsequent starts. The count is derived by
    deserializing the ``functions_data`` BLOB once per affected row.
    """
    from app.utils.secure_deserializer import SecureDeserializationError, secure_load_bytes

    session: AsyncSession = await get_async_session("predictions")
    try:
        rows = (
            await session.execute(
                select(Prediction.id, Prediction.functions_data).where(
                    or_(Prediction.function_count.is_(None), Prediction.function_count == 0)
                )
            )
        ).all()
        for pred_id, functions_data in rows:
            count = 0
            try:
                raw = await asyncio.to_thread(secure_load_bytes, functions_data)
                if isinstance(raw, list):
                    count = len(raw)
            except SecureDeserializationError:
                logger.warning("Blocked deserializing prediction id {} during function_count backfill", pred_id)
            except Exception:
                logger.exception("Failed to backfill function_count for prediction id {}", pred_id)
            await session.execute(update(Prediction).where(Prediction.id == pred_id).values(function_count=count))
        await session.commit()
        if rows:
            logger.info("Backfilled function_count for {} prediction rows", len(rows))
    except sa_exc.SQLAlchemyError:
        await session.rollback()
        logger.exception("Failed to backfill prediction function_count")
    finally:
        await close_async_session(session)


async def _backfill_owner_columns() -> None:
    """Backfill ``user_id`` on legacy rows from the owning binary where possible.

    Runs once per startup; only touches rows whose ``user_id`` is NULL, so it
    is cheap on subsequent starts. Rows that cannot be attributed (no matching
    binary, or the binary has no uploader) remain NULL and are treated as
    unowned by the ownership dependencies.

    Backfill rules (by name match):
    - ``models``: model_name == Binary.name -> Binary.uploaded_by
    - ``functions``: model_name -> owning Model.user_id (or Binary fallback)
    - ``predictions``: task_name == Binary.name -> Binary.uploaded_by
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
        b_rows = (await b_session.execute(select(Binary.name, Binary.uploaded_by))).all()
        binary_owner: dict[str, int | None] = {row[0]: row[1] for row in b_rows}

        # 1) Models from their binary.
        m_rows = (await m_session.execute(select(Model.id, Model.model_name).where(Model.user_id.is_(None)))).all()
        for model_id, model_name in m_rows:
            owner = binary_owner.get(model_name)
            if owner is not None:
                await m_session.execute(update(Model).where(Model.id == model_id).values(user_id=owner))
        await m_session.commit()

        # Re-read model owners (now backfilled) for dependent tables.
        m_all = (await m_session.execute(select(Model.model_name, Model.user_id))).all()
        model_owner: dict[str, int | None] = {row[0]: row[1] for row in m_all}

        # 2) Functions from their model (or binary fallback).
        f_rows = (
            await f_session.execute(select(Function.id, Function.model_name).where(Function.user_id.is_(None)))
        ).all()
        for fn_id, model_name in f_rows:
            owner = model_owner.get(model_name)
            if owner is None:
                owner = binary_owner.get(model_name)
            if owner is not None:
                await f_session.execute(update(Function).where(Function.id == fn_id).values(user_id=owner))
        await f_session.commit()

        # 3) Predictions from their task/binary.
        p_rows = (
            await p_session.execute(select(Prediction.id, Prediction.task_name).where(Prediction.user_id.is_(None)))
        ).all()
        for pred_id, task_name in p_rows:
            owner = binary_owner.get(task_name)
            if owner is not None:
                await p_session.execute(update(Prediction).where(Prediction.id == pred_id).values(user_id=owner))
        await p_session.commit()

        # Re-read prediction owners (now backfilled).
        p_all = (await p_session.execute(select(Prediction.task_name, Prediction.user_id))).all()
        pred_owner: dict[str, int | None] = {row[0]: row[1] for row in p_all}

        # 4) Scan reports from target name (binary / model / prediction owner).
        s_rows = (
            await i_session.execute(select(ScanReport.id, ScanReport.target_name).where(ScanReport.user_id.is_(None)))
        ).all()
        for report_id, target_name in s_rows:
            owner = binary_owner.get(target_name) or model_owner.get(target_name) or pred_owner.get(target_name)
            if owner is not None:
                await i_session.execute(update(ScanReport).where(ScanReport.id == report_id).values(user_id=owner))
        await i_session.commit()

        # Re-read scan report owners (now backfilled).
        s_all = (await i_session.execute(select(ScanReport.target_name, ScanReport.user_id))).all()
        report_owner: dict[str, int | None] = {row[0]: row[1] for row in s_all}

        # 5) LLM results from their scan report (or target fallback).
        l_rows = (
            await i_session.execute(
                select(LLMAnalysisResult.id, LLMAnalysisResult.target_name).where(LLMAnalysisResult.user_id.is_(None))
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
                    update(LLMAnalysisResult).where(LLMAnalysisResult.id == result_id).values(user_id=owner)
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
                await session.execute(select(func.count()).select_from(model_cls).where(model_cls.user_id.is_(None)))
            ).scalar_one()
            if unowned:
                logger.warning(f"{unowned} row(s) in {table_name} remain unowned (user_id is NULL) after backfill")


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
        # LLM verdict columns added after the initial llm_analysis_results schema.
        await _ensure_llm_verdict_columns(async_engines[name])
        # Denormalized prediction function count for lightweight list queries.
        await _ensure_prediction_count_columns(async_engines[name])
        # Per-user prediction unique constraint (table rebuild for SQLite).
        if name == "predictions":
            await _ensure_prediction_per_user_constraint(async_engines[name])
        # Per-user LLM result unique constraint (table rebuild for SQLite).
        if name == "intelligence":
            await _ensure_llm_result_per_user_constraint(async_engines[name])
    try:
        await _backfill_owner_columns()
    except Exception as e:  # pragma: no cover - defensive: never block startup
        logger.error(f"Ownership backfill failed: {e}")
    try:
        await _backfill_prediction_function_count()
    except Exception as e:  # pragma: no cover - defensive: never block startup
        logger.error(f"Prediction function_count backfill failed: {e}")


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
    """Close an async database session.

    Standard helper for repositories that acquire a session via
    :func:`get_async_session` and manage its lifecycle explicitly. Prefer
    the :func:`async_session` context manager for new code.
    """
    await session.close()


async def dispose_async_engines() -> None:
    """Dispose all async database engines."""
    for name, engine in async_engines.items():
        await engine.dispose()
        logger.info("Async database '{}' engine disposed", name)
    async_engines.clear()
    async_session_factories.clear()
