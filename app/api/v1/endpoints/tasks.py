"""Task execution endpoints for Glyph API v1.

Provides endpoints for executing analysis tasks (code reuse detection,
ML training, ML prediction) on previously uploaded binaries.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.api.types import TaskType
from app.api.v1.task_runners import (
    run_code_reuse_task,
    run_dangerous_functions_task,
    run_ml_task,
    run_similarity_computation_task,
)
from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.processing.task_management import TaskManager
from app.utils.request_context import capture_request_context
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
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/execute")
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
    from app.database.binary_repository import BinaryRepository

    # Validate binary exists and belongs to user
    binary = await BinaryRepository.get(request_values.binary_id)
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
                error_code="MISSING_MODEL_NAME", error_message="model_name is required for ML tasks",
            ).model_dump(),
        )
    if request_values.task_type == TaskType.ML_TRAINING and not request_values.ml_class_type:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="MISSING_ML_CLASS_TYPE", error_message="ml_class_type is required for ML training",
            ).model_dump(),
        )

    task_uuid = TaskManager().get_uuid()
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()

    if request_values.task_type == TaskType.CODE_REUSE:
        background_tasks.add_task(
            run_code_reuse_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_name,
            captured_ctx,
        )
    elif request_values.task_type == TaskType.DANGEROUS_FUNCTIONS:
        background_tasks.add_task(
            run_dangerous_functions_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_name,
            captured_ctx,
        )
    elif request_values.task_type == TaskType.SIMILARITY_COMPUTATION:
        background_tasks.add_task(
            run_similarity_computation_task,
            [request_values.binary_id],
            task_uuid,
            request_values.task_name,
            0.7,
            current_user.id,
            captured_ctx,
        )
    else:
        background_tasks.add_task(
            run_ml_task,
            request_values.binary_id,
            task_uuid,
            request_values.task_type,
            request_values.task_name,
            request_values.model_name or "",
            request_values.ml_class_type,
            captured_ctx,
            current_user.id,
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
                error_code="TASK_RESULTS_NOT_AVAILABLE", error_message="Task results not available",
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
    from app.database.binary_repository import BinaryRepository

    # Validate all binaries exist and belong to user
    for bid in request_values.binary_ids:
        binary = await BinaryRepository.get(bid)
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
        run_similarity_computation_task,
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
    from app.database.similarity_repository import SimilarityRepository

    computations = await SimilarityRepository.list_all(computed_by=current_user.id)

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
    from app.database.binary_repository import BinaryRepository
    from app.database.similarity_repository import SimilarityRepository

    computation = await SimilarityRepository.get(computation_id)
    if computation is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="COMPUTATION_NOT_FOUND", error_message="Computation not found",
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
        name_a = await BinaryRepository.get_name(pair.binary_a_id)
        name_b = await BinaryRepository.get_name(pair.binary_b_id)
        pair_responses.append(
            SimilarityPairResponse(
                binary_a_id=pair.binary_a_id,
                binary_a_name=name_a or f"binary_{pair.binary_a_id}",
                binary_b_id=pair.binary_b_id,
                binary_b_name=name_b or f"binary_{pair.binary_b_id}",
                overall_similarity=pair.overall_similarity,
                matched_function_count=pair.matched_function_count,
                total_function_comparisons=pair.total_function_comparisons,
            ),
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
    from app.database.similarity_repository import SimilarityRepository

    computation = await SimilarityRepository.get(computation_id)
    if computation is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="COMPUTATION_NOT_FOUND", error_message="Computation not found",
            ).model_dump(),
        )

    if computation.computed_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    await SimilarityRepository.delete(computation_id)

    return create_success_response(
        data={"id": str(computation_id)},
        message="Similarity computation deleted",
    )
