"""Binary upload and analysis endpoints for Glyph API v1.

Provides endpoints for uploading binary files, initiating Ghidra analysis,
and managing the binary processing pipeline. Handles file validation,
MIME type checking, and background task submission.
"""

import os
import shutil
import stat
import uuid
from pathlib import Path

import magic
from typing import Annotated, Any, Literal, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile)
from starlette.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from app.config.settings import get_settings
from app.services.request_handler import GhidraRequest
from app.processing.task_management import Ghidra, TaskManager
from app.utils.persistence_util import FunctionPersistanceUtil
from app.utils.responses import (
    create_success_response,
    create_error_response,
    create_paginated_response,
    PaginatedResponse,
    SuccessResponse)
from app.templates import templates
from loguru import logger
from app.utils.request_context import (
    CapturedContext,
    capture_request_context,
    restore_request_context,
    clear_request_context,
)
from app.auth.dependencies import get_current_active_user
from app.database.models import User


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

ALLOWED_MIME_TYPES: set[str] = {
    "application/x-executable",
    "application/x-object",
    "application/octet-stream",
    "application/x-elf",
    "application/x-dosexec",
    "application/x-sharedlib",
}


def validate_binary_mime_type(file_content: bytes) -> None:
    """Validate that uploaded file content is a recognized binary format.

    Args:
        file_content: Raw bytes from the uploaded file.

    Raises:
        HTTPException: If MIME type is not in the allowed set.
    """
    try:
        mime_type = magic.from_buffer(file_content[:1024], mime=True)
    except Exception:
        logger.exception("Failed to detect MIME type")
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="MIME_DETECTION_FAILED",
                error_message="Failed to analyze file type").model_dump())

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_FILE_TYPE",
                error_message=f"File type '{mime_type}' not allowed. Expected binary/ELF format").model_dump())


def sanitize_filename(filename: str) -> str:
    """Sanitize and validate the uploaded filename.

    Prevents path traversal and null byte injection attacks.

    Args:
        filename: Raw filename from the upload.

    Returns:
        Sanitized filename (basename only).

    Raises:
        HTTPException: If filename contains invalid characters.
    """
    if not filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="EMPTY_FILENAME",
                error_message="Empty filename").model_dump())

    if ".." in filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_FILENAME",
                error_message="Invalid filename characters").model_dump())

    if "\x00" in filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="INVALID_FILENAME",
                error_message="Invalid filename characters").model_dump())

    return Path(filename).name


async def _run_upload_pipeline(
    binary_id: int,
    file_path: str,
    task_uuid: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the upload pipeline: decompile + save raw functions.

    Runs Ghidra decompilation and saves raw function output to the
    BinaryFunction table. No ML processing is performed.

    Args:
        binary_id: Database id of the uploaded binary.
        file_path: Path to the binary file on disk.
        task_uuid: Task UUID for progress tracking.
        captured_ctx: Captured request context for logging propagation.
    """
    from app.processing.steps import ValidationStep, DecompileStep, SaveRawFunctionsStep
    from app.processing.pipeline import ProcessingPipeline, PipelineContext

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        context = PipelineContext(
            uuid=task_uuid,
            binary_path=file_path,
            pipeline_type="binary_upload",
            metadata={"binary_id": binary_id},
        )
        context.set("binary_id", binary_id)

        pipeline = ProcessingPipeline(
            "Binary Upload Pipeline",
            [
                ValidationStep(),
                DecompileStep(),
                SaveRawFunctionsStep(),
            ],
        )
        result = await pipeline.execute(context)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error(
                "Upload pipeline failed: {}", result.error
            )
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
        import asyncio

        asyncio.get_event_loop().call_later(
            10, lambda: TaskManager.remove_task(task_uuid)
        )
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
            logger.opt(exception=result.exc_info).error(
                "Pipeline execution failed: {}", result.error
            )
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
                    await FunctionPersistanceUtil.add_model_functions(training_request)
                    logger.debug(
                        "Functions saved for model {}", ghidra_request.model_name
                    )
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
                        await FunctionPersistanceUtil.add_prediction_functions(
                            prediction_request, predictions
                        )
                        logger.debug(
                            "Predictions saved for task {}", ghidra_request.name
                        )
                    except Exception:
                        logger.exception("Failed to create PredictionRequest")
                        raise

            TaskManager.set_status(task_uuid, "completed")

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Pipeline task failed")
        raise
    finally:
        import asyncio

        asyncio.get_event_loop().call_later(
            10, lambda: TaskManager.remove_task(task_uuid)
        )
        clear_request_context()


@router.post("/uploadBinary", response_model=None)
async def post_upload_binary(
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_file: UploadFile = File(...),
    name: str = Form(...),
) -> Union[SuccessResponse[BinaryUploadResponse], HTMLResponse]:
    """Upload a binary and store raw decompiled functions.

    The binary file is saved to disk, metadata is stored in the
    binaries database, and a background task runs Ghidra decompilation
    followed by saving raw functions. No ML processing occurs at upload
    time.

    Args:
        binary_file: The binary file to upload.
        name: Human-readable name for the binary.

    Returns:
        Binary id and task UUID for progress tracking.
    """
    form_data = BinaryUploadForm(name=name)

    accept = request.headers.get("Accept", "")

    if not binary_file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="NO_FILE_FOUND",
                error_message="no file found",
            ).model_dump(),
        )

    settings = get_settings()
    max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

    file_content = await binary_file.read()
    logger.info(
        "Binary upload started: {} ({} bytes)",
        binary_file.filename,
        len(file_content),
    )

    if len(file_content) > max_file_size_bytes:
        actual_size_mb = len(file_content) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=create_error_response(
                error_code="FILE_TOO_LARGE",
                error_message=f"File size ({actual_size_mb:.2f}MB) exceeds maximum allowed ({settings.max_file_size_mb}MB)",
            ).model_dump(),
        )

    mime_type = magic.from_buffer(file_content[:1024], mime=True)
    # Override MIME type for .bin files
    if binary_file.filename and binary_file.filename.lower().endswith(".bin"):
        mime_type = "application/x-sharedlib"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{mime_type}' not allowed. Expected binary/ELF format",
        )

    sanitize_filename(binary_file.filename)
    unique_filename = f"{uuid.uuid4()}"
    upload_folder = settings.upload_folder

    os.makedirs(upload_folder, exist_ok=True)
    os.chmod(upload_folder, stat.S_IRWXU)

    disk_usage = shutil.disk_usage(upload_folder)
    if disk_usage.free < len(file_content) * 1.1:
        raise HTTPException(
            status_code=507,
            detail=create_error_response(
                error_code="INSUFFICIENT_STORAGE",
                error_message="Insufficient disk space to complete upload",
            ).model_dump(),
        )

    file_path = os.path.join(upload_folder, unique_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

    # Save binary metadata to database
    from app.database.sql_service import SQLUtil

    binary_id = await SQLUtil.save_binary(
        name=form_data.name,
        file_path=file_path,
        file_size=len(file_content),
        mime_type=mime_type,
        uploaded_by=current_user.id,
    )

    task_uuid = str(uuid.uuid4())
    TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()
    background_tasks.add_task(
        _run_upload_pipeline, binary_id, file_path, task_uuid, captured_ctx
    )
    logger.info(
        "Binary uploaded to: {}, background task queued (uuid={}), returning response now",
        file_path,
        task_uuid,
    )

    if "text/html" in accept and "application/json" not in accept:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "user": current_user,
                "binary_id": binary_id,
                "task_uuid": task_uuid,
            },
        )

    result = create_success_response(
        data=BinaryUploadResponse(binary_id=binary_id, uuid=task_uuid),
        message="Binary uploaded successfully",
    )
    logger.info("Returning success response for upload {}", task_uuid)
    return result


@router.get("/list", response_model=SuccessResponse[PaginatedResponse[BinaryListItem]])
async def list_binaries(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
) -> SuccessResponse[PaginatedResponse[BinaryListItem]]:
    """List binaries uploaded by the current user with pagination."""
    from app.database.sql_service import SQLUtil

    total = await SQLUtil.count_binaries_by_user(current_user.id)
    offset = (page - 1) * page_size
    binaries = await SQLUtil.get_binaries_by_user(current_user.id, offset=offset, limit=page_size)

    items: list[BinaryListItem] = []
    for b in binaries:
        # Count functions
        function_count = await SQLUtil.count_binary_functions(b.id)
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

    Deprecated: use GET /list for database-backed binary listing.
    """
    files: list[str] = []
    settings = get_settings()
    directory_path = settings.upload_folder
    for _, _, files_found in os.walk(directory_path):
        if files_found:
            files.extend(files_found)
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
    from app.database.sql_service import SQLUtil

    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found").model_dump())

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied").model_dump())

    functions = await SQLUtil.get_binary_functions(binary_id)

    detail = BinaryDetailResponse(
        id=binary.id,
        name=binary.name,
        file_size=binary.file_size,
        mime_type=binary.mime_type,
        uploaded_by=binary.uploaded_by,
        created_at=binary.created_at.isoformat(),
        modified_at=binary.modified_at.isoformat(),
        function_count=len(functions),
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
    from app.database.sql_service import SQLUtil

    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found").model_dump())

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied").model_dump())

    total = await SQLUtil.count_binary_functions(binary_id)
    offset = (page - 1) * page_size
    functions = await SQLUtil.get_binary_functions(binary_id, offset=offset, limit=page_size)

    items: list[BinaryFunctionItem] = []
    for fn in functions:
        line_count = fn.raw_code.count('\n') + 1 if fn.raw_code else 0
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
    from app.database.sql_service import SQLUtil

    binary = await SQLUtil.get_binary(binary_id)
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code="BINARY_NOT_FOUND",
                error_message="Binary not found").model_dump())

    if binary.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code="ACCESS_DENIED",
                error_message="Access denied").model_dump())

    await SQLUtil.delete_binary(binary_id)

    return create_success_response(
        data={"message": f"Binary '{binary.name}' deleted successfully"},
        message="Binary deleted successfully",
    )


def _upload_single_binary(
    binary_file: UploadFile,
    name: str,
    current_user: User,
    background_tasks: BackgroundTasks,
) -> BulkUploadItem:
    """Upload a single binary file and return the result.

    Args:
        binary_file: The binary file to upload.
        name: Human-readable name for the binary.
        current_user: The authenticated user uploading the file.
        background_tasks: FastAPI background tasks handler.

    Returns:
        BulkUploadItem with success or error status.
    """
    settings = get_settings()
    max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

    try:
        form_data = BinaryUploadForm(name=name)

        if not binary_file.filename:
            return BulkUploadItem(name=name, status="error", error="No filename provided")

        file_content = binary_file.file.read()
        if len(file_content) > max_file_size_bytes:
            actual_size_mb = len(file_content) / (1024 * 1024)
            return BulkUploadItem(
                name=name,
                status="error",
                error=f"File size ({actual_size_mb:.2f}MB) exceeds maximum ({settings.max_file_size_mb}MB)",
            )

        mime_type = magic.from_buffer(file_content[:1024], mime=True)
        if mime_type not in ALLOWED_MIME_TYPES:
            return BulkUploadItem(
                name=name,
                status="error",
                error=f"File type '{mime_type}' not allowed",
            )

        unique_filename = f"{uuid.uuid4()}"
        upload_folder = settings.upload_folder
        os.makedirs(upload_folder, exist_ok=True)
        os.chmod(upload_folder, stat.S_IRWXU)

        file_path = os.path.join(upload_folder, unique_filename)

        with open(file_path, "wb") as f:
            f.write(file_content)
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

        from app.database.sql_service import SQLUtil

        binary_id = SQLUtil.save_binary(
            name=form_data.name,
            file_path=file_path,
            file_size=len(file_content),
            mime_type=mime_type,
            uploaded_by=current_user.id,
        )

        task_uuid = str(uuid.uuid4())
        TaskManager.register_task(task_uuid, "starting", owner_id=current_user.id)

        captured_ctx = capture_request_context()
        background_tasks.add_task(
            _run_upload_pipeline, binary_id, file_path, task_uuid, captured_ctx
        )

        logger.info("Bulk upload: binary {} saved (id={}, uuid={})", name, binary_id, task_uuid)

        return BulkUploadItem(
            binary_id=binary_id,
            uuid=task_uuid,
            name=name,
            status="success",
        )

    except Exception as e:
        logger.exception("Bulk upload failed for file: {}", name)
        return BulkUploadItem(name=name, status="error", error=str(e))


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
        result = _upload_single_binary(file, name, current_user, background_tasks)
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
