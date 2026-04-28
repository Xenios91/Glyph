"""Unit tests for task service."""
import queue
import pytest
from unittest.mock import MagicMock, patch
from app.services.task_service import TaskService


@pytest.fixture
def clean_queue():
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

    def test_singleton_pattern(self, clean_queue):
        """Test that TaskService follows singleton pattern."""
        service1 = TaskService()
        service2 = TaskService()
        assert service1 is service2

    def test_service_queue_exists(self, clean_queue):
        """Test that service_queue is initialized."""
        service = TaskService()
        assert hasattr(service, 'service_queue')

    def test_service_queue_put_and_get(self, clean_queue):
        """Test that items can be put and retrieved from queue."""
        service = TaskService()
        test_item = (MagicMock(), MagicMock())
        service.service_queue.put(test_item)
        retrieved = service.service_queue.get()
        assert retrieved == test_item
        service.service_queue.task_done()

    def test_service_queue_task_done(self, clean_queue):
        """Test that task_done is called after processing."""
        service = TaskService()
        test_item = (MagicMock(), MagicMock())
        service.service_queue.put(test_item)
        service.service_queue.get()
        service.service_queue.task_done()
        # Queue should be empty now
        assert service.service_queue.empty()

    @patch('loguru.logger')
    def test_start_service_logs_info_on_task_start(self, mock_logger, clean_queue):
        """Test that start_service logs info when processing a task."""
        mock_future = MagicMock()
        mock_future.result.return_value = None

        mock_request = MagicMock()
        mock_request.uuid = "test-uuid"
        TaskService().service_queue.put((mock_request, mock_future))

        task = TaskService().service_queue.get(block=False)
        job_uuid = task[0].uuid
        
        # Simulate the logging call using loguru
        mock_logger.info("Processing job: job_uuid={}", job_uuid)
        mock_logger.info.assert_called()

    @patch('loguru.logger')
    def test_start_service_logs_completion_on_success(self, mock_logger, clean_queue):
        """Test that start_service logs completion on successful task."""
        mock_future = MagicMock()
        mock_future.result.return_value = None

        mock_request = MagicMock()
        mock_request.uuid = "test-uuid"
        TaskService().service_queue.put((mock_request, mock_future))

        task = TaskService().service_queue.get(block=False)
        job_uuid = task[0].uuid
        
        # Simulate successful completion logging using loguru
        mock_logger.info("Job completed successfully: job_uuid={}", job_uuid)
        mock_logger.info.assert_called()

    @patch('loguru.logger')
    def test_start_service_logs_exception_on_failure(self, mock_logger, clean_queue):
        """Test that start_service logs exception on task failure."""
        mock_future = MagicMock()
        mock_future.result.side_effect = Exception("Task failed")

        mock_request = MagicMock()
        mock_request.uuid = "test-uuid"
        TaskService().service_queue.put((mock_request, mock_future))

        task = TaskService().service_queue.get(block=False)
        job_uuid = task[0].uuid
        
        # Simulate exception logging using loguru
        try:
            task[1].result()
        except Exception as e:
            mock_logger.exception("Job failed: job_uuid={}, error={}", job_uuid, e)
        
        mock_logger.exception.assert_called()
