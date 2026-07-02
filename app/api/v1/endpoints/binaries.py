"""Binary upload and analysis endpoints for Glyph API v1.

Provides endpoints for uploading binary files, initiating Ghidra analysis,
and managing the binary processing pipeline. Delegates business logic to
BinaryUploadService and BinaryAnalysisService.
"""

import asyncio
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.auth.dependencies import get_current_active_user
from app.database.function_repository import FunctionRepository
from app.database.models import User
from app.database.prediction_repository import PredictionRepository
from app.exceptions import BinaryAccessError, BinaryNotFoundError, ValidationError
from app.processing.task_management import Ghidra, TaskManager
from app.services.binary_upload_service import BinaryUploadService
from app.services.request_handler import GhidraRequest
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    clear_request_context,
    restore_request_context,
)
from app.utils.responses import (
    PaginatedResponse,
    SuccessResponse,
    create_error_response,
    create_paginated_response,
    create_success_response,
)


class BinaryUploadForm(BaseModel):
    """Form schema for binary upload requests.

    Attributes:
        name: Human-readable name for the binary.
    """

    name: str = Field(..., min_length=1, max_length=256)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str:
        """Strip whitespace from the name field.

        Args:
            v: Raw form value.

        Returns:
            Stripped string value.

        Raises:
            ValueError: If value is empty.
        """
        if v is None:
            raise ValueError("name is required")
        return v.strip()


class BinaryUploadResponse(BaseModel):
    """Response schema for binary upload.

    Attributes:
        binary_id: Database id of the uploaded binary.
        uuid: Unique identifier for the decompilation task.
    """

    binary_id: int = Field(...)
    uuid: str = Field(...)


class BinaryListItem(BaseModel):
    """Single binary entry for listing endpoints."""

    id: int
    name: str
    file_size: int
    mime_type: str
    function_count: int
    created_at: str


class BinaryListResponse(BaseModel):
    """Response schema for binary listing."""

    binaries: list[BinaryListItem]


class BinaryDetailResponse(BaseModel):
    """Response schema for binary detail."""

    id: int
    name: str
    file_size: int
    mime_type: str
    uploaded_by: int
    created_at: str
    modified_at: str
    function_count: int


router = APIRouter()

_upload_service = BinaryUploadService()

# Background task tracker to prevent garbage collection of fire-and-forget tasks
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _remove_task_delayed(task_uuid: str) -> None:
    """Remove a task from TaskManager after a delay.

    Args:
        task_uuid: The task UUID to remove.
    """
    await asyncio.sleep(10)
    TaskManager.remove_task(task_uuid)


async def _save_prediction_functions(prediction_request: Any, predictions: list[str]) -> None:
    """Merge predictions with functions and persist to database.

    Args:
        prediction_request: The prediction request containing functions.
        predictions: List of predicted labels.
    """
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


async def _run_upload_pipeline(
    binary_id: int,
    file_path: str,
    task_uuid: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the upload pipeline: decompile + save raw functions.

    Delegates to BinaryUploadService.run_upload_pipeline for the
    actual pipeline execution, wrapping it with TaskManager status
    updates and request context management.

    Args:
        binary_id: Database id of the uploaded binary.
        file_path: Path to the binary file on disk.
        task_uuid: Task UUID for progress tracking.
        captured_ctx: Captured request context for logging propagation.
    """
    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        result = await _upload_service.run_upload_pipeline(binary_id, file_path, task_uuid)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error("Upload pipeline failed: {}", result.error)
        else:
            functions_saved = result.get("functions_saved", 0)
            logger.info(
                "Upload pipeline completed: {} raw functions saved for binary {}",
                functions_saved,
                binary_id,
            )
            TaskManager.set_status(task_uuid, "completed")

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Upload pipeline task failed")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


async def _run_pipeline_analysis(
    ghidra_request: GhidraRequest,
    file_path: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the full analysis pipeline for a binary file.

    Legacy handler kept for backward compatibility with existing
    training / prediction workflows that still pass full GhidraRequest
    objects.

    Args:
        ghidra_request: The Ghidra analysis request containing metadata.
        file_path: Path to the binary file on disk.
        captured_ctx: Captured request context for logging propagation.
    """
    task_uuid = ghidra_request.uuid
    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")
        result = await Ghidra.run_full_pipeline(ghidra_request, file_path)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error("Pipeline execution failed: {}", result.error)
        else:
            logger.info("Pipeline execution completed")

            if ghidra_request.is_training:
                filtered_functions = result.get("filtered_functions")
                if filtered_functions:
                    from app.services.request_handler import TrainingRequest

                    training_data = {
                        "binaryName": ghidra_request.file_name,
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    training_request = TrainingRequest(
                        req_uuid=task_uuid,
                        model_name=ghidra_request.model_name,
                        data=training_data,
                    )
                    functions = training_request.get_functions() or []
                    if functions:
                        await FunctionRepository.save(ghidra_request.model_name, functions)
                    logger.debug("Functions saved for model {}", ghidra_request.model_name)
            else:
                predictions = result.get("predictions")
                filtered_functions = result.get("filtered_functions")
                logger.debug(
                    "Prediction results: {} predictions, {} functions, task '{}'",
                    len(predictions) if predictions else 0,
                    len(filtered_functions) if filtered_functions else 0,
                    ghidra_request.name,
                )
                if predictions and filtered_functions:
                    from app.services.request_handler import PredictionRequest

                    prediction_data = {
                        "binaryName": ghidra_request.file_name,
                        "taskName": ghidra_request.name,
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    try:
                        prediction_request = PredictionRequest(
                            req_uuid=task_uuid,
                            model_name=ghidra_request.model_name,
                            data=prediction_data,
                        )
                        await _save_prediction_functions(prediction_request, predictions)
                        logger.debug("Predictions saved for task {}", ghidra_request.name)
                    except Exception:
                        logger.exception("Failed to create PredictionRequest")
                        raise

            TaskManager.set_status(task_uuid, "completed")

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Pipeline task failed")
        raise
    finally:
        _create_background_task(_remove_task_delayed(task_uuid))
        clear_request_context()


@router.post("/uploadBinary", response_model=None)
async def post_upload_binary(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_file: UploadFile = File(...),
    name: str = Form(...),
) -> SuccessResponse[BinaryUploadResponse]:
    """Upload a binary and store raw decompiled functions.

    Delegates file validation, storage, and metadata persistence to
    BinaryUploadService, then queues a background decompilation task.
    """
    if not binary_file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="NO_FILE_FOUND",
                error_message="no file found",
            ).model_dump(),
        )

    try:
        binary_id, file_path = await _upload_service.upload_binary(
            file_stream=binary_file,
            name=name,
            user_id=current_user.id,
            filename=binary_file.filename,
        )
    except ValidationError as e:
        status_code = 413 if "exceeds" in e.message or "size" in e.message.lower() else 400
        raise HTTPException(
            status_code=status_code,
            detail=create_error_response(
                error_code="VALIDATION_ERROR",
                error_message=e.message,
            ).model_dump(),
        )

    task_uuid = str(uuid.uuid4())
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()
    background_tasks.add_task(_run_upload_pipeline, binary_id, file_path, task_uuid, captured_ctx)
    logger.info(
        "Binary uploaded, background task queued (uuid={})",
        task_uuid,
    )

    return create_success_response(
        data=BinaryUploadResponse(binary_id=binary_id, uuid=task_uuid),
        message="Binary uploaded successfully",
    )


@router.get("/list", response_model=SuccessResponse[PaginatedResponse[BinaryListItem]])
async def list_binaries(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> SuccessResponse[PaginatedResponse[BinaryListItem]]:
    """List binaries uploaded by the current user with pagination."""
    offset = (page - 1) * page_size
    binaries, total = await _upload_service.list_binaries(user_id=current_user.id, offset=offset, limit=page_size)

    items: list[BinaryListItem] = []
    for b in binaries:
        function_count = await _upload_service.get_function_count(b.id)
        items.append(
            BinaryListItem(
                id=b.id,
                name=b.name,
                file_size=b.file_size,
                mime_type=b.mime_type,
                function_count=function_count,
                created_at=b.created_at.isoformat(),
            )
        )

    return create_success_response(
        data=create_paginated_response(items, total, page, page_size),
        message="Binaries retrieved successfully",
    )


@router.get("/listBins", response_model=SuccessResponse[dict[str, Any]])
async def list_bins(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Legacy endpoint — lists uploaded binary files from disk.

    Only returns binaries belonging to the current user.
    Deprecated: use GET /list for database-backed binary listing.
    """
    import os

    binaries, _ = await _upload_service.list_binaries(user_id=current_user.id, offset=0, limit=1000)
    files = [os.path.basename(b.file_path) for b in binaries if os.path.exists(b.file_path)]
    return create_success_response(
        data={"files": files},
        message="Binaries retrieved successfully",
    )


@router.get("/binaries/{binary_id}", response_model=SuccessResponse[BinaryDetailResponse])
async def get_binary_detail(
    binary_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[BinaryDetailResponse]:
    """Get detailed metadata for a specific binary."""
    try:
        binary = await _upload_service.get_binary(binary_id, current_user.id)
    except BinaryNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="BINARY_NOT_FOUND", error_message="Binary not found").model_dump(),
        )
    except BinaryAccessError:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    function_count = await _upload_service.get_function_count(binary_id)

    detail = BinaryDetailResponse(
        id=binary.id,
        name=binary.name,
        file_size=binary.file_size,
        mime_type=binary.mime_type,
        uploaded_by=binary.uploaded_by,
        created_at=binary.created_at.isoformat(),
        modified_at=binary.modified_at.isoformat(),
        function_count=function_count,
    )

    return create_success_response(
        data=detail,
        message="Binary details retrieved successfully",
    )


class BinaryFunctionItem(BaseModel):
    """Single function entry for binary function listing."""

    function_name: str
    entrypoint: str
    raw_code_lines: int


class BinaryFunctionsResponse(BaseModel):
    """Response schema for binary function listing."""

    functions: list[BinaryFunctionItem]


class BulkUploadItem(BaseModel):
    """Individual result item for bulk binary upload."""

    binary_id: int | None = None
    uuid: str | None = None
    name: str
    status: Literal["success", "error"]
    error: str | None = None


class BinaryBulkUploadResponse(BaseModel):
    """Response schema for bulk binary upload."""

    results: list[BulkUploadItem]
    total: int
    successful: int
    failed: int


@router.get("/functions/{binary_id}", response_model=SuccessResponse[PaginatedResponse[BinaryFunctionItem]])
async def list_binary_functions(
    binary_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> SuccessResponse[PaginatedResponse[BinaryFunctionItem]]:
    """List decompiled functions for a specific binary with pagination."""
    try:
        await _upload_service.get_binary(binary_id, current_user.id)
    except BinaryNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="BINARY_NOT_FOUND", error_message="Binary not found").model_dump(),
        )
    except BinaryAccessError:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    total = await _upload_service.get_function_count(binary_id)
    offset = (page - 1) * page_size
    functions = await _upload_service.get_functions(binary_id, offset=offset, limit=page_size)

    items: list[BinaryFunctionItem] = []
    for fn in functions:
        line_count = fn.raw_code.count("\n") + 1 if fn.raw_code else 0
        items.append(
            BinaryFunctionItem(
                function_name=fn.function_name,
                entrypoint=fn.entrypoint,
                raw_code_lines=line_count,
            )
        )

    return create_success_response(
        data=create_paginated_response(items, total, page, page_size),
        message="Functions retrieved successfully",
    )


@router.delete("/binaries/{binary_id}", response_model=SuccessResponse[dict[str, str]])
async def delete_binary(
    binary_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, str]]:
    """Delete a binary and all its associated functions."""
    try:
        binary = await _upload_service.get_binary(binary_id, current_user.id)
        binary_name = binary.name
    except BinaryNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(error_code="BINARY_NOT_FOUND", error_message="Binary not found").model_dump(),
        )
    except BinaryAccessError:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(error_code="ACCESS_DENIED", error_message="Access denied").model_dump(),
        )

    await _upload_service.delete_binary(binary_id, current_user.id)

    return create_success_response(
        data={"message": f"Binary '{binary_name}' deleted successfully"},
        message="Binary deleted successfully",
    )


async def _upload_single_binary(
    binary_file: UploadFile,
    name: str,
    current_user: User,
    background_tasks: BackgroundTasks,
) -> BulkUploadItem:
    """Upload a single binary file and return the result.

    Delegates to BinaryUploadService.upload_binary for the actual
    file validation, storage, and metadata persistence.

    Args:
        binary_file: The binary file to upload.
        name: Human-readable name for the binary.
        current_user: The authenticated user uploading the file.
        background_tasks: FastAPI background tasks handler.

    Returns:
        BulkUploadItem with success or error status.
    """
    if not binary_file.filename:
        return BulkUploadItem(name=name, status="error", error="No filename provided")

    try:
        binary_id, file_path = await _upload_service.upload_binary(
            file_stream=binary_file,
            name=name,
            user_id=current_user.id,
            filename=binary_file.filename,
        )
    except ValidationError as e:
        return BulkUploadItem(name=name, status="error", error=e.message)

    task_uuid = str(uuid.uuid4())
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()
    background_tasks.add_task(_run_upload_pipeline, binary_id, file_path, task_uuid, captured_ctx)

    logger.info("Bulk upload: binary {} saved (id={}, uuid={})", name, binary_id, task_uuid)

    return BulkUploadItem(
        binary_id=binary_id,
        uuid=task_uuid,
        name=name,
        status="success",
    )


@router.post(
    "/uploadBulk",
    response_model=SuccessResponse[BinaryBulkUploadResponse],
    summary="Bulk upload binaries",
    description=(
        "Upload multiple binary files in a single request. Each file is "
        "processed independently and a background decompilation task is "
        "queued for each. Returns a summary with per-file status."
    ),
)
async def post_upload_bulk(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_active_user)],
    files: Annotated[
        list[UploadFile],
        File(..., description="Binary files to upload (up to 20)"),
    ],
    names: Annotated[
        str,
        Form(
            ...,
            description=(
                "Comma-separated names for each binary. Must match the number "
                "of files. If fewer names are provided, filenames are used."
            ),
        ),
    ],
) -> SuccessResponse[BinaryBulkUploadResponse]:
    """Upload multiple binaries and queue decompilation tasks for each."""
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="TOO_MANY_FILES",
                error_message="Maximum 20 files per bulk upload",
            ).model_dump(),
        )

    # Parse names
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    results: list[BulkUploadItem] = []

    for idx, file in enumerate(files):
        name = name_list[idx] if idx < len(name_list) else (file.filename or f"binary_{idx}")
        result = await _upload_single_binary(file, name, current_user, background_tasks)
        results.append(result)

    successful = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")

    return create_success_response(
        data=BinaryBulkUploadResponse(
            results=results,
            total=len(results),
            successful=successful,
            failed=failed,
        ),
        message=f"Bulk upload complete: {successful} succeeded, {failed} failed",
    )
