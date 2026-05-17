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
from typing import Annotated, Any, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
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
        training_data: Whether the binary is for training ("true" or "false").
        model_name: Name of the ML model to associate with this binary.
        ml_class_type: Machine learning classification type.
        name: Human-readable name for this binary analysis task.
    """

    training_data: str = Field(default="false")
    model_name: str = Field(..., min_length=1)
    ml_class_type: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)

    @field_validator("training_data", mode="before")
    @classmethod
    def validate_training_data(cls, v: str | None) -> str:
        """Normalize training_data to 'true' or 'false'.

        Args:
            v: Raw form value.

        Returns:
            Normalized boolean string.

        Raises:
            ValueError: If value is not 'true' or 'false'.
        """
        if v is None:
            return "false"
        v_lower = v.lower().strip()
        if v_lower not in ("true", "false"):
            raise ValueError("training_data must be 'true' or 'false'")
        return v_lower

    @field_validator("model_name", "ml_class_type", "name", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str:
        """Strip whitespace from string fields.

        Args:
            v: Raw form value.

        Returns:
            Stripped string value.

        Raises:
            ValueError: If value is empty.
        """
        if v is None:
            raise ValueError("Field cannot be empty")
        return v.strip()


class BinaryUploadResponse(BaseModel):
    """Response schema for binary upload.

    Attributes:
        uuid: Unique identifier for the submitted analysis task.
    """

    uuid: str = Field(...)


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
        raise HTTPException(status_code=400, detail="Failed to analyze file type")

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{mime_type}' not allowed. Expected binary/ELF format")


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
        raise HTTPException(status_code=400, detail="Empty filename")

    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename characters")

    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename characters")

    return Path(filename).name


async def _run_pipeline_analysis(
    ghidra_request: GhidraRequest,
    file_path: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute the full analysis pipeline for a binary file.

    Runs Ghidra decompilation, tokenization, filtering, and optionally
    training or prediction depending on the request type. Results are
    persisted to the database.

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
                "Pipeline execution failed: {}", result.error)
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
                        data=training_data)
                    await FunctionPersistanceUtil.add_model_functions(training_request)
                    logger.debug("Functions saved for model {}", ghidra_request.model_name)
            else:
                predictions = result.get("predictions")
                filtered_functions = result.get("filtered_functions")
                logger.debug(
                    "Prediction results: {} predictions, {} functions, task '{}'",
                    len(predictions) if predictions else 0,
                    len(filtered_functions) if filtered_functions else 0,
                    ghidra_request.name)
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
                            data=prediction_data)
                        await FunctionPersistanceUtil.add_prediction_functions(
                            prediction_request, predictions
                        )
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
        import asyncio
        asyncio.get_event_loop().call_later(10, lambda: TaskManager.remove_task(task_uuid))
        clear_request_context()


@router.post("/uploadBinary", response_model=None)
async def post_upload_binary(
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    binary_file: UploadFile = File(...),
    training_data: str = Form("false"),
    model_name: str = Form(...),
    ml_class_type: str = Form(...),
    name: str = Form(...)
) -> Union[SuccessResponse[BinaryUploadResponse], HTMLResponse]:
    form_data = BinaryUploadForm(
        training_data=training_data,
        model_name=model_name,
        ml_class_type=ml_class_type,
        name=name)

    accept = request.headers.get("Accept", "")

    if not binary_file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="NO_FILE_FOUND",
                error_message="no file found").model_dump())

    settings = get_settings()
    max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

    file_content = await binary_file.read()
    logger.info(
        "Binary upload started: {} ({} bytes)",
        binary_file.filename,
        len(file_content))

    if len(file_content) > max_file_size_bytes:
        actual_size_mb = len(file_content) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=create_error_response(
                error_code="FILE_TOO_LARGE",
                error_message=f"File size ({actual_size_mb:.2f}MB) exceeds maximum allowed ({settings.max_file_size_mb}MB)").model_dump())

    validate_binary_mime_type(file_content)
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
                error_message="Insufficient disk space to complete upload").model_dump())

    file_path = os.path.join(upload_folder, unique_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
    is_training_data = form_data.training_data == "true"

    ghidra_task = GhidraRequest(
        unique_filename,
        is_training_data,
        form_data.model_name,
        form_data.name,
        form_data.ml_class_type)

    TaskManager.register_task(ghidra_task.uuid, "starting", owner_id=current_user.id)

    captured_ctx = capture_request_context()
    background_tasks.add_task(
        _run_pipeline_analysis, ghidra_task, file_path, captured_ctx)
    logger.info("Binary uploaded to: {}, background task queued (uuid={}), returning response now", file_path, ghidra_task.uuid)

    if "text/html" in accept and "application/json" not in accept:
        return templates.TemplateResponse(request, "upload.html", {"user": current_user})

    result = create_success_response(
        data=BinaryUploadResponse(uuid=ghidra_task.uuid),
        message="Binary uploaded successfully")
    logger.info("Returning success response for upload {}", ghidra_task.uuid)
    return result


@router.get("/listBins", response_model=SuccessResponse[dict[str, Any]])
async def list_bins(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
    files: list[str] = []
    settings = get_settings()
    directory_path = settings.upload_folder
    for _, _, files_found in os.walk(directory_path):
        if files_found:
            files.extend(files_found)
    return create_success_response(
        data={"files": files},
        message="Binaries retrieved successfully")
