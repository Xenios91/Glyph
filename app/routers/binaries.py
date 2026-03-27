import logging
import os
from pathlib import Path
import uuid

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import GlyphConfig
from app.request_handler import GhidraRequest
from app.task_management import Ghidra

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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

    extension = Path(binaryFile.filename).suffix
    unique_filename = f"{uuid.uuid4()}{extension}"
    upload_folder = GlyphConfig._config["UPLOAD_FOLDER"]

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)
    with open(file_path, "wb") as f:
        f.write(file_content)

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
