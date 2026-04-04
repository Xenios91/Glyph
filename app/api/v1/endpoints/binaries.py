"""Binary upload and management endpoints for Glyph API.

This module provides endpoints for uploading binary files and managing
binary-related operations.
"""

import logging
import os
import stat
from pathlib import Path
import uuid
import magic

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from app.config.settings import get_settings
from app.services.request_handler import GhidraRequest
from app.processing.task_management import Ghidra
from app.utils.responses import (
    create_success_response,
    create_error_response,
    SuccessResponse,
)


class BinaryUploadForm(BaseModel):
    """Pydantic model for binary upload form validation.

    Attributes:
        training_data: Whether this is training data ("true" or "false").
        model_name: Name of the model to use (required, non-empty).
        ml_class_type: Type of ML classification (required, non-empty).
        task_name: Optional task name (empty string or non-empty).
    """

    training_data: str = Field(
        default="false",
        description="Whether this is training data",
    )
    model_name: str = Field(
        ...,
        min_length=1,
        description="Name of the model to use",
    )
    ml_class_type: str = Field(
        ...,
        min_length=1,
        description="Type of ML classification",
    )
    task_name: str = Field(
        default="",
        description="Optional task name for prediction mode",
    )

    @field_validator("training_data", mode="before")
    @classmethod
    def validate_training_data(cls, v: str) -> str:
        """Validate training_data is 'true' or 'false'."""
        if v is None:
            return "false"
        v_lower = v.lower().strip()
        if v_lower not in ("true", "false"):
            raise ValueError("training_data must be 'true' or 'false'")
        return v_lower

    @field_validator("model_name", "ml_class_type", mode="before")
    @classmethod
    def strip_strings(cls, v: str) -> str:
        """Strip whitespace from string fields."""
        if v is None:
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("task_name", mode="before")
    @classmethod
    def strip_task_name(cls, v: str) -> str:
        """Strip whitespace from task_name field."""
        if v is None:
            return ""
        return v.strip()


class BinaryUploadResponse(BaseModel):
    """Response model for binary upload.

    Attributes:
        uuid: The unique identifier for the uploaded binary.
    """

    uuid: str = Field(..., description="Unique identifier for the uploaded binary")


router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Allowed MIME types for binary files
ALLOWED_MIME_TYPES = {
    "application/x-executable",
    "application/x-object",
    "application/octet-stream",
    "application/x-elf",
    "application/x-dosexec",  # Windows PE/EXE files
    "application/x-sharedlib",  # Shared libraries (.so, .dll)
}


def validate_binary_mime_type(file_content: bytes) -> None:
    """Validate uploaded file is a legitimate binary using MIME type detection.

    Args:
        file_content: The file content bytes for MIME type detection.

    Raises:
        HTTPException: If MIME type validation fails.
    """
    try:
        mime_type = magic.from_buffer(file_content[:1024], mime=True)
    except Exception as exc:
        logging.error("Failed to detect MIME type: %s", exc)
        raise HTTPException(status_code=400, detail="Failed to analyze file type")

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{mime_type}' not allowed. Expected binary/ELF format",
        )


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks.

    Args:
        filename: The original filename.

    Returns:
        A sanitized filename with only the base name.

    Raises:
        HTTPException: If filename is invalid.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    # Check for path traversal attempts BEFORE stripping components
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename characters")

    # Check for null bytes
    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename characters")

    # Get just the filename without any directory components
    base_name = Path(filename).name

    return base_name


def _run_ghidra_analysis(ghidra_request: GhidraRequest) -> None:
    """Background task for running Ghidra analysis on a binary.

    Args:
        ghidra_request: The Ghidra request containing analysis parameters.
    """
    try:
        Ghidra.start_task(ghidra_request)
        logging.info(
            "Ghidra analysis task completed successfully: %s", ghidra_request.uuid
        )
    except Exception as exc:
        logging.error("Ghidra analysis task failed: %s - %s", ghidra_request.uuid, exc)
        raise


@router.post("/uploadBinary", response_model=SuccessResponse[BinaryUploadResponse])
async def post_upload_binary(
    background_tasks: BackgroundTasks,
    request: Request,
    binary_file: UploadFile = File(...),
    training_data: str = Form("false"),
    model_name: str = Form(...),
    ml_class_type: str = Form(...),
    task_name: str = Form(""),
):
    """Handle POST request for binary file uploads.

    Args:
        background_tasks: FastAPI BackgroundTasks for async task execution.
        request: The FastAPI request object.
        binary_file: The binary file to upload.
        training_data: Whether this is training data ("true" or "false").
        model_name: Name of the model to use.
        ml_class_type: Type of ML classification.
        task_name: Optional task name for prediction mode.

    Returns:
        JSONResponse with upload result or HTML template.

    Raises:
        HTTPException: If validation fails or file is too large.
    """
    # Validate form data using Pydantic model
    form_data = BinaryUploadForm(
        training_data=training_data,
        model_name=model_name,
        ml_class_type=ml_class_type,
        task_name=task_name,
    )

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
    if len(file_content) > max_file_size_bytes:
        actual_size_mb = len(file_content) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=create_error_response(
                error_code="FILE_TOO_LARGE",
                error_message=f"File size ({actual_size_mb:.2f}MB) exceeds maximum allowed ({settings.max_file_size_mb}MB)",
            ).model_dump(),
        )

    # Validate MIME type to ensure file is a legitimate binary
    validate_binary_mime_type(file_content)

    # Sanitize filename to prevent path traversal attacks
    sanitize_filename(binary_file.filename)

    # Generate unique filename using UUID (no extension from user input)
    unique_filename = f"{uuid.uuid4()}"
    upload_folder = settings.upload_folder

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)

    # Write file with secure permissions (owner read/write only)
    with open(file_path, "wb") as f:
        f.write(file_content)

    # Set restrictive file permissions (0o600 = owner read/write only)
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

    is_training_data = form_data.training_data == "true"

    ghidra_task = GhidraRequest(
        unique_filename,
        is_training_data,
        form_data.model_name,
        form_data.task_name,
        form_data.ml_class_type,
    )

    # Add Ghidra analysis as a background task
    background_tasks.add_task(_run_ghidra_analysis, ghidra_task)

    if "*/*" in accept:
        return templates.TemplateResponse("upload.html", {"request": request})

    return create_success_response(
        data=BinaryUploadResponse(uuid=unique_filename),
        message="Binary uploaded successfully",
    )


@router.get("/listBins", response_model=SuccessResponse[dict])
async def list_bins():
    """
    Handles a GET request to retrieve all available binaries
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
