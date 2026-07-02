"""Task execution endpoints for Glyph API v1.

Provides endpoints for executing analysis tasks (code reuse detection,
ML training, ML prediction) on previously uploaded binaries.
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.api.types import TaskType
from app.auth.dependencies import get_current_active_user
from app.database.models import SimilarityPair, User
from app.processing.task_management import TaskManager
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    clear_request_context,
    restore_request_context,
)
from app.utils.responses import (
    SuccessResponse,
    create_error_response,
    create_success_response,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TaskExecutionRequest(BaseModel):
    """Request schema for executing an analysis task on a binary.

    Attributes:
        binary_id: Database id of the binary to analyze.
        task_type: Type of analysis task to perform.
        task_name: Human-readable name for this task execution.
        model_name: Required for ml_training and ml_prediction tasks.
        ml_class_type: Required for ml_training tasks.
    """

    binary_id: int = Field(..., gt=0)
    task_type: TaskType
    task_name: str = Field(..., min_length=1, max_length=128)
    model_name: str | None = None
    ml_class_type: str | None = None


class TaskExecutionResponse(BaseModel):
    """Response schema for task execution."""

    task_uuid: str
    task_type: str
    binary_id: int
    status: str


class CodeReuseMatch(BaseModel):
    """Single function match in code reuse results."""

    source_function_name: str
    target_function_name: str
    similarity_score: float
    source_tokens: str
    target_tokens: str


class CodeReuseComparison(BaseModel):
    """Comparison result against a single target binary."""

    target_binary_id: int
    target_binary_name: str
    matched_functions: list[CodeReuseMatch]
    overall_similarity: float


class CodeReuseResults(BaseModel):
    """Full code reuse detection results."""

    task_uuid: str
    source_binary_id: int
    source_binary_name: str
    comparisons: list[CodeReuseComparison]


# ---------------------------------------------------------------------------
# Similarity computation schemas
# ---------------------------------------------------------------------------


class SimilarityComputationRequest(BaseModel):
    """Request schema for starting a similarity computation."""

    task_name: str = Field(..., min_length=1, max_length=128)
    binary_ids: list[int] = Field(..., min_length=2, description="Binaries to compare")
    match_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class SimilarityPairResponse(BaseModel):
    """Single pairwise similarity result."""

    binary_a_id: int
    binary_a_name: str
    binary_b_id: int
    binary_b_name: str
    overall_similarity: float
    matched_function_count: int
    total_function_comparisons: int


class SimilarityMatrixResponse(BaseModel):
    """Response schema for similarity matrix data."""

    computation_id: int
    task_name: str
    binary_count: int
    total_comparisons: int
    status: str
    matrix: list[SimilarityPairResponse]


class SimilarityComputationListResponse(BaseModel):
    """Response schema for listing similarity computations."""

    computations: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Background task handlers
# ---------------------------------------------------------------------------


# Background task tracker to prevent garbage collection of fire-and-forget tasks
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _remove_task_delayed(task_uuid: str) -> None:
    """Remove a task from TaskManager after a delay.

    Args:
        task_uuid: The task UUID to remove.
    """
    await asyncio.sleep(10)
    TaskManager.remove_task(task_uuid)


async def _save_prediction_functions_tasks(prediction_request: Any, predictions: list[str]) -> None:
    """Merge predictions with functions and persist to database."""
    from app.database.prediction_repository import PredictionRepository

    functions: list[dict[str, Any]] = prediction_request.get_functions() or []
    task_name = prediction_request.task_name

    if functions and len(functions) == len(predictions):
        for ctr, function in enumerate(functions):
            updated_function = function.copy()
            updated_function["prediction"] = predictions[ctr]
            functions[ctr] = updated_function
        await PredictionRepository.save(task_name, prediction_request.model_name, functions)
    elif functions:
        logger.warning(
            "Mismatch between functions (%d) and predictions (%d) for task '%s'",
            len(functions),
            len(predictions),
            task_name,
        )


def _create_background_task(coro: Any) -> asyncio.Task[None]:
    """Create a background task that won't be garbage-collected.

    Args:
        coro: The coroutine to run in the background.

    Returns:
        The created asyncio.Task.
    """
    task: asyncio.Task[None] = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _run_code_reuse_task(
    binary_id: int,
    task_uuid: str,
    task_name: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute code reuse detection pipeline.

    Loads raw functions from the source binary, applies in-memory
    tokenization and filtering, then compares against all other
    binaries in the database.

    Args:
        binary_id: Source binary id.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        captured_ctx: Captured request context.
    """
    from app.database.sql_service import SQLUtil
    from app.processing.pipeline import PipelineContext
    from app.processing.steps import FilterStep, TokenizeStep
    from app.services.code_reuse_detector import compare_binaries

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Load source binary functions
        source_functions = await SQLUtil.get_binary_functions(binary_id)
        if not source_functions:
            TaskManager.set_status(task_uuid, "error")
            logger.error("No functions found for source binary {}", binary_id)
            return

        source_name = await SQLUtil.get_binary_name(binary_id)

        # Tokenize and filter source functions in-memory
        source_context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type="code_reuse",
            metadata={"binary_id": binary_id, "task_name": task_name},
        )

        source_dicts = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in source_functions
        ]
        source_context.set("functions", source_dicts)

        tokenize_step = TokenizeStep()
        source_context = await tokenize_step.execute(source_context)
        if source_context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Tokenization failed: {}", source_context.error)
            return

        filter_step = FilterStep()
        source_context = await filter_step.execute(source_context)
        if source_context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Filtering failed: {}", source_context.error)
            return

        filtered_source = source_context.get("filtered_functions", [])

        # Get all other binaries to compare against
        all_binary_ids = await SQLUtil.get_all_binary_ids()
        target_ids = [bid for bid in all_binary_ids if bid != binary_id]

        if not target_ids:
            logger.info("No other binaries to compare against for binary {}", binary_id)
            TaskManager.set_status(task_uuid, "completed")
            # Store empty results
            TaskManager.set_task_result(
                task_uuid,
                {
                    "task_uuid": task_uuid,
                    "source_binary_id": binary_id,
                    "source_binary_name": source_name,
                    "comparisons": [],
                },
            )
            return

        # Compare against each target binary
        comparisons: list[dict[str, Any]] = []
        for target_id in target_ids:
            result = await compare_binaries(filtered_source, target_id)
            if result:
                comparisons.append(result)  # type: ignore[arg-type]

        TaskManager.set_status(task_uuid, "completed")

        results = {
            "task_uuid": task_uuid,
            "source_binary_id": binary_id,
            "source_binary_name": source_name,
            "comparisons": comparisons,
        }
        TaskManager.set_task_result(task_uuid, results)

        logger.info(
            "Code reuse detection completed: {} comparisons for binary {}",
            len(comparisons),
            binary_id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Code reuse task failed")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


async def _run_dangerous_functions_task(
    binary_id: int,
    task_uuid: str,
    task_name: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute dangerous function scanning pipeline.

    Loads raw functions from the binary, applies in-memory tokenization
    and filtering, then scans against the dangerous function catalog.

    Args:
        binary_id: Binary id to scan.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        captured_ctx: Captured request context.
    """
    from app.database.sql_service import SQLUtil
    from app.processing.pipeline import PipelineContext
    from app.processing.steps import FilterStep, TokenizeStep
    from app.services.dangerous_function_scanner import generate_report

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Load binary functions
        binary_functions = await SQLUtil.get_binary_functions(binary_id)
        if not binary_functions:
            TaskManager.set_status(task_uuid, "error")
            logger.error("No functions found for binary {}", binary_id)
            return

        binary_name = await SQLUtil.get_binary_name(binary_id)

        # Build function dicts for pipeline processing
        function_dicts = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in binary_functions
        ]

        # Run tokenize and filter steps
        context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type="dangerous_functions",
            metadata={"binary_id": binary_id, "task_name": task_name},
        )
        context.set("functions", function_dicts)

        tokenize_step = TokenizeStep()
        context = await tokenize_step.execute(context)
        if context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Tokenization failed: {}", context.error)
            return

        filter_step = FilterStep()
        context = await filter_step.execute(context)
        if context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Filtering failed: {}", context.error)
            return

        filtered_functions = context.get("filtered_functions", [])

        # Scan for dangerous functions
        report = generate_report(binary_name or f"binary_{binary_id}", filtered_functions)

        TaskManager.set_status(task_uuid, "completed")

        # Store results
        result = {
            "task_uuid": task_uuid,
            "binary_id": binary_id,
            "binary_name": binary_name,
            "model_name": binary_name or f"binary_{binary_id}",
            "total_functions_scanned": report.total_functions_scanned,
            "total_found": report.total_found,
            "critical_count": report.critical_count,
            "high_count": report.high_count,
            "medium_count": report.medium_count,
            "low_count": report.low_count,
            "results": [
                {
                    "function_name": r.function_name,
                    "containing_function": r.containing_function,
                    "entrypoint": r.entrypoint,
                    "category": r.category,
                    "severity": r.severity,
                    "cwe": r.cwe,
                    "description": r.description,
                    "safe_alternative": r.safe_alternative,
                    "usage_context": r.usage_context,
                    "containing_function_code": r.containing_function_code,
                }
                for r in report.results
            ],
        }
        TaskManager.set_task_result(task_uuid, result)

        logger.info(
            "Dangerous function scan completed: {} dangerous functions found in binary {}",
            report.total_found,
            binary_id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Dangerous function scan task failed")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


async def _run_ml_task(
    binary_id: int,
    task_uuid: str,
    task_type: TaskType,
    task_name: str,
    model_name: str,
    ml_class_type: str | None = None,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute ML training or prediction pipeline.

    Loads raw functions from the binary, applies in-memory processing,
    and trains or predicts using the specified model.

    Args:
        binary_id: Binary id to analyze.
        task_uuid: Task UUID for progress tracking.
        task_type: ml_training or ml_prediction.
        task_name: Human-readable task name.
        model_name: ML model name.
        ml_class_type: Classification type (for training).
        captured_ctx: Captured request context.
    """
    from app.processing.pipeline import PipelineContext

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        pipeline_type = "ml_training" if task_type == TaskType.ML_TRAINING else "ml_prediction"

        context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type=pipeline_type,
            metadata={
                "binary_id": binary_id,
                "model_name": model_name,
                "task_name": task_name,
                "ml_class_type": ml_class_type,
            },
        )
        context.set("binary_id", binary_id)

        if task_type == TaskType.ML_TRAINING:
            from app.processing.pipeline_configs import TRAINING_FROM_DB_PIPELINE

            pipeline = TRAINING_FROM_DB_PIPELINE
        else:
            from app.processing.pipeline_configs import PREDICTION_FROM_DB_PIPELINE

            pipeline = PREDICTION_FROM_DB_PIPELINE

        result = await pipeline.execute(context)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error("ML pipeline failed: {}", result.error)
        else:
            # Persist results to the database
            filtered_functions = result.get("filtered_functions")
            if task_type == TaskType.ML_TRAINING:
                if filtered_functions:
                    from app.database.function_repository import FunctionRepository
                    from app.services.request_handler import TrainingRequest

                    training_data = {
                        "binaryName": f"binary_{binary_id}",
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    try:
                        training_request = TrainingRequest(
                            req_uuid=task_uuid,
                            model_name=model_name,
                            data=training_data,
                        )
                        functions = training_request.get_functions() or []
                        if functions:
                            await FunctionRepository.save(model_name, functions)
                        logger.info(
                            "Functions saved for model '{}' ({} functions)",
                            model_name,
                            len(filtered_functions),
                        )
                    except Exception:
                        logger.exception("Failed to save functions for model '{}'", model_name)
                        raise
            elif task_type == TaskType.ML_PREDICTION:
                predictions = result.get("predictions")
                if predictions and filtered_functions:
                    from app.database.prediction_repository import PredictionRepository
                    from app.services.request_handler import PredictionRequest

                    prediction_data = {
                        "binaryName": f"binary_{binary_id}",
                        "taskName": task_name,
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    try:
                        prediction_request = PredictionRequest(
                            req_uuid=task_uuid,
                            model_name=model_name,
                            data=prediction_data,
                        )
                        await _save_prediction_functions_tasks(prediction_request, predictions)
                        logger.info(
                            "Predictions saved for task '{}' ({} predictions)",
                            task_name,
                            len(predictions),
                        )
                    except Exception:
                        logger.exception("Failed to save predictions for task '{}'", task_name)
                        raise

            TaskManager.set_status(task_uuid, "completed")
            logger.info("ML {} pipeline completed for binary {}", task_type.value, binary_id)

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("ML task failed")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


async def _run_similarity_computation_task(
    binary_ids: list[int],
    task_uuid: str,
    task_name: str,
    match_threshold: float,
    user_id: int,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute similarity matrix computation across a set of binaries.

    Computes pairwise similarity for all unique binary pairs using the
    existing compute_similarity() method with in-memory tokenization
    and filtering. Results are persisted to the intelligence database.

    Args:
        binary_ids: List of binary IDs to compare.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        match_threshold: Minimum similarity score to count a match.
        user_id: ID of the user who initiated the computation.
        captured_ctx: Captured request context.
    """
    from app.database.sql_service import SQLUtil
    from app.services.binary_similarity_service import BinarySimilarityService

    computation: Any | None = None
    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Create the computation record
        computation = await SQLUtil.create_similarity_computation(
            task_name=task_name,
            computed_by=user_id,
            binary_count=len(binary_ids),
        )

        # Compute the similarity matrix
        entries = await BinarySimilarityService.compute_similarity_matrix(
            binary_ids=binary_ids,
            match_threshold=match_threshold,
        )

        # Persist pair results
        pairs = [
            SimilarityPair(
                binary_a_id=entry.binary_a_id,
                binary_b_id=entry.binary_b_id,
                overall_similarity=entry.overall_similarity,
                matched_function_count=entry.matched_function_count,
                total_function_comparisons=entry.total_function_comparisons,
            )
            for entry in entries
        ]
        await SQLUtil.save_similarity_pairs(
            computation_id=computation.id,
            pairs=pairs,
        )

        # Mark computation completed
        await SQLUtil.update_similarity_computation_status(
            computation_id=computation.id,
            status="completed",
            total_comparisons=len(entries),
        )

        TaskManager.set_status(task_uuid, "completed")

        # Store lightweight result reference
        result = {
            "task_uuid": task_uuid,
            "computation_id": computation.id,
            "binary_count": len(binary_ids),
            "pairs_computed": len(entries),
        }
        TaskManager.set_task_result(task_uuid, result)

        logger.info(
            "Similarity computation completed: {} pairs from {} binaries (computation_id={})",
            len(entries),
            len(binary_ids),
            computation.id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Similarity computation task failed")
        # Mark computation as errored if it was created
        if computation is not None:
            try:
                await SQLUtil.update_similarity_computation_status(
                    computation_id=computation.id,
                    status="error",
                )
            except Exception:
                logger.exception("Failed to persist error state for similarity computation")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/execute", response_model=SuccessResponse[TaskExecutionResponse])
async def execute_task(
    background_tasks: BackgroundTasks,
    request_values: TaskExecutionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[TaskExecutionResponse]:
    """Execute an analysis task on a previously uploaded binary.

    Validates the binary exists and belongs to the user, then queues
    the appropriate pipeline (code reuse, dangerous functions, ML training, or ML prediction)
    as a background task.

    Args:
        request_values: Task execution parameters.

    Returns:
        Task UUID and status for progress tracking.
    """
    from app.database.sql_service import SQLUtil

    # Validate binary exists and belongs to user
    binary = await SQLUtil.get_binary(request_values.binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="BINARY_NOT_FOUND", error_message="Binary not found").model_dump(),
        )

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    # Validate task-specific parameters
    if request_values.task_type in (TaskType.ML_TRAINING, TaskType.ML_PREDICTION) and not request_values.model_name:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="MISSING_MODEL_NAME", error_message="model_name is required for ML tasks"
            ).model_dump(),
        )
    if request_values.task_type == TaskType.ML_TRAINING and not request_values.ml_class_type:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="MISSING_ML_CLASS_TYPE", error_message="ml_class_type is required for ML training"
            ).model_dump(),
        )

    task_uuid = TaskManager().get_uuid()
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()

    if request_values.task_type == TaskType.CODE_REUSE:
        background_tasks.add_task(
            _run_code_reuse_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_name,
            captured_ctx,
        )
    elif request_values.task_type == TaskType.DANGEROUS_FUNCTIONS:
        background_tasks.add_task(
            _run_dangerous_functions_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_name,
            captured_ctx,
        )
    elif request_values.task_type == TaskType.SIMILARITY_COMPUTATION:
        background_tasks.add_task(
            _run_similarity_computation_task,
            [request_values.binary_id],
            task_uuid,
            request_values.task_name,
            0.7,
            current_user.id,
            captured_ctx,
        )
    else:
        background_tasks.add_task(
            _run_ml_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_type,
            request_values.task_name,
            request_values.model_name or "",
            request_values.ml_class_type,
            captured_ctx,
        )

    logger.info(
        "Task {} queued for binary {} (uuid={})",
        request_values.task_type.value,
        request_values.binary_id,
        task_uuid,
    )

    return create_success_response(
        data=TaskExecutionResponse(
            task_uuid=task_uuid,
            task_type=request_values.task_type.value,
            binary_id=request_values.binary_id,
            status="starting",
        ),
        message=f"Task {request_values.task_type.value} queued successfully",
    )


@router.get("/{task_uuid}/results")
async def get_task_results(
    task_uuid: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Retrieve results for a completed task.

    Args:
        task_uuid: The task UUID from the execution response.

    Returns:
        Task results (structure depends on task type).
    """
    status = TaskManager.get_status(task_uuid)
    if status == "UUID Not Found":
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="TASK_NOT_FOUND", error_message="Task not found").model_dump(),
        )

    if not TaskManager.verify_task_owner(task_uuid, current_user.id):
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    result = TaskManager.get_task_result(task_uuid)
    if result is None and status == "completed":
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="TASK_RESULTS_NOT_AVAILABLE", error_message="Task results not available"
            ).model_dump(),
        )

    return create_success_response(
        data={"task_uuid": task_uuid, "status": status, "result": result},
        message="Task results retrieved",
    )


@router.get("/{task_uuid}/status")
async def get_task_status(
    task_uuid: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, str]]:
    """Check the current status of a task.

    Args:
        task_uuid: The task UUID.

    Returns:
        Current task status string.
    """
    status = TaskManager.get_status(task_uuid)
    if status == "UUID Not Found":
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="TASK_NOT_FOUND", error_message="Task not found").model_dump(),
        )

    if not TaskManager.verify_task_owner(task_uuid, current_user.id):
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    return create_success_response(
        data={"task_uuid": task_uuid, "status": status},
        message="Task status retrieved",
    )


# ---------------------------------------------------------------------------
# Similarity computation endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/similarity-computation",
    response_model=SuccessResponse[TaskExecutionResponse],
)
async def start_similarity_computation(
    background_tasks: BackgroundTasks,
    request_values: SimilarityComputationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[TaskExecutionResponse]:
    """Start a new similarity computation across a set of binaries.

    Validates that all binary IDs belong to the user, then queues
    the similarity matrix computation as a background task.

    Args:
        request_values: Similarity computation parameters.

    Returns:
        Task UUID and status for progress tracking.
    """
    from app.database.sql_service import SQLUtil

    # Validate all binaries exist and belong to user
    for bid in request_values.binary_ids:
        binary = await SQLUtil.get_binary(bid)
        if binary is None:
            raise HTTPException(status_code=404, detail=f"Binary {bid} not found")
        if binary.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=403,
                detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
            )

    task_uuid = TaskManager().get_uuid()
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()

    background_tasks.add_task(
        _run_similarity_computation_task,
        request_values.binary_ids,
        task_uuid,
        request_values.task_name,
        request_values.match_threshold,
        current_user.id,
        captured_ctx,
    )

    logger.info(
        "Similarity computation queued for {} binaries (uuid={})",
        len(request_values.binary_ids),
        task_uuid,
    )

    return create_success_response(
        data=TaskExecutionResponse(
            task_uuid=task_uuid,
            task_type=TaskType.SIMILARITY_COMPUTATION.value,
            binary_id=request_values.binary_ids[0],
            status="starting",
        ),
        message="Similarity computation queued successfully",
    )


@router.get("/similarity-computations")
async def list_similarity_computations(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[list[dict[str, Any]]]:
    """List all saved similarity computations for the current user.

    Returns:
        List of computation metadata records ordered by creation date.
    """
    from app.database.sql_service import SQLUtil

    computations = await SQLUtil.list_similarity_computations(computed_by=current_user.id)

    result = [
        {
            "id": c.id,
            "task_name": c.task_name,
            "binary_count": c.binary_count,
            "total_comparisons": c.total_comparisons,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in computations
    ]

    return create_success_response(
        data=result,
        message="Similarity computations retrieved",
    )


@router.get("/similarity-computations/{computation_id}")
async def get_similarity_computation(
    computation_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[SimilarityMatrixResponse]:
    """Get a specific similarity computation and its pairwise results.

    Args:
        computation_id: Database ID of the computation.

    Returns:
        Computation metadata with full similarity matrix.
    """
    from app.database.sql_service import SQLUtil

    computation = await SQLUtil.get_similarity_computation(computation_id)
    if computation is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="COMPUTATION_NOT_FOUND", error_message="Computation not found"
            ).model_dump(),
        )

    if computation.computed_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    # Build pair responses with binary names
    pair_responses: list[SimilarityPairResponse] = []
    for pair in computation.pairs:
        name_a = await SQLUtil.get_binary_name(pair.binary_a_id)
        name_b = await SQLUtil.get_binary_name(pair.binary_b_id)
        pair_responses.append(
            SimilarityPairResponse(
                binary_a_id=pair.binary_a_id,
                binary_a_name=name_a or f"binary_{pair.binary_a_id}",
                binary_b_id=pair.binary_b_id,
                binary_b_name=name_b or f"binary_{pair.binary_b_id}",
                overall_similarity=pair.overall_similarity,
                matched_function_count=pair.matched_function_count,
                total_function_comparisons=pair.total_function_comparisons,
            )
        )

    response = SimilarityMatrixResponse(
        computation_id=computation.id,
        task_name=computation.task_name,
        binary_count=computation.binary_count,
        total_comparisons=computation.total_comparisons,
        status=computation.status,
        matrix=pair_responses,
    )

    return create_success_response(
        data=response,
        message="Similarity computation retrieved",
    )


@router.delete("/similarity-computations/{computation_id}")
async def delete_similarity_computation(
    computation_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, str]]:
    """Delete a saved similarity computation and its pairwise results.

    Args:
        computation_id: Database ID of the computation.

    Returns:
        Confirmation message.
    """
    from app.database.sql_service import SQLUtil

    computation = await SQLUtil.get_similarity_computation(computation_id)
    if computation is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="COMPUTATION_NOT_FOUND", error_message="Computation not found"
            ).model_dump(),
        )

    if computation.computed_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    await SQLUtil.delete_similarity_computation(computation_id)

    return create_success_response(
        data={"id": str(computation_id)},
        message="Similarity computation deleted",
    )
