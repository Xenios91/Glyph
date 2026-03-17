import logging
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates


from app.persistance_util import (
    FunctionPersistanceUtil,
    MLPersistanceUtil,
    PredictionPersistanceUtil,
)
from app.task_management import TaskManager

from app.helpers import ACCEPT_TYPE
from templates.utils import format_code

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/getModels")
async def get_list_models(request: Request):
    """
    Handles a GET request to obtain all models available
    """
    models: set[str] = MLPersistanceUtil.get_models_list()
    accept = request.headers.get("Accept", "")

    if ACCEPT_TYPE not in accept:
        return {"models": list(models)}

    models_status: dict = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"

    return templates.TemplateResponse(
        "get_models.html",
        {"request": request, "title": "Models List", "models": models_status},
    )


@router.delete("/deleteModel")
async def delete_model(modelName: str = Query(...)):
    """
    Handles a DELETE request to delete a supplied model by name
    """
    model_name = modelName.strip()

    if not model_name:
        raise HTTPException(status_code=400, detail="invalid model name")

    try:
        MLPersistanceUtil.delete_model(model_name)
        PredictionPersistanceUtil.delete_model_predictions(model_name)
        return JSONResponse(content={}, status_code=200)
    except Exception as error:
        logging.error(error)
        # Depending on your preference, you can return a 500 or just an empty 200
        return JSONResponse(content={}, status_code=200)


@router.get("/getFunction")
async def get_function(
    request: Request, modelName: str = Query(...), functionName: str = Query(...)
):
    """
    Handles a GET request to return a specific function associated with a model
    """
    model_name = modelName.strip()
    func_name_query = functionName.strip()

    if not model_name or not func_name_query:
        raise HTTPException(status_code=400, detail="invalid model or function name")

    function_information: list = FunctionPersistanceUtil.get_function(
        model_name, func_name_query
    )

    if not function_information:
        raise HTTPException(status_code=404, detail="Function not found")

    f_name = function_information[1]
    f_entry = function_information[2]
    f_tokens = format_code(function_information[3])

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return {"functions": function_information}

    return templates.TemplateResponse(
        "get_function.html",
        {
            "request": request,
            "model_name": model_name,
            "function_name": f_name,
            "function_entry": f_entry,
            "tokens": f_tokens,
        },
    )


@router.get("/getFunctions")
async def get_functions(request: Request, modelName: str = Query(...)):
    """
    Handles a GET request to return all identified functions associated with a model
    """
    model_name = modelName.strip()

    if not model_name:
        raise HTTPException(status_code=400, detail="invalid model name")

    functions: list = FunctionPersistanceUtil.get_functions(model_name)

    accept = request.headers.get("Accept", "")
    if ACCEPT_TYPE not in accept:
        return {"functions": functions}

    return templates.TemplateResponse(
        "get_symbols.html",
        {
            "request": request,
            "bin_name": "test",
            "model_name": model_name,
            "functions": functions,
        },
    )
