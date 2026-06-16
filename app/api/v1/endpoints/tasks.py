"""Task execution endpoints for Glyph API v1.

Provides endpoints for executing analysis tasks (code reuse detection,
ML training, ML prediction) on previously uploaded binaries.
"""

import asyncio
import contextvars
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.types import TaskType
from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.processing.task_management import TaskManager
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    restore_request_context,
    clear_request_context,
)
from app.utils.responses import (
    create_success_response,
    SuccessResponse,
)
from loguru import logger


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
# Background task handlers
# ---------------------------------------------------------------------------

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
    from app.processing.steps import TokenizeStep, FilterStep
    from app.processing.pipeline import ProcessingPipeline, PipelineContext
    from app.database.sql_service import SQLUtil
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
                comparisons.append(result)

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
        asyncio.get_event_loop().call_later(
            10, lambda: TaskManager.remove_task(task_uuid)
        )
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
    from app.processing.steps import (
        LoadBinaryFunctionsStep,
        TokenizeStep,
        FilterStep,
        FeatureExtractStep,
        TrainStep,
        PredictStep,
    )
    from app.processing.pipeline import ProcessingPipeline, PipelineContext
    from app.database.sql_service import SQLUtil

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
            pipeline = ProcessingPipeline(
                "ML Training Pipeline",
                [
                    LoadBinaryFunctionsStep(),
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
                    LoadBinaryFunctionsStep(),
                    TokenizeStep(),
                    FilterStep(),
                    FeatureExtractStep(),
                    PredictStep(),
                ],
            )

        result = await pipeline.execute(context)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error(
                "ML pipeline failed: {}", result.error
            )
        else:
            TaskManager.set_status(task_uuid, "completed")
            logger.info("ML {} pipeline completed for binary {}", task_type.value, binary_id)

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("ML task failed")
        raise
    finally:
        asyncio.get_event_loop().call_later(
            10, lambda: TaskManager.remove_task(task_uuid)
        )
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
    the appropriate pipeline (code reuse, ML training, or ML prediction)
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
        raise HTTPException(status_code=404, detail="Binary not found")

    if binary.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate task-specific parameters
    if request_values.task_type in (TaskType.ML_TRAINING, TaskType.ML_PREDICTION):
        if not request_values.model_name:
            raise HTTPException(
                status_code=400,
                detail="model_name is required for ML tasks",
            )
    if request_values.task_type == TaskType.ML_TRAINING:
        if not request_values.ml_class_type:
            raise HTTPException(
                status_code=400,
                detail="ml_class_type is required for ML training",
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


@router.get("/tasks/{task_uuid}/results")
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
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = TaskManager.get_task_result(task_uuid)
    if result is None and status == "completed":
        raise HTTPException(status_code=404, detail="Task results not available")

    return create_success_response(
        data={"task_uuid": task_uuid, "status": status, "result": result},
        message="Task results retrieved",
    )


@router.get("/tasks/{task_uuid}/status")
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
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return create_success_response(
        data={"task_uuid": task_uuid, "status": status},
        message="Task status retrieved",
    )
