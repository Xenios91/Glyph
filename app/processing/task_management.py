"""Task management module for Glyph application.

This module provides task execution management for training, prediction,
and Ghidra analysis tasks. It integrates with the pluggable pipeline
framework for processing binary analysis workflows.

"""

import atexit
import signal
import threading
import time
import uuid
from concurrent.futures import Future, ProcessPoolExecutor, wait, FIRST_COMPLETED
from typing import Any, Callable

from app.config.settings import MAX_CPU_CORES
from app.services.request_handler import GhidraRequest
from app.services.task_service import TaskService
from app.processing.pipeline import PipelineContext
from app.utils.logging_config import get_logger
from app.utils.request_context import get_request_context, set_request_context, clear_request_context

logger = get_logger(__name__)


def _run_with_context(job_uuid: str, target: Callable[..., Any], *args: Any) -> None:
    """Run a target function with propagated request context.

    Captures the current request context before entering the background thread
    and restores it within the target execution.

    Args:
        job_uuid: The job UUID to set as task_id.
        target: The callable to execute.
        *args: Arguments to pass to the target.
    """
    ctx = get_request_context()
    try:
        set_request_context(
            request_id=ctx.request_id,
            task_id=job_uuid,
            user_id=ctx.user_id,
            username=ctx.username,
        )
        target(*args)
    finally:
        clear_request_context()


class EventWatcher:
    """Event watcher for monitoring TaskManager executor futures."""

    _instance: "EventWatcher | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "EventWatcher":
        """Create or return the singleton instance of EventWatcher."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the EventWatcher."""
        if self._initialized:
            return
        self._initialized = True
        self._callbacks: dict[str, Callable[[Any, Any], None]] = {}
        self._watched_futures: dict[str, tuple[Any, Future]] = {}
        self._watching: bool = False
        self._watch_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None

    def register_callback(
        self,
        job_uuid: str,
        callback: Callable[[Any, Any], None],
        request: Any,
        future: Future,
    ) -> None:
        """Register a callback for a specific job UUID and track the future.

        Args:
            job_uuid: The UUID of the job to watch.
            callback: Callback function to invoke when job completes.
                      Receives (request, future) as arguments.
            request: The request object associated with this job.
            future: The Future object to monitor for completion.
        """
        self._callbacks[job_uuid] = callback
        self._watched_futures[job_uuid] = (request, future)
        logger.debug("Registered callback for job: job_uuid=%s", job_uuid)

    def start_watching(self) -> None:
        """Start watching for completed futures in a background thread."""
        if self._watching:
            logger.warning("EventWatcher is already watching")
            return

        self._watching = True
        self._stop_event = threading.Event()
        self._watch_thread = threading.Thread(
            target=self._watch_loop, name="EventWatcher", daemon=True
        )
        self._watch_thread.start()
        logger.info("EventWatcher started")

    def stop_watching(self) -> None:
        """Stop watching for completed futures."""
        if not self._watching:
            return

        logger.info("Stopping EventWatcher...")
        self._watching = False
        if self._stop_event is not None:
            self._stop_event.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None
        logger.info("EventWatcher stopped")

    def _watch_loop(self) -> None:
        """Background loop that watches for completed futures."""

        logger.debug("EventWatcher loop started")
        # Type guard: _stop_event is set in start_watching before this loop runs
        assert self._stop_event is not None
        while self._watching and not self._stop_event.is_set():
            try:
                # Get all futures we're watching
                if not self._watched_futures:
                    # No futures to watch, wait before checking again
                    time.sleep(2.5)
                    continue

                # Extract futures for waiting
                futures_only: list[Future] = [
                    task[1] for task in self._watched_futures.values()
                ]

                # Wait for any future to complete
                done, _ = wait(futures_only, timeout=2.5, return_when=FIRST_COMPLETED)

                for future in done:
                    # Find the corresponding job_uuid and request
                    for job_uuid, task in self._watched_futures.items():
                        if task[1] is future:
                            request = task[0]
                            # Invoke registered callback
                            if job_uuid in self._callbacks:
                                try:
                                    # Propagate request context to callback thread
                                    current_ctx = get_request_context()
                                    set_request_context(
                                        request_id=current_ctx.request_id,
                                        task_id=job_uuid,
                                        user_id=current_ctx.user_id,
                                        username=current_ctx.username,
                                    )
                                    self._callbacks[job_uuid](request, future)
                                    logger.debug(
                                        "Callback invoked for job: job_uuid=%s",
                                        job_uuid,
                                        extra={"extra_data": {"job_uuid": job_uuid, "task_id": job_uuid}},
                                    )
                                except Exception as callback_error:
                                    logger.error(
                                        "Callback error for job_uuid=%s: %s",
                                        job_uuid,
                                        callback_error,
                                        exc_info=True,
                                        extra={"extra_data": {"job_uuid": job_uuid}},
                                    )
                                finally:
                                    clear_request_context()
                            if (
                                self._watched_futures.get(job_uuid)
                                and self._watched_futures[job_uuid][1] is future
                            ):
                                del self._watched_futures[job_uuid]
                                logger.debug("Cleaned up job: %s", job_uuid)
                            else:
                                logger.debug(
                                    "Job %s was re-registered by callback, keeping alive.",
                                    job_uuid,
                                )

                            break

            except Exception as loop_error:
                logger.error("Error in EventWatcher loop: %s", loop_error, exc_info=True)
                # Wait before retrying
                time.sleep(1.0)

        logger.info("EventWatcher loop stopped")


class TaskManager:
    """Base class for managing tasks in Glyph application."""

    exec_pool: ProcessPoolExecutor | None = None
    _executor_shutdown: bool = False
    __instance: "TaskManager | None" = None

    def __init_subclass__(cls, **kwargs) -> None:
        """Initialize the process pool executor for subclasses."""
        super().__init_subclass__(**kwargs)
        if cls.exec_pool is None:
            cls.exec_pool = ProcessPoolExecutor(max_workers=MAX_CPU_CORES)
            # Register cleanup handlers
            atexit.register(cls._shutdown_executor)
            # Register signal handlers for graceful shutdown
            signal.signal(signal.SIGTERM, cls._signal_handler)
            signal.signal(signal.SIGINT, cls._signal_handler)

    def __new__(cls) -> "TaskManager":
        """Create or return the singleton instance of TaskManager."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def _get_executor(cls) -> ProcessPoolExecutor:
        """Get or create the process pool executor.

        Returns:
            The ProcessPoolExecutor instance.
        """
        if cls.exec_pool is None or cls._executor_shutdown:
            cls.exec_pool = ProcessPoolExecutor(max_workers=MAX_CPU_CORES)
            cls._executor_shutdown = False
        return cls.exec_pool

    @classmethod
    def _shutdown_executor(cls) -> None:
        """Shutdown the executor gracefully.

        This method is called on application exit or shutdown signals.
        """
        if cls.exec_pool is not None:
            cls.exec_pool.shutdown(wait=False, cancel_futures=True)
            cls.exec_pool = None
            cls._executor_shutdown = True
            logger.info("ProcessPoolExecutor shut down successfully")

    @classmethod
    def _signal_handler(cls, signum: int, _frame: Any) -> None:
        """Handle shutdown signals.

        Args:
            signum: The signal number received.
            _frame: The current stack frame (unused).
        """
        logger.info("Received signal %d, shutting down executor...", signum)
        cls._shutdown_executor()

    @classmethod
    def get_uuid(cls) -> str:
        """Generate a unique UUID.

        UUID4 uses 122 random bits, making collision probability
        approximately 1 in 5.3×10^36 - statistically impossible for practical use.

        Returns:
            A unique UUID string.
        """
        return str(uuid.uuid4())

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        """Get the status of a job by its UUID.

        Args:
            job_uuid: The UUID of the job.

        Returns:
            The status of the job or "UUID Not Found".
        """
        status: str = "UUID Not Found"
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                status = task[0].status
                break
        return status

    @classmethod
    def get_all_status(cls) -> dict[str, str]:
        """Get the status of all jobs in the queue.

        Returns:
            A dictionary mapping model names to their statuses.
        """
        status_list: dict[str, str] = {}
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            status: str = task[0].status
            model_name: str = task[0].model_name
            status_list[model_name] = status
        return status_list

    @classmethod
    def set_status(cls, job_uuid: str, status: str) -> bool:
        """Set the status of a job by its UUID.

        Args:
            job_uuid: The UUID of the job.
            status: The new status to set.

        Returns:
            True if the status was set, False if the UUID was not found.
        """
        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                task[0].status = status
                return True
        return False


class Ghidra(TaskManager):
    """Task manager for running Ghidra analysis on binaries.

    This class integrates with the pipeline framework to provide
    end-to-end binary analysis workflows.
    """

    @classmethod
    def run_full_pipeline(
        cls,
        ghidra_request: GhidraRequest,
        file_path: str,
    ) -> PipelineContext:
        """Run the full analysis pipeline for a binary.

        This method provides an end-to-end pipeline interface that combines
        Ghidra analysis with ML training or prediction.

        Args:
            ghidra_request: The Ghidra request containing analysis parameters.
            file_path: Path to the binary file.

        Returns:
            The pipeline context with analysis results.
        """
        from app.processing.steps import (
            ValidationStep,
            DecompileStep,
            TokenizeStep,
            FilterStep,
            FeatureExtractStep,
            TrainStep,
            PredictStep,
        )
        from app.processing.pipeline import ProcessingPipeline

        context = PipelineContext(
            uuid=ghidra_request.uuid,
            binary_path=file_path,
            pipeline_type="ml_training"
            if ghidra_request.is_training
            else "ml_prediction",
            metadata={
                "model_name": ghidra_request.model_name,
                "task_name": ghidra_request.task_name,
                "ml_class_type": ghidra_request.ml_class_type,
            },
        )

        if ghidra_request.is_training:
            pipeline = ProcessingPipeline(
                "ML Training Pipeline",
                [
                    ValidationStep(),
                    DecompileStep(),
                    TokenizeStep(),
                    FilterStep(),
                    FeatureExtractStep(),
                    TrainStep(),
                ],
            )
        else:
            pipeline = ProcessingPipeline(
                "ML Prediction Pipeline",
                [
                    ValidationStep(),
                    DecompileStep(),
                    TokenizeStep(),
                    FilterStep(),
                    FeatureExtractStep(),
                    PredictStep(),
                ],
            )
        return pipeline.execute(context)
