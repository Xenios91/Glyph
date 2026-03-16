from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import os
import logging
from werkzeug.utils import secure_filename
from app.persistance_util import MLPersistanceUtil
from app.request_handler import GhidraRequest
from app.task_management import Ghidra
from app.helpers import ACCEPT_TYPE
from app.config import GlyphConfig

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/uploadBinary")
async def get_upload_binary(request: Request):
    """
    Handles GET request to load the upload webpage
    """
    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return JSONResponse(content={"error": "API calls can only be POST"}, status_code=200)

    models: set[str] = MLPersistanceUtil.get_models_list()
    allow_prediction = len(models) > 0
    return templates.TemplateResponse(
        "upload.html",
        {"request": request, "allow_prediction": allow_prediction, "models": models},
    )


@router.post("/uploadBinary")
async def post_upload_binary(
    request: Request,
    binaryFile: UploadFile = File(...),
    trainingData: str = Form("false"),
    modelName: str = Form(...),
    mlClassType: str = Form(...),
    taskName: Optional[str] = Form(""),
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

    filename = secure_filename(binaryFile.filename)
    upload_folder = GlyphConfig._config["UPLOAD_FOLDER"]

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    with open(file_path, "wb") as f:
        f.write(await binaryFile.read())

    ghidra_task = GhidraRequest(
        filename, is_training_data, model_name, task_name, ml_class_type
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