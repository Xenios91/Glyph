import logging
import os
import stat
from pathlib import Path
import uuid
import magic

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config.settings import GlyphConfig
from app.services.request_handler import GhidraRequest
from app.processing.task_management import Ghidra

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
    except Exception as e:
        logging.error("Failed to detect MIME type: %s", e)
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


@router.post("/uploadBinary")
async def post_upload_binary(
    request: Request,
    binaryFile: UploadFile = File(...),
    trainingData: str = Form("false"),
    modelName: str = Form(...),
    mlClassType: str = Form(...),
    taskName: str | None = Form(""),
):
    """
    Handles POST request for binary file uploads
    """
    accept = request.headers.get("Accept", "")

    if not binaryFile.filename:
        return JSONResponse(content={"error": "no file found"}, status_code=400)

    try:
        is_training_data: bool = trainingData.lower() == "true"
        model_name: str = modelName.strip()
        task_name: str = taskName.strip() if taskName else ""
        ml_class_type: str = mlClassType.strip()
    except Exception as e:
        logging.error(e)
        return JSONResponse(content={"error": str(e)}, status_code=400)

    if not model_name or not ml_class_type:
        return JSONResponse(
            content={"error": "invalid request, missing query strings"}, status_code=400
        )

    max_file_size_mb = GlyphConfig.get_config_value("max_file_size_mb")
    if max_file_size_mb is None:
        max_file_size_mb = 512

    max_file_size_bytes = max_file_size_mb * 1024 * 1024

    file_content = await binaryFile.read()
    if len(file_content) > max_file_size_bytes:
        actual_size_mb = len(file_content) / (1024 * 1024)
        return JSONResponse(
            content={
                "error": f"File size ({actual_size_mb:.2f}MB) exceeds maximum "
                f"allowed ({max_file_size_mb}MB)"
            },
            status_code=413
        )

    # Validate MIME type to ensure file is a legitimate binary
    validate_binary_mime_type(file_content)

    # Sanitize filename to prevent path traversal attacks
    safe_filename = sanitize_filename(binaryFile.filename)
    
    # Generate unique filename using UUID (no extension from user input)
    unique_filename = f"{uuid.uuid4()}"
    upload_folder = GlyphConfig._config["UPLOAD_FOLDER"]

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
    Ghidra().start_task(ghidra_task)

    if "*/*" in accept:
        return templates.TemplateResponse("upload.html", {"request": request})

    return JSONResponse(content={}, status_code=200)


@router.get("/listBins")
async def list_bins():
    """
    Handles a GET request to retrieve all available binaries
    """
    files: list[str] = []
    directory_path = GlyphConfig._config["UPLOAD_FOLDER"]
    for _, _, files_found in os.walk(directory_path):
        if files_found:
            files.extend(files_found)
    return JSONResponse(content={"files": files}, status_code=200)
