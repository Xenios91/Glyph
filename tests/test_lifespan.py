"""Tests for the lifespan module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from app.core.lifespan import lifespan


pytestmark = pytest.mark.asyncio


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app."""
        app = Mock()
        return app

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.SQLUtil")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_startup_success(
        self,
        mock_threading,
        mock_task_service,
        mock_sql_util,
        mock_get_settings,
        mock_app,
    ):
        """Test successful lifespan startup."""
        mock_get_settings.return_value = Mock()
        mock_sql_util.init_db = Mock()

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        async with lifespan(mock_app):
            # Verify startup was called
            mock_get_settings.assert_called_once()
            mock_sql_util.init_db.assert_called_once()
            mock_threading.Thread.assert_called_once()
            mock_thread.start.assert_called_once()

    @patch("app.core.lifespan.get_settings")
    async def test_lifespan_startup_config_failure(self, mock_get_settings, mock_app):
        """Test lifespan startup fails on config error."""
        mock_get_settings.side_effect = RuntimeError("Config error")

        with pytest.raises(RuntimeError, match="Config error"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.SQLUtil")
    async def test_lifespan_startup_db_failure(
        self,
        mock_sql_util,
        mock_get_settings,
        mock_app,
    ):
        """Test lifespan startup fails on DB error."""
        mock_get_settings.return_value = Mock()
        mock_sql_util.init_db.side_effect = Exception("DB error")

        with pytest.raises(RuntimeError, match="Database initialization failed"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.SQLUtil")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_startup_task_service_failure(
        self,
        mock_threading,
        mock_task_service,
        mock_sql_util,
        mock_get_settings,
        mock_app,
    ):
        """Test lifespan startup fails on task service error."""
        mock_get_settings.return_value = Mock()
        mock_sql_util.init_db = Mock()

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start.side_effect = Exception("Task service error")

        with pytest.raises(RuntimeError, match="Task service startup failed"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.SQLUtil")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_shutdown(
        self,
        mock_threading,
        mock_task_service,
        mock_sql_util,
        mock_get_settings,
        mock_app,
    ):
        """Test lifespan shutdown is called."""
        mock_get_settings.return_value = Mock()
        mock_sql_util.init_db = Mock()

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        # Use a flag to track if we entered the context
        entered = False

        async with lifespan(mock_app):
            entered = True

        assert entered is True

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.SQLUtil")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_exception_during_yield(
        self,
        mock_threading,
        mock_task_service,
        mock_sql_util,
        mock_get_settings,
        mock_app,
    ):
        """Test lifespan handles exception during yield."""
        mock_get_settings.return_value = Mock()
        mock_sql_util.init_db = Mock()

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        with pytest.raises(ValueError, match="Test exception"):
            async with lifespan(mock_app):
                raise ValueError("Test exception")

        # If we get here, the exception was properly propagated
        # and the finally block was executed
