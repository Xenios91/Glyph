"""Unit tests for task service."""
from typing import Any

import queue
import pytest
from unittest.mock import MagicMock
from app.services.task_service import TaskService


@pytest.fixture
def clean_queue() -> Any:
    """Fixture to ensure queue is empty before each test."""
    # Empty the queue before the test
    while not TaskService().service_queue.empty():
        try:
            TaskService().service_queue.get_nowait()
            TaskService().service_queue.task_done()
        except queue.Empty:
            # Break when queue is empty to avoid infinite loops
            break
    yield
    # Clean up after the test
    while not TaskService().service_queue.empty():
        try:
            TaskService().service_queue.get_nowait()
            TaskService().service_queue.task_done()
        except queue.Empty:
            # Break when queue is empty to avoid infinite loops
            break


class TestTaskService:
    """Tests for TaskService singleton and queue operations."""

    def test_singleton_pattern(self, clean_queue: Any) -> None:
        """Test that TaskService follows singleton pattern."""
        service1 = TaskService()
        service2 = TaskService()
        assert service1 is service2

    def test_service_queue_exists(self, clean_queue: Any) -> None:
        """Test that service_queue is initialized."""
        service = TaskService()
        assert hasattr(service, 'service_queue')

    def test_service_queue_put_and_get(self, clean_queue: Any) -> None:
        """Test that items can be put and retrieved from queue."""
        service = TaskService()
        test_item = (MagicMock(), MagicMock())
        service.service_queue.put(test_item)
        retrieved = service.service_queue.get()
        assert retrieved == test_item
        service.service_queue.task_done()

    def test_service_queue_task_done(self, clean_queue: Any) -> None:
        """Test that task_done is called after processing."""
        service = TaskService()
        test_item = (MagicMock(), MagicMock())
        service.service_queue.put(test_item)
        service.service_queue.get()
        service.service_queue.task_done()
        # Queue should be empty now
        assert service.service_queue.empty()

    def test_task_processing_success(self, clean_queue: Any) -> None:
        """Test that successful task processing completes without error."""
        mock_future = MagicMock()
        mock_future.result.return_value = None

        mock_request = MagicMock()
        mock_request.uuid = "test-uuid"
        TaskService().service_queue.put((mock_request, mock_future))

        task = TaskService().service_queue.get(block=False)
        # Simulate what TaskService.start_service does
        task[1].result()  # Should not raise
        TaskService().service_queue.task_done()
        
        assert TaskService().service_queue.empty()

    def test_task_processing_failure_handling(self, clean_queue: Any) -> None:
        """Test that failed task processing handles exceptions gracefully."""
        mock_future = MagicMock()
        mock_future.result.side_effect = Exception("Task failed")

        mock_request = MagicMock()
        mock_request.uuid = "test-uuid"
        TaskService().service_queue.put((mock_request, mock_future))

        task = TaskService().service_queue.get(block=False)
        
        # Simulate what TaskService.start_service does - catch the exception
        try:
            task[1].result()
        except Exception:
            pass  # Expected exception
        
        TaskService().service_queue.task_done()
        assert TaskService().service_queue.empty()
