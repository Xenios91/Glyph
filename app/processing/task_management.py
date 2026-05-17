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
from loguru import logger
from app.utils.request_context import (
    CapturedContext,
    restore_request_context,
    clear_request_context,
)


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
        self._data_lock = threading.Lock()
        self._callbacks: dict[str, Callable[[Any, Any], None]] = {}
        self._watched_futures: dict[str, tuple[Any, Future[None], CapturedContext | None]] = {}
        self._watching: bool = False
        self._watch_thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None

    def register_callback(
        self,
        job_uuid: str,
        callback: Callable[[Any, Any], None],
        request: Any,
        future: Future[None],
        captured_ctx: CapturedContext | None = None,
    ) -> None:
        """Register a callback for a specific job UUID and track the future.

        Args:
            job_uuid: The UUID of the job to watch.
            callback: Callback function to invoke when job completes.
                      Receives (request, future) as arguments.
            request: The request object associated with this job.
            future: The Future object to monitor for completion.
            captured_ctx: Captured request context from the originating thread.
        """
        with self._data_lock:
            self._callbacks[job_uuid] = callback
            self._watched_futures[job_uuid] = (request, future, captured_ctx)
        logger.debug("Registered callback for job {}", job_uuid)

    def start_watching(self) -> None:
        """Start watching for completed futures in a background thread."""
        if self._watching:
            logger.warning("EventWatcher is already running")
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

        logger.info("Stopping EventWatcher")
        self._watching = False
        if self._stop_event is not None:
            self._stop_event.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None
        logger.info("EventWatcher stopped")

    @logger.catch(reraise=False, message="Error in EventWatcher loop")
    def _watch_loop(self) -> None:
        """Background loop that watches for completed futures."""

        logger.debug("EventWatcher watch loop started")
        assert self._stop_event is not None
        while self._watching and not self._stop_event.is_set():
            futures_only: list[Future[None]] = []
            with self._data_lock:
                if self._watched_futures:
                    futures_only = [
                        task[1] for task in self._watched_futures.values()
                    ]

            if not futures_only:
                time.sleep(2.5)
                continue

            done, _ = wait(futures_only, timeout=2.5, return_when=FIRST_COMPLETED)

            for future in done:
                with self._data_lock:
                    target_uuid: str | None = None
                    target_task: tuple[Any, Future[None], CapturedContext | None] | None = None
                    target_callback: Callable[[Any, Any], None] | None = None

                    for job_uuid, task in self._watched_futures.items():
                        if task[1] is future:
                            target_uuid = job_uuid
                            target_task = task
                            target_callback = self._callbacks.get(job_uuid)
                            break

                    if target_uuid is None or target_task is None:
                        continue

                if target_callback is not None:
                    request = target_task[0]
                    captured_ctx = target_task[2]
                    try:
                        if captured_ctx is not None:
                            restore_request_context(
                                captured_ctx, override_task_id=target_uuid)
                        target_callback(request, future)
                        logger.debug("Callback invoked for job {}", target_uuid)
                    except Exception:
                        logger.exception(
                            "Callback failed for job {}", target_uuid)
                    finally:
                        clear_request_context()

                with self._data_lock:
                    if (
                        self._watched_futures.get(target_uuid)
                        and self._watched_futures[target_uuid][1] is future
                    ):
                        del self._watched_futures[target_uuid]
                        logger.debug("Cleaned up job {}", target_uuid)
                    else:
                        logger.debug(
                            "Job {} re-registered by callback, keeping alive",
                            target_uuid)

            time.sleep(0.5)

        logger.info("EventWatcher watch loop stopped")


class TaskManager:
    """Base class for managing tasks in Glyph application."""

    exec_pool: ProcessPoolExecutor | None = None
    _executor_shutdown: bool = False
    __instance: "TaskManager | None" = None
    _active_tasks: dict[str, str] = {}
    _task_owners: dict[str, int] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize the process pool executor for subclasses."""
        super().__init_subclass__(**kwargs)
        if cls.exec_pool is None:
            cls.exec_pool = ProcessPoolExecutor(max_workers=MAX_CPU_CORES)
            atexit.register(cls._shutdown_executor)
            if threading.current_thread() is threading.main_thread():
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
            logger.info("ProcessPoolExecutor shut down")

    @classmethod
    def _signal_handler(cls, signum: int, _frame: Any) -> None:
        """Handle shutdown signals.

        Args:
            signum: The signal number received.
            _frame: The current stack frame (unused).
        """
        logger.info("Received signal {}, shutting down executor", signum)
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
    def register_task(
        cls,
        job_uuid: str,
        initial_status: str = "starting",
        owner_id: int | None = None,
    ) -> None:
        """Register a new task in the active tasks registry.

        Call this when a task is queued so that get_status() can find it
        even after it leaves the service queue.

        Args:
            job_uuid: The UUID of the job.
            initial_status: Initial status string (default "starting").
            owner_id: The user ID that owns this task (for access control).
        """
        cls._active_tasks[job_uuid] = initial_status
        if owner_id is not None:
            cls._task_owners[job_uuid] = owner_id
        logger.debug(
            "Registered task {} with status '{}' owner={}",
            job_uuid, initial_status, owner_id)

    @classmethod
    def get_status(cls, job_uuid: str) -> str:
        """Get the status of a job by its UUID.

        Checks the active tasks registry first, then falls back to the
        service queue for backwards compatibility.

        Args:
            job_uuid: The UUID of the job.

        Returns:
            The status of the job or "UUID Not Found".
        """
        if job_uuid in cls._active_tasks:
            return cls._active_tasks[job_uuid]

        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                status: str = task[0].status
                cls._active_tasks[job_uuid] = status
                return status
        return "UUID Not Found"

    @classmethod
    def get_all_status(cls) -> dict[str, str]:
        """Get the status of all jobs.

        Returns statuses from both the active tasks registry and the
        service queue.  For backwards compatibility, queue entries are
        keyed by model_name while registry entries are keyed by UUID.

        Returns:
            A dictionary mapping model names / UUIDs to their statuses.
        """
        status_list: dict[str, str] = dict(cls._active_tasks)

        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            status: str = task[0].status
            model_name: str = task[0].model_name
            status_list[model_name] = status
        return status_list

    @classmethod
    def verify_task_owner(cls, job_uuid: str, user_id: int) -> bool:
        """Verify that the given user owns the specified task.

        Args:
            job_uuid: The UUID of the job.
            user_id: The user ID to check ownership for.

        Returns:
            True if the user owns the task or no owner is registered,
            False otherwise.
        """
        owner = cls._task_owners.get(job_uuid)
        if owner is None:
            return True
        return owner == user_id

    @classmethod
    def set_status(cls, job_uuid: str, status: str, owner_id: int | None = None) -> bool:
        """Set the status of a job by its UUID.

        Updates both the active tasks registry and the service queue
        entry (if still queued).

        Args:
            job_uuid: The UUID of the job.
            status: The new status to set.
            owner_id: Optional user ID to verify ownership before updating.

        Returns:
            True if the status was set, False if the UUID was not found
            or ownership verification failed.
        """
        if owner_id is not None and not cls.verify_task_owner(job_uuid, owner_id):
            logger.warning(
                "Ownership check failed for task {} by user {}", job_uuid, owner_id)
            return False

        if job_uuid in cls._active_tasks:
            cls._active_tasks[job_uuid] = status
            logger.debug("Updated task {} status to '{}'", job_uuid, status)
            return True

        queue_list: list[tuple[Any, Any]] = list(TaskService().service_queue.queue)
        for task in queue_list:
            queued_uuid: str = task[0].uuid
            if job_uuid == queued_uuid:
                task[0].status = status
                cls._active_tasks[job_uuid] = status
                return True
        return False

    @classmethod
    def remove_task(cls, job_uuid: str) -> None:
        """Remove a completed or failed task from the active registry.

        Args:
            job_uuid: The UUID of the job to remove.
        """
        if job_uuid in cls._active_tasks:
            del cls._active_tasks[job_uuid]
        cls._task_owners.pop(job_uuid, None)
        logger.debug("Removed task {} from active registry", job_uuid)


class Ghidra(TaskManager):
    """Task manager for running Ghidra analysis on binaries.

    This class integrates with the pipeline framework to provide
    end-to-end binary analysis workflows.
    """

    @classmethod
    async def run_full_pipeline(
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
            PredictStep)
        from app.processing.pipeline import ProcessingPipeline

        context = PipelineContext(
            uuid=ghidra_request.uuid,
            binary_path=file_path,
            pipeline_type="ml_training"
            if ghidra_request.is_training
            else "ml_prediction",
            metadata={
                "model_name": ghidra_request.model_name,
                "name": ghidra_request.name,
                "ml_class_type": ghidra_request.ml_class_type,
            })

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
                ])
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
                ])
        return await pipeline.execute(context)
