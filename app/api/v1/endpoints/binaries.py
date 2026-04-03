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

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, StringConstraints
from typing_extensions import Annotated

from app.config.settings import get_settings
from app.services.request_handler import GhidraRequest
from app.processing.task_management import Ghidra
from app.utils.responses import create_success_response, create_error_response, SuccessResponse


class UploadBinaryRequest(BaseModel):
    """Request model for binary upload.

    Attributes:
        binary_file: The binary file to upload.
        training_data: Whether this is training data.
        model_name: Name of the model to use.
        ml_class_type: Type of ML classification.
        task_name: Optional task name.
    """

    binary_file: UploadFile
    training_data: str = "false"
    model_name: str
    ml_class_type: str
    task_name: str | None = None

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Allowed MIME types for binary files
ALLOWED_MIME_TYPES = {
    'application/x-executable',
    'application/x-object',
    'application/octet-stream',
    'application/x-elf',
    'application/x-dosexec',  # Windows PE/EXE files
    'application/x-sharedlib',  # Shared libraries (.so, .dll)
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
            detail=f"File type '{mime_type}' not allowed. Expected binary/ELF format"
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
    if '..' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename characters")
    
    # Check for null bytes
    if '\x00' in filename:
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
        Ghidra().start_task(ghidra_request)
        logging.info("Ghidra analysis task completed successfully: %s", ghidra_request.uuid)
    except Exception as exc:
        logging.error("Ghidra analysis task failed: %s - %s", ghidra_request.uuid, exc)
        raise


@router.post("/uploadBinary", response_model=SuccessResponse[dict])
async def post_upload_binary(
    background_tasks: BackgroundTasks,
    request: Request,
    binary_file: UploadFile = File(...),
    training_data: str = Form("false"),
    model_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Form(...),
    ml_class_type: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Form(...),
    task_name: Annotated[str, StringConstraints(strip_whitespace=True)] = Form(""),
):
    """Handle POST request for binary file uploads.

    Args:
        background_tasks: FastAPI BackgroundTasks for async task execution.
        request: The FastAPI request object.
        binary_file: The binary file to upload.
        training_data: Whether this is training data.
        model_name: Name of the model to use (automatically validated and stripped).
        ml_class_type: Type of ML classification (automatically validated and stripped).
        task_name: Optional task name (automatically stripped).

    Returns:
        JSONResponse with upload result or HTML template.
        
    Raises:
        HTTPException: If validation fails or file is too large.
    """
    accept = request.headers.get("Accept", "")

    if not binary_file.filename:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="NO_FILE_FOUND",
                error_message="no file found",
            ).model_dump(),
        )

    try:
        is_training_data: bool = training_data.lower() == "true"
        # Validation is handled by Pydantic - strings are already stripped
    except (AttributeError, ValueError) as exc:
        logging.error("Failed to parse request parameters: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code="PARSE_ERROR",
                error_message=str(exc),
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

    ghidra_task = GhidraRequest(
        unique_filename, is_training_data, model_name, task_name, ml_class_type
    )
    
    # Add Ghidra analysis as a background task
    background_tasks.add_task(_run_ghidra_analysis, ghidra_task)

    if "*/*" in accept:
        return templates.TemplateResponse("upload.html", {"request": request})

    return create_success_response(
        data={"uuid": unique_filename},
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
