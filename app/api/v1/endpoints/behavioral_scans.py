"""Behavioral scan endpoints for Glyph API v1.

Provides endpoints for scanning analyzed binaries for malware-associated
behaviors and retrieving scan results with severity, behavior categories,
and matched evidence.
"""

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel

from app.auth.dependencies import assert_owned, can_access, get_current_active_user
from app.database.binary_repository import BinaryRepository
from app.database.behavioral_scan_report_repository import BehavioralScanReportRepository
from app.database.function_repository import FunctionRepository
from app.database.model_repository import ModelRepository
from app.database.models import User
from app.database.prediction_repository import PredictionRepository
from app.services.behavioral_scanner import (
    BehavioralScanReport,
    BehavioralScanResult,
    generate_report,
)
from app.services.behavioral_signatures_catalog import (
    get_all_entries,
    get_categories,
    get_entries_by_category,
    get_entry,
)
from app.utils.common import binary_function_to_dict
from app.utils.responses import (
    ErrorResponse,
    SuccessResponse,
    create_error_response,
    create_success_response,
)
from app.utils.secure_deserializer import SecureDeserializationError, secure_load_bytes

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class BehavioralScanRequest(BaseModel):
    """Request schema for initiating a behavioral scan.

    Attributes:
        modelName: Name of the model to scan (functions stored for this model).
        taskName: Optional name of a prediction task to scan instead.
        binaryId: Optional binary id to scan directly from the library.

    """

    modelName: str | None = None
    taskName: str | None = None
    binaryId: int | None = None

    model_config = {"extra": "forbid"}


class BehavioralScanResultDict(BaseModel):
    """Single behavioral scan result for API response.

    Attributes:
        signature_id: Stable id of the matched signature.
        behavior_name: Human-readable behavior name.
        category: Behavior category.
        severity: Risk level.
        detection_method: How the signature was detected.
        containing_function: Function exhibiting the behavior.
        entrypoint: Memory offset/address.
        mitre_technique: Optional MITRE ATT&CK technique id.
        description: What the behavior means.
        matched_evidence: Decompiled statements that triggered the signature.
        containing_function_code: Full decompiled code of the containing function.

    """

    signature_id: str
    behavior_name: str
    category: str
    severity: str
    detection_method: str
    containing_function: str
    entrypoint: str
    mitre_technique: str
    description: str
    matched_evidence: list[str] = []
    containing_function_code: str = ""


class BehavioralScanReportResponse(BaseModel):
    """Aggregated behavioral scan report for API response.

    Attributes:
        model_name: Name of the model/binary scanned.
        total_functions_scanned: Total functions analyzed.
        total_found: Total behavioral matches.
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
    results: list[BehavioralScanResultDict] = []


class SignatureEntryDict(BaseModel):
    """Behavioral signature catalog entry for API response.

    Attributes:
        signature_id: Stable id of the signature.
        name: Human-readable behavior name.
        category: Behavior category.
        severity: Risk level.
        detection_method: How the signature is detected.
        patterns: Patterns to match, interpreted per detection method.
        description: What the behavior means and why it matters.
        mitre_technique: Optional MITRE ATT&CK technique id.

    """

    signature_id: str
    name: str
    category: str
    severity: str
    detection_method: str
    patterns: list[str]
    description: str
    mitre_technique: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _scan_result_to_dict(result: BehavioralScanResult) -> BehavioralScanResultDict:
    """Convert a BehavioralScanResult dataclass to a BehavioralScanResultDict model.

    Args:
        result: Scan result from the scanner service.

    Returns:
        BehavioralScanResultDict suitable for JSON serialization.

    """
    return BehavioralScanResultDict(
        signature_id=result.signature_id,
        behavior_name=result.behavior_name,
        category=result.category,
        severity=result.severity,
        detection_method=result.detection_method,
        containing_function=result.containing_function,
        entrypoint=result.entrypoint,
        mitre_technique=result.mitre_technique,
        description=result.description,
        matched_evidence=result.matched_evidence,
        containing_function_code=result.containing_function_code,
    )


def _scan_report_to_dict(report: BehavioralScanReport) -> BehavioralScanReportResponse:
    """Convert a BehavioralScanReport dataclass to a BehavioralScanReportResponse model.

    Args:
        report: Scan report from the scanner service.

    Returns:
        BehavioralScanReportResponse suitable for JSON serialization.

    """
    results = [_scan_result_to_dict(r) for r in report.results]
    return BehavioralScanReportResponse(
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
    category: Annotated[str | None, Query(description="Filter by category")] = None,
) -> SuccessResponse[Any]:
    """Get the behavioral signature catalog.

    Returns all known behavioral signatures or filters by category.

    Args:
        request: FastAPI request object.
        category: Optional category filter (e.g., "Anti-Debugging").

    Returns:
        Success response with catalog entries.

    """
    entries = get_entries_by_category(category) if category else get_all_entries()

    catalog = [
        SignatureEntryDict(
            signature_id=e.signature_id,
            name=e.name,
            category=e.category,
            severity=e.severity,
            detection_method=e.detection_method,
            patterns=list(e.patterns),
            description=e.description,
            mitre_technique=e.mitre_technique,
        )
        for e in entries
    ]

    return create_success_response(
        data={"categories": get_categories(), "entries": catalog},
        message="Catalog retrieved successfully",
    )


@router.get("/catalog/{signature_id}")
async def get_catalog_entry(
    request: Request,
    signature_id: str,
) -> SuccessResponse[Any] | ErrorResponse:
    """Get a specific behavioral signature catalog entry.

    Args:
        request: FastAPI request object.
        signature_id: Stable signature id (e.g., "BEHAV-001") or behavior name.

    Returns:
        Success response with the catalog entry or error response if not found.

    """
    entry = get_entry(signature_id)
    if entry is None:
        return create_error_response(
            error_code="CATALOG_NOT_FOUND",
            error_message=f"Signature '{signature_id}' not found in catalog",
        )

    return create_success_response(
        data=SignatureEntryDict(
            signature_id=entry.signature_id,
            name=entry.name,
            category=entry.category,
            severity=entry.severity,
            detection_method=entry.detection_method,
            patterns=list(entry.patterns),
            description=entry.description,
            mitre_technique=entry.mitre_technique,
        ).model_dump(),
        message=f"Catalog entry for '{signature_id}' retrieved",
    )


@router.get("/available-models")
async def get_available_models(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Get list of models and prediction tasks available for scanning.

    Returns:
        Success response with lists of model names and prediction task names.

    """
    # Scope to targets the current user may access (own + legacy/unowned).
    models = await ModelRepository.get_models_list_for_user(current_user.id)
    # Fetch only the task names the user may access; this avoids loading and
    # deserializing every prediction's functions_data BLOB.
    task_names: list[str] = sorted(await PredictionRepository.get_task_names_for_user(current_user.id))

    return create_success_response(
        data={
            "models": models,
            "prediction_tasks": task_names,
        },
        message="Available targets retrieved",
    )


@router.post("/scan")
async def scan_behavioral(
    request: Request,
    body: BehavioralScanRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Scan a model, prediction task, or binary for malware-associated behaviors.

    Analyzes all functions stored for the specified model, prediction task,
    or binary against the behavioral signature catalog and returns a report
    with matches, severity levels, and matched evidence.

    Args:
        request: FastAPI request object.
        body: Scan request with modelName, taskName, or binaryId.
        current_user: Authenticated user.

    Returns:
        Success response with scan report.

    Raises:
        HTTPException: If none of modelName, taskName, or binaryId is provided,
            or if the specified target does not exist.

    """
    target_name: str | None = None
    functions_data: list[dict[str, Any]] = []
    report_owner_id: int | None = None

    if body.modelName:
        target_name = body.modelName
        # Check model exists and is accessible by the current user
        model_row = await ModelRepository.get(target_name)
        if model_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{target_name}' not found",
            )
        assert_owned(model_row, current_user, "model")
        report_owner_id = model_row.user_id

        # Get functions for this model (scoped to accessible rows)
        functions = await FunctionRepository.get_functions(target_name)
        functions = [f for f in functions if can_access(f, current_user)]
        functions_data = _functions_to_dicts(functions)

    elif body.binaryId is not None:
        # Load binary and check ownership
        binary = await BinaryRepository.get(binary_id=body.binaryId)
        if binary is None:
            raise HTTPException(
                status_code=404,
                detail=f"Binary {body.binaryId} not found",
            )

        if binary.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

        target_name = binary.name
        report_owner_id = binary.uploaded_by

        # Load binary functions and convert to dict format
        binary_functions = await BinaryRepository.get_functions(binary_id=body.binaryId)
        functions_data = [binary_function_to_dict(bf) for bf in binary_functions]

    elif body.taskName:
        target_name = body.taskName
        # Get the caller's own prediction with this task name. Scoped to the
        # caller so a same-named row owned by another user is never matched.
        prediction = await PredictionRepository.get_for_user(target_name, current_user.id)
        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction task '{target_name}' not found",
            )

        # Enforce prediction ownership before exposing any prediction data.
        assert_owned(prediction, current_user, "prediction")
        report_owner_id = prediction.user_id

        # Deserialize prediction functions (off the event loop; handles both
        # compressed and legacy uncompressed payloads).
        try:
            raw_data = await asyncio.to_thread(secure_load_bytes, prediction.functions_data)
            if isinstance(raw_data, list):
                functions_data = raw_data
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
            logger.exception("Failed to deserialize prediction data for task '{}'", target_name)
            raise HTTPException(
                status_code=500,
                detail="Failed to load prediction data",
            )

    else:
        raise HTTPException(
            status_code=400,
            detail="One of 'modelName', 'taskName', or 'binaryId' must be provided",
        )

    # Perform scan (empty function lists produce an empty report)
    report = generate_report(target_name or "unknown", functions_data)
    report_dict = _scan_report_to_dict(report).model_dump()

    # Persist the report so it can be restored when the target is re-selected.
    # A persistence failure must not fail the scan itself.
    try:
        await BehavioralScanReportRepository.save_report(report_dict, user_id=report_owner_id)
    except Exception:
        logger.exception("Failed to persist behavioral scan report for target '{}'", target_name)

    message = (
        f"No functions found for '{target_name}'"
        if not functions_data
        else f"Scan complete: {report.total_found} behaviors found"
    )
    return create_success_response(data=report_dict, message=message)


@router.get(
    "/scan-results",
    summary="Retrieve the last stored behavioral scan report for a target",
    description=(
        "Return the most recent behavioral scan report previously persisted "
        "for the given target name. The data payload is null when the target has "
        "never been scanned."
    ),
)
async def get_scan_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=256, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Get the last stored behavioral scan report for a target.

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response with the stored scan report, or a null data payload
        when nothing has been saved yet for the target.

    """
    row = await BehavioralScanReportRepository.get_report(target_name, current_user.id)
    if row is None:
        return create_success_response(
            data=None,
            message=f"No stored behavioral scan results for '{target_name}'",
        )

    try:
        results = json.loads(row.results_json) if row.results_json else []
    except (json.JSONDecodeError, TypeError):
        logger.exception("Failed to decode stored behavioral scan results for target '{}'", target_name)
        results = []

    return create_success_response(
        data={
            "model_name": row.target_name,
            "total_functions_scanned": row.total_functions_scanned,
            "total_found": row.total_found,
            "critical_count": row.critical_count,
            "high_count": row.high_count,
            "medium_count": row.medium_count,
            "low_count": row.low_count,
            "results": results,
            "modified_at": row.modified_at.isoformat(),
        },
        message=f"Stored behavioral scan results retrieved for '{target_name}'",
    )


@router.delete(
    "/scan-results",
    summary="Delete the stored behavioral scan report for a target",
    description=(
        "Remove the persisted behavioral scan report for the given target name."
    ),
)
async def delete_scan_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=256, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[str]:
    """Delete the stored behavioral scan report for a target.

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response confirming deletion (or that nothing was stored).

    """
    deleted = await BehavioralScanReportRepository.delete_for_target(target_name, current_user.id)

    if not deleted:
        return create_success_response(data="not_found", message=f"No stored behavioral scan results for '{target_name}'")

    return create_success_response(
        data="deleted",
        message=f"Stored behavioral scan results deleted for '{target_name}'",
    )
