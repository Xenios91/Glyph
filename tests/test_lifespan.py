"""Tests for the lifespan module."""

from typing import Any

import pytest
from unittest.mock import Mock, patch

from app.core.lifespan import lifespan


class TestLifespan:
    """Tests for lifespan context manager."""

    @pytest.fixture
    def mock_app(self) -> Mock:
        """Create a mock FastAPI app."""
        app = Mock()
        return app

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_startup_success(
        self,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test successful lifespan startup."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        async with lifespan(mock_app):
            # Verify startup was called
            mock_get_settings.assert_called_once()
            mock_init_async_databases.assert_called_once()
            mock_threading.Thread.assert_called_once()
            mock_thread.start.assert_called_once()

    @patch("app.core.lifespan.get_settings")
    async def test_lifespan_startup_config_failure(
        self, mock_get_settings: Any, mock_app: Mock
    ) -> None:
        """Test lifespan startup fails on config error."""
        mock_get_settings.side_effect = RuntimeError("Config error")

        with pytest.raises(RuntimeError, match="Config error"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.init_async_databases")
    async def test_lifespan_startup_db_failure(
        self,
        mock_init_async_databases: Any,
        mock_get_settings: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan startup fails on DB error."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.side_effect = Exception("DB error")

        with pytest.raises(RuntimeError, match="Async database initialization failed"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_startup_task_service_failure(
        self,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan startup fails on task service error."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start.side_effect = Exception("Task service error")

        with pytest.raises(RuntimeError, match="Task service startup failed"):
            async with lifespan(mock_app):
                pass

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_shutdown(
        self,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan shutdown properly disposes async engines."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        # Use a flag to track if we entered the context
        entered = False

        async with lifespan(mock_app):
            entered = True

        assert entered is True
        # Verify dispose was called during shutdown
        mock_dispose_async_engines.assert_called_once()

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    async def test_lifespan_exception_during_yield(
        self,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan handles exception during yield."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        with pytest.raises(ValueError, match="Test exception"):
            async with lifespan(mock_app):
                raise ValueError("Test exception")

        # If we get here, the exception was properly propagated
        # and the finally block was executed
        # Verify dispose was still called during shutdown
        mock_dispose_async_engines.assert_called_once()

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    @patch("app.core.lifespan.EventWatcher")
    async def test_lifespan_starts_event_watcher(
        self,
        mock_event_watcher_class: Any,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan startup starts the EventWatcher."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        mock_event_watcher_instance = Mock()
        mock_event_watcher_class.return_value = mock_event_watcher_instance

        async with lifespan(mock_app):
            pass

        # Verify EventWatcher was instantiated and started
        mock_event_watcher_class.assert_called_once()
        mock_event_watcher_instance.start_watching.assert_called_once()

    @patch("app.core.lifespan.dispose_async_engines")
    @patch("app.core.lifespan.init_async_databases")
    @patch("app.core.lifespan.get_settings")
    @patch("app.core.lifespan.TaskService")
    @patch("app.core.lifespan.threading")
    @patch("app.core.lifespan.EventWatcher")
    async def test_lifespan_stops_event_watcher_on_shutdown(
        self,
        mock_event_watcher_class: Any,
        mock_threading: Any,
        mock_task_service: Any,
        mock_get_settings: Any,
        mock_init_async_databases: Any,
        mock_dispose_async_engines: Any,
        mock_app: Mock,
    ) -> None:
        """Test lifespan shutdown stops the EventWatcher."""
        mock_get_settings.return_value = Mock()
        mock_init_async_databases.return_value = None
        mock_dispose_async_engines.return_value = None

        mock_thread = Mock()
        mock_threading.Thread.return_value = mock_thread
        mock_thread.start = Mock()

        mock_event_watcher_instance = Mock()
        mock_event_watcher_class.return_value = mock_event_watcher_instance

        async with lifespan(mock_app):
            pass

        # Verify EventWatcher was stopped during shutdown
        mock_event_watcher_instance.stop_watching.assert_called_once()
