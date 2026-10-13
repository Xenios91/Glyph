"""Unit tests for SQLite directory handling in the session handler."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.database.session_handler import _create_engine, _ensure_sqlite_directory


class TestEnsureSqliteDirectory:
    """Tests for automatic creation of SQLite parent directories."""

    def test_creates_missing_nested_parent_directory(self, tmp_path: Any):
        """A missing nested parent directory for a SQLite file is created."""
        nested = Path(tmp_path) / "new" / "nested"
        _ensure_sqlite_directory(f"sqlite+aiosqlite:///{nested / 'test.db'}")
        assert nested.is_dir()

    def test_relative_path_resolves_against_cwd(self, tmp_path: Any, monkeypatch: Any):
        """Relative paths like data/models.db resolve against the current working directory."""
        monkeypatch.chdir(tmp_path)
        _ensure_sqlite_directory("sqlite+aiosqlite:///data/models.db")
        assert (Path(tmp_path) / "data").is_dir()

    def test_memory_database_is_skipped(self):
        """`:memory:` URLs never touch the filesystem."""
        with patch("app.database.session_handler.os.makedirs") as mock_makedirs:
            _ensure_sqlite_directory("sqlite+aiosqlite:///:memory:")
            mock_makedirs.assert_not_called()

    def test_shared_memory_file_uri_is_skipped(self):
        """`file:...?mode=memory` URIs used by unit tests never touch the filesystem."""
        with patch("app.database.session_handler.os.makedirs") as mock_makedirs:
            _ensure_sqlite_directory("sqlite+aiosqlite:///file:mem_models?mode=memory&cache=shared")
            mock_makedirs.assert_not_called()

    def test_bare_filename_needs_no_directory(self):
        """A bare filename in the working directory has no parent to create."""
        with patch("app.database.session_handler.os.makedirs") as mock_makedirs:
            _ensure_sqlite_directory("sqlite+aiosqlite:///bare.db")
            mock_makedirs.assert_not_called()

    def test_non_sqlite_url_is_skipped(self):
        """Non-SQLite backends are left alone."""
        with patch("app.database.session_handler.os.makedirs") as mock_makedirs:
            _ensure_sqlite_directory("postgresql+asyncpg://user:pass@localhost/glyph")
            mock_makedirs.assert_not_called()

    async def test_create_engine_creates_parent_directory(self, tmp_path: Any):
        """_create_engine prepares the database directory before engine creation."""
        nested = Path(tmp_path) / "created" / "by"
        engine = _create_engine(f"sqlite+aiosqlite:///{nested / 'engine.db'}")
        try:
            assert nested.is_dir()
        finally:
            await engine.dispose()
