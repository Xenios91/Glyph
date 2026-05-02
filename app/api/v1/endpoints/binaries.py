"""Binary upload and management endpoints for Glyph API.

This module provides endpoints for uploading binary files and managing
binary-related operations.
"""

import os
import shutil
import stat
import time
from pathlib import Path
import uuid
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
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from app.config.settings import get_settings
from app.services.request_handler import GhidraRequest
from app.processing.task_management import Ghidra
from app.utils.persistence_util import FunctionPersistanceUtil
from app.utils.responses import (
    create_success_response,
    create_error_response,
    SuccessResponse)
from app.utils.jinja_utils import configure_jinja2_templates
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
    """Pydantic model for binary upload form validation.

    Attributes:
        training_data: Whether this is training data ("true" or "false").
        model_name: Name of the model to use (required, non-empty).
        ml_class_type: Type of ML classification (required, non-empty).
        name: Required name for both training and prediction modes.
    """

    training_data: str = Field(
        default="false",
        description="Whether this is training data")
    model_name: str = Field(
        ...,
        min_length=1,
        description="Name of the model to use")
    ml_class_type: str = Field(
        ...,
        min_length=1,
        description="Type of ML classification")
    name: str = Field(
        ...,
        min_length=1,
        description="Required name for the task or model")

    @field_validator("training_data", mode="before")
    @classmethod
    def validate_training_data(cls, v: str | None) -> str:
        """Validate training_data is 'true' or 'false'."""
        if v is None:
            return "false"
        v_lower = v.lower().strip()
        if v_lower not in ("true", "false"):
            raise ValueError("training_data must be 'true' or 'false'")
        return v_lower

    @field_validator("model_name", "ml_class_type", "name", mode="before")
    @classmethod
    def strip_strings(cls, v: str | None) -> str:
        """Strip whitespace from string fields."""
        if v is None:
            raise ValueError("Field cannot be empty")
        return v.strip()


class BinaryUploadResponse(BaseModel):
    """Response model for binary upload.

    Attributes:
        uuid: The unique identifier for the uploaded binary.
    """

    uuid: str = Field(..., description="Unique identifier for the uploaded binary")


router = APIRouter()
templates = Jinja2Templates(directory="templates")
configure_jinja2_templates(templates)

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
    except Exception:
        logger.exception("Failed to detect MIME type")
        raise HTTPException(status_code=400, detail="Failed to analyze file type")

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{mime_type}' not allowed. Expected binary/ELF format")


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


async def _run_pipeline_analysis(
    ghidra_request: GhidraRequest,
    file_path: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Background task for running the full analysis pipeline on a binary.

    This function uses the pluggable pipeline framework to process the binary:
    1. Validation - Binary file validation
    2. Decompile - Ghidra decompilation
    3. Tokenize - Token extraction
    4. Filter - Token filtering/normalization
    5. FeatureExtract - TF-IDF feature extraction
    6. Train/Predict - Model training or prediction

    Args:
        ghidra_request: The Ghidra request containing analysis parameters.
        file_path: Path to the uploaded binary file.
        captured_ctx: Captured request context from the originating request
            thread. Restored before awaiting to preserve tracing.
    """
    try:
        # Restore request context from the snapshot captured on the request thread
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=ghidra_request.uuid)

        # Run the full pipeline
        result = await Ghidra.run_full_pipeline(ghidra_request, file_path)

        # Handle results based on pipeline type
        if result.error:
            logger.opt(exception=result.exc_info).error(
                "Pipeline execution failed: {}", result.error)
        else:
            logger.info("Pipeline execution completed")

            # For training, save functions to database
            if ghidra_request.is_training:
                filtered_functions = result.get("filtered_functions")
                if filtered_functions:
                    # Create a mock training request for persistence
                    from app.services.request_handler import TrainingRequest

                    training_data = {
                        "binaryName": ghidra_request.file_name,
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    training_request = TrainingRequest(
                        req_uuid=ghidra_request.uuid,
                        model_name=ghidra_request.model_name,
                        data=training_data)
                    await FunctionPersistanceUtil.add_model_functions(training_request)
                    logger.debug(
                        "Functions saved for model {}",
                        ghidra_request.model_name)

            # For prediction, save predictions to database
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
                    logger.debug(
                        "Creating PredictionRequest for task '{}' uuid {}",
                        ghidra_request.name,
                        ghidra_request.uuid)
                    try:
                        prediction_request = PredictionRequest(
                            req_uuid=ghidra_request.uuid,
                            model_name=ghidra_request.model_name,
                            data=prediction_data)
                        logger.debug(
                            "PredictionRequest created for task '{}'",
                            prediction_request.task_name)
                        await FunctionPersistanceUtil.add_prediction_functions(
                            prediction_request, predictions
                        )
                        logger.debug(
                            "Predictions saved for task {}",
                            ghidra_request.name)
                    except Exception:
                        logger.exception("Failed to create PredictionRequest")
                        raise

    except Exception:
        logger.exception("Pipeline task failed")
        raise
    finally:
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
    """Handle POST request for binary file uploads.

    Args:
        background_tasks: FastAPI BackgroundTasks for async task execution.
        request: The FastAPI request object.
        binary_file: The binary file to upload.
        training_data: Whether this is training data ("true" or "false").
        model_name: Name of the model to use.
        ml_class_type: Type of ML classification.
        name: Required name for the task or model.

    Returns:
        JSONResponse with upload result or HTML template.

    Raises:
        HTTPException: If validation fails or file is too large.
    """
    _t0 = time.monotonic()
    def _elapsed(tag: str) -> None:
        logger.info("[UPLOAD-TIMING] {:.3f}s {}", time.monotonic() - _t0, tag)

    _elapsed("endpoint entry (after auth)")

    # Validate form data using Pydantic model
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
    _elapsed("file read complete")

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

    # Validate MIME type to ensure file is a legitimate binary
    validate_binary_mime_type(file_content)
    _elapsed("MIME validation complete")

    # Sanitize filename to prevent path traversal attacks
    sanitize_filename(binary_file.filename)
    _elapsed("filename sanitized")

    # Generate unique filename using UUID (no extension from user input)
    unique_filename = f"{uuid.uuid4()}"
    upload_folder = settings.upload_folder

    os.makedirs(upload_folder, exist_ok=True)
    # Set restrictive directory permissions (owner only)
    os.chmod(upload_folder, stat.S_IRWXU)

    # Check available disk space before writing
    disk_usage = shutil.disk_usage(upload_folder)
    if disk_usage.free < len(file_content) * 1.1:  # 10% buffer
        raise HTTPException(
            status_code=507,
            detail=create_error_response(
                error_code="INSUFFICIENT_STORAGE",
                error_message="Insufficient disk space to complete upload").model_dump())

    file_path = os.path.join(upload_folder, unique_filename)

    # Write file with secure permissions (owner read/write only)
    with open(file_path, "wb") as f:
        f.write(file_content)
    _elapsed("file written to disk")

    # Set restrictive file permissions (0o600 = owner read/write only)
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
    _elapsed("file permissions set")

    is_training_data = form_data.training_data == "true"

    ghidra_task = GhidraRequest(
        unique_filename,
        is_training_data,
        form_data.model_name,
        form_data.name,
        form_data.ml_class_type)

    # Capture request context before handing off to background task
    captured_ctx = capture_request_context()
    _elapsed("context captured")

    background_tasks.add_task(
        _run_pipeline_analysis, ghidra_task, file_path, captured_ctx)
    _elapsed("background task added")

    logger.info("Binary uploaded to: {}, background task queued, returning response now", file_path)

    # Return HTML only for browser navigation requests (Accept contains text/html)
    # API requests (Accept: application/json) should get JSON responses
    if "text/html" in accept and "application/json" not in accept:
        return templates.TemplateResponse(request, "upload.html", {})

    result = create_success_response(
        data=BinaryUploadResponse(uuid=unique_filename),
        message="Binary uploaded successfully")
    _elapsed("success response created")
    logger.info("Returning success response for upload {}", unique_filename)
    return result


@router.get("/listBins", response_model=SuccessResponse[dict[str, Any]])
async def list_bins(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> SuccessResponse[dict[str, Any]]:
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
        message="Binaries retrieved successfully")
