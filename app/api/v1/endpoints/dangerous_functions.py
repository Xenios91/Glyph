"""Dangerous function scanning endpoints for Glyph API v1.

Provides endpoints for scanning analyzed binaries for dangerous/insecure
functions and retrieving scan results with severity, CWE references,
and usage context.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_active_user
from app.database.models import User
from app.services.dangerous_function_scanner import (
    ScanReport,
    ScanResult,
    generate_report,
)
from app.services.dangerous_functions_catalog import (
    get_all_entries,
    get_categories,
    get_entries_by_category,
    get_entry,
)
from app.utils.persistence_util import FunctionPersistanceUtil, MLPersistanceUtil, PredictionPersistanceUtil
from app.utils.responses import (
    create_error_response,
    create_success_response,
    ErrorResponse,
    SuccessResponse,
)
from app.utils.secure_deserializer import secure_load, SecureDeserializationError
from loguru import logger

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    """Request schema for initiating a dangerous function scan.

    Attributes:
        modelName: Name of the model to scan (functions stored for this model).
        taskName: Optional name of a prediction task to scan instead.
    """

    modelName: str | None = None
    taskName: str | None = None

    model_config = {"extra": "allow"}


class ScanResultDict(BaseModel):
    """Single scan result for API response.

    Attributes:
        function_name: Dangerous function name found.
        containing_function: Function that contains or is the dangerous function.
        entrypoint: Memory offset/address.
        category: Vulnerability category.
        severity: Risk level.
        cwe: CWE identifier.
        description: Why this function is dangerous.
        safe_alternative: Recommended replacement.
        usage_context: Decompiled code lines showing usage.
    """

    function_name: str
    containing_function: str
    entrypoint: str
    category: str
    severity: str
    cwe: str
    description: str
    safe_alternative: str
    usage_context: list[str] = []


class ScanReportResponse(BaseModel):
    """Aggregated scan report for API response.

    Attributes:
        model_name: Name of the model/binary scanned.
        total_functions_scanned: Total functions analyzed.
        total_found: Total dangerous function matches.
        critical_count: Critical severity count.
        high_count: High severity count.
        medium_count: Medium severity count.
        low_count: Low severity count.
        results: Individual scan results.
    """

    model_name: str
    total_functions_scanned: int
    total_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    results: list[ScanResultDict] = []


class CatalogEntryDict(BaseModel):
    """Catalog entry for API response.

    Attributes:
        name: Function name.
        category: Vulnerability category.
        severity: Risk level.
        cwe: CWE identifier.
        description: Why this function is dangerous.
        safe_alternative: Recommended replacement.
    """

    name: str
    category: str
    severity: str
    cwe: str
    description: str
    safe_alternative: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _scan_result_to_dict(result: ScanResult) -> ScanResultDict:
    """Convert a ScanResult dataclass to a ScanResultDict model.

    Args:
        result: Scan result from the scanner service.

    Returns:
        ScanResultDict suitable for JSON serialization.
    """
    return ScanResultDict(
        function_name=result.function_name,
        containing_function=result.containing_function,
        entrypoint=result.entrypoint,
        category=result.category,
        severity=result.severity,
        cwe=result.cwe,
        description=result.description,
        safe_alternative=result.safe_alternative,
        usage_context=result.usage_context,
    )


def _scan_report_to_dict(report: ScanReport) -> ScanReportResponse:
    """Convert a ScanReport dataclass to a ScanReportResponse model.

    Args:
        report: Scan report from the scanner service.

    Returns:
        ScanReportResponse suitable for JSON serialization.
    """
    results = [_scan_result_to_dict(r) for r in report.results]
    return ScanReportResponse(
        model_name=report.model_name,
        total_functions_scanned=report.total_functions_scanned,
        total_found=report.total_found,
        critical_count=report.critical_count,
        high_count=report.high_count,
        medium_count=report.medium_count,
        low_count=report.low_count,
        results=results,
    )


def _functions_to_dicts(functions: list[Any]) -> list[dict[str, Any]]:
    """Convert ORM Function objects to dictionaries for the scanner.

    Args:
        functions: List of Function ORM objects.

    Returns:
        List of function dictionaries compatible with scan_functions().
    """
    result: list[dict[str, Any]] = []
    for func in functions:
        # ORM objects have attributes; convert to dict format expected by scanner
        func_dict: dict[str, Any] = {
            "functionName": func.function_name,
            "lowAddress": func.entrypoint,
            "tokenList": func.tokens.split() if func.tokens else [],
        }
        result.append(func_dict)
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/catalog")
async def get_catalog(
    request: Request,
    category: str | None = Query(None, description="Filter by category"),
) -> SuccessResponse[Any]:
    """Get the dangerous function catalog.

    Returns all known dangerous functions or filters by category.

    Args:
        request: FastAPI request object.
        category: Optional category filter (e.g., "Buffer Overflow").

    Returns:
        Success response with catalog entries.
    """
    if category:
        entries = get_entries_by_category(category)
    else:
        entries = get_all_entries()

    catalog = [
        CatalogEntryDict(
            name=e.name,
            category=e.category,
            severity=e.severity,
            cwe=e.cwe,
            description=e.description,
            safe_alternative=e.safe_alternative,
        )
        for e in entries
    ]

    return create_success_response(
        data={"categories": get_categories(), "entries": catalog},
        message="Catalog retrieved successfully",
    )


@router.get("/catalog/{function_name}")
async def get_catalog_entry(
    request: Request,
    function_name: str,
) -> Union[SuccessResponse[Any], ErrorResponse]:
    """Get a specific dangerous function catalog entry.

    Args:
        request: FastAPI request object.
        function_name: Name of the function to look up.

    Returns:
        Success response with the catalog entry or error response if not found.
    """
    entry = get_entry(function_name)
    if entry is None:
        return create_error_response(
            error_code="CATALOG_NOT_FOUND",
            error_message=f"Function '{function_name}' not found in catalog",
        )

    return create_success_response(
        data=CatalogEntryDict(
            name=entry.name,
            category=entry.category,
            severity=entry.severity,
            cwe=entry.cwe,
            description=entry.description,
            safe_alternative=entry.safe_alternative,
        ).model_dump(),
        message=f"Catalog entry for '{function_name}' retrieved",
    )


@router.get("/available-models")
async def get_available_models(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[Any]:
    """Get list of models and prediction tasks available for scanning.

    Returns:
        Success response with lists of model names and prediction task names.
    """
    models = await MLPersistanceUtil.get_models_list()
    predictions = await PredictionPersistanceUtil.get_predictions_list()

    task_names: list[str] = [p.task_name for p in predictions] if predictions else []

    return create_success_response(
        data={
            "models": models,
            "prediction_tasks": task_names,
        },
        message="Available targets retrieved",
    )


@router.post("/scan")
async def scan_dangerous_functions(
    request: Request,
    body: ScanRequest,
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[Any]:
    """Scan a model or prediction task for dangerous functions.

    Analyzes all functions stored for the specified model or prediction task
    against the dangerous function catalog and returns a report with matches,
    severity levels, and usage context.

    Args:
        request: FastAPI request object.
        body: Scan request with modelName or taskName.
        current_user: Authenticated user.

    Returns:
        Success response with scan report.

    Raises:
        HTTPException: If neither modelName nor taskName is provided,
            or if the specified target does not exist.
    """
    target_name: str | None = None
    functions_data: list[dict[str, Any]] = []

    if body.modelName:
        target_name = body.modelName
        # Check model exists
        exists = await MLPersistanceUtil.check_name(target_name)
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{target_name}' not found",
            )

        # Get functions for this model
        functions = await FunctionPersistanceUtil.get_functions(target_name)
        functions_data = _functions_to_dicts(functions)

    elif body.taskName:
        target_name = body.taskName
        # Get prediction data
        all_predictions = await PredictionPersistanceUtil.get_predictions_list()
        matching = [p for p in all_predictions if p.task_name == target_name]
        if not matching:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction task '{target_name}' not found",
            )
        prediction = matching[0]

        # Deserialize prediction functions
        try:
            raw_data = secure_load(BytesIO(prediction.functions_data))  # type: ignore[arg-type]
            if isinstance(raw_data, list):
                functions_data = raw_data  # type: ignore[assignment]
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Prediction data is not in expected format",
                )
        except SecureDeserializationError:
            raise HTTPException(
                status_code=500,
                detail="Failed to load prediction data: security validation failed",
            )
        except Exception:
            logger.exception("Failed to deserialize prediction data for task '%s'", target_name)
            raise HTTPException(
                status_code=500,
                detail="Failed to load prediction data",
            )

    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'modelName' or 'taskName' must be provided",
        )

    if not functions_data:
        return create_success_response(
            data=ScanReportResponse(
                model_name=target_name or "unknown",
                total_functions_scanned=0,
                total_found=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                results=[],
            ).model_dump(),
            message=f"No functions found for '{target_name}'",
        )

    # Perform scan
    report = generate_report(target_name or "unknown", functions_data)

    return create_success_response(
        data=_scan_report_to_dict(report).model_dump(),
        message=f"Scan complete: {report.total_found} dangerous functions found",
    )
