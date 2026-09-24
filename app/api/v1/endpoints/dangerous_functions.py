"""Dangerous function scanning endpoints for Glyph API v1.

Provides endpoints for scanning analyzed binaries for dangerous/insecure
functions and retrieving scan results with severity, CWE references,
and usage context.
"""

import json
from io import BytesIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_active_user
from app.core.rate_limiter import LLM_ANALYSIS_LIMIT, limiter
from app.database.function_repository import FunctionRepository
from app.database.llm_result_repository import LLMResultRepository
from app.database.llm_user_config_repository import resolve_user_llm_config
from app.database.model_repository import ModelRepository
from app.database.models import LLMAnalysisResult, User
from app.database.prediction_repository import PredictionRepository
from app.database.scan_report_repository import ScanReportRepository
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
from app.services.llm_analysis_service import LLMNotConfiguredError, analyze_findings
from app.utils.responses import (
    ErrorResponse,
    SuccessResponse,
    create_error_response,
    create_success_response,
)
from app.utils.secure_deserializer import SecureDeserializationError, secure_load

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Request schema for initiating a dangerous function scan.

    Attributes:
        modelName: Name of the model to scan (functions stored for this model).
        taskName: Optional name of a prediction task to scan instead.
        binaryId: Optional binary id to scan directly from the library.

    """

    modelName: str | None = None
    taskName: str | None = None
    binaryId: int | None = None

    model_config = {"extra": "forbid"}


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
        containing_function_code: Full decompiled code of the containing function.

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
    containing_function_code: str = ""


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


class LLMAnalysisRequest(BaseModel):
    """Request schema for triggering LLM analysis of scan findings.

    Attributes:
        target_name: Stable name of the scanned target the findings belong to.
        save: Whether to persist the results to the database (default true).
        findings: Scanner findings to analyze, as obtained from a prior scan.

    """

    target_name: str = Field(min_length=1, max_length=128)
    save: bool = True
    findings: list[ScanResultDict] = Field(min_length=1, max_length=100)


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
        containing_function_code=result.containing_function_code,
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
    category: Annotated[str | None, Query(description="Filter by category")] = None,
) -> SuccessResponse[Any]:
    """Get the dangerous function catalog.

    Returns all known dangerous functions or filters by category.

    Args:
        request: FastAPI request object.
        category: Optional category filter (e.g., "Buffer Overflow").

    Returns:
        Success response with catalog entries.

    """
    entries = get_entries_by_category(category) if category else get_all_entries()

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
) -> SuccessResponse[Any] | ErrorResponse:
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
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Get list of models and prediction tasks available for scanning.

    Returns:
        Success response with lists of model names and prediction task names.

    """
    models = await ModelRepository.get_models_list()
    predictions = await PredictionRepository.get_predictions_list()

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
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Scan a model, prediction task, or binary for dangerous functions.

    Analyzes all functions stored for the specified model, prediction task,
    or binary against the dangerous function catalog and returns a report
    with matches, severity levels, and usage context.

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

    if body.modelName:
        target_name = body.modelName
        # Check model exists
        exists = await ModelRepository.exists(target_name)
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{target_name}' not found",
            )

        # Get functions for this model
        functions = await FunctionRepository.get_functions(target_name)
        functions_data = _functions_to_dicts(functions)

    elif body.binaryId is not None:
        from app.database.sql_service import SQLUtil

        # Load binary and check ownership
        binary = await SQLUtil.get_binary(body.binaryId)
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

        # Load binary functions and convert to dict format
        binary_functions = await SQLUtil.get_binary_functions(body.binaryId)
        functions_data = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in binary_functions
        ]

    elif body.taskName:
        target_name = body.taskName
        # Get prediction data
        all_predictions = await PredictionRepository.get_predictions_list()
        matching = [p for p in all_predictions if p.task_name == target_name]
        if not matching:
            raise HTTPException(
                status_code=404,
                detail=f"Prediction task '{target_name}' not found",
            )
        prediction = matching[0]

        # Deserialize prediction functions
        try:
            raw_data = secure_load(BytesIO(prediction.functions_data))  # type: ignore[attr-defined]
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
            logger.exception("Failed to deserialize prediction data for task '%s'", target_name)
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
        await ScanReportRepository.save_report(report_dict)
    except Exception:
        logger.exception("Failed to persist scan report for target '{}'", target_name)

    message = (
        f"No functions found for '{target_name}'"
        if not functions_data
        else f"Scan complete: {report.total_found} dangerous functions found"
    )
    return create_success_response(data=report_dict, message=message)


@router.get(
    "/scan-results",
    summary="Retrieve the last stored scan report for a target",
    description=(
        "Return the most recent dangerous function scan report previously persisted "
        "for the given target name. The data payload is null when the target has "
        "never been scanned."
    ),
)
async def get_scan_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=256, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[Any]:
    """Get the last stored scan report for a target.

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response with the stored scan report, or a null data payload
        when nothing has been saved yet for the target.

    """
    row = await ScanReportRepository.get_report(target_name)
    if row is None:
        return create_success_response(
            data=None,
            message=f"No stored scan results for '{target_name}'",
        )

    try:
        results = json.loads(row.results_json) if row.results_json else []
    except (json.JSONDecodeError, TypeError):
        logger.exception("Failed to decode stored scan results for target '{}'", target_name)
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
        message=f"Stored scan results retrieved for '{target_name}'",
    )


@router.delete(
    "/scan-results",
    summary="Delete the stored scan report and LLM results for a target",
    description=(
        "Remove the persisted dangerous function scan report and the stored "
        "LLM analysis results for the given target name. Use DELETE "
        "/llm-results to remove only the LLM results while keeping the scan "
        "report."
    ),
)
async def delete_scan_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=256, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[str]:
    """Delete the stored scan report and LLM results for a target.

    The persisted scan report is removed together with any stored LLM
    analysis results for the target, so a "Delete" clears both the scan and
    the LLM results. To remove only the LLM results while keeping the scan
    report, use DELETE /llm-results.

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response confirming deletion (or that nothing was stored).

    """
    report_deleted = await ScanReportRepository.delete_for_target(target_name)
    llm_deleted = await LLMResultRepository.delete_for_target(target_name)

    if not report_deleted and not llm_deleted:
        return create_success_response(data="not_found", message=f"No stored scan results for '{target_name}'")

    return create_success_response(
        data="deleted",
        message=f"Stored scan results and LLM results deleted for '{target_name}'",
    )


@router.delete(
    "/llm-results",
    summary="Delete the stored LLM analysis results for a target",
    description=(
        "Remove the persisted LLM analysis results for the given target name. "
        "The stored scan report is not affected; use DELETE /scan-results "
        "to remove that."
    ),
)
async def delete_llm_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=128, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[str]:
    """Delete the stored LLM analysis results for a target.

    Only the persisted LLM analysis rows are removed; the stored scan
    report for the target is kept (delete it via DELETE /scan-results).

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response confirming deletion (or that nothing was stored).

    """
    deleted = await LLMResultRepository.delete_for_target(target_name)

    if not deleted:
        return create_success_response(data="not_found", message=f"No stored LLM results for '{target_name}'")

    return create_success_response(data="deleted", message=f"Stored LLM results deleted for '{target_name}'")


@router.post(
    "/llm-analysis",
    summary="Analyze scan findings with the configured LLM endpoint",
    description=(
        "Send scanner findings to the user-configured OpenAI-compatible chat completions "
        "endpoint for analysis. Results are persisted to the database by default."
    ),
)
@limiter.limit(LLM_ANALYSIS_LIMIT)  # pyright: ignore[reportUnknownMemberType, reportUntypedFunctionDecorator]
async def analyze_dangerous_functions(
    request: Request,
    body: LLMAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Send scan findings to the configured LLM endpoint for analysis.

    The client supplies findings it already obtained from a scan; no re-scan
    is performed. One result per finding is returned, keyed by the finding's
    zero-based index. When save is true (the default), results are upserted
    to the database; a persistence failure is reported via saved=false but
    does not fail the request.

    Args:
        request: FastAPI request object (used for rate limiting).
        body: Analysis request with target name, save flag, and findings.
        current_user: Authenticated user.

    Returns:
        Success response with per-finding results and summary counts.

    Raises:
        HTTPException: 503 LLM_NOT_CONFIGURED when the LLM endpoint is
            disabled or cannot be built from the current configuration.

    """
    llm = await resolve_user_llm_config(current_user.id)
    try:
        analyses = await analyze_findings(llm, [f.model_dump() for f in body.findings])
    except LLMNotConfiguredError as exc:
        logger.warning("LLM analysis rejected: {}", exc)
        raise HTTPException(
            status_code=503,
            detail=create_error_response(
                error_code="LLM_NOT_CONFIGURED",
                error_message=str(exc),
            ).model_dump(),
        ) from exc

    results: dict[str, dict[str, Any]] = {
        str(index): {
            "status": analysis.status,
            "analysis": analysis.analysis,
            "error": analysis.error,
            "model": analysis.model,
            "elapsed_ms": analysis.elapsed_ms,
        }
        for index, analysis in enumerate(analyses)
    }

    total = len(analyses)
    succeeded = sum(1 for analysis in analyses if analysis.status == "success")
    failed = total - succeeded

    saved = False
    if body.save:
        rows = [
            LLMAnalysisResult(
                target_name=body.target_name,
                function_name=finding.function_name,
                containing_function=finding.containing_function,
                entrypoint=finding.entrypoint,
                status=analysis.status,
                analysis=analysis.analysis,
                error=analysis.error,
                model_name=analysis.model,
                elapsed_ms=analysis.elapsed_ms,
            )
            for finding, analysis in zip(body.findings, analyses, strict=True)
        ]
        try:
            await LLMResultRepository.upsert_many(body.target_name, rows)
            saved = True
        except Exception:
            saved = False
            logger.exception("Failed to save LLM analysis results for target '{}'", body.target_name)

    model_name = next(
        (analysis.model for analysis in analyses if analysis.status == "success" and analysis.model),
        llm.model,
    )

    return create_success_response(
        data={
            "target_name": body.target_name,
            "model": model_name,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "saved": saved,
            "results": results,
        },
        message=f"LLM analysis complete: {succeeded}/{total} succeeded",
    )


@router.get(
    "/llm-results",
    summary="Retrieve stored LLM analysis results for a target",
    description="Return the persisted LLM analysis results previously saved for a scanned target.",
)
async def get_llm_results(
    request: Request,
    target_name: Annotated[str, Query(min_length=1, max_length=128, description="Name of the scanned target")],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> SuccessResponse[dict[str, Any]]:
    """Get the stored LLM analysis results for a scanned target.

    Args:
        request: FastAPI request object.
        target_name: Stable name of the scanned target.
        current_user: Authenticated user.

    Returns:
        Success response with the stored results (an empty list is a valid
        success when nothing has been saved yet).

    """
    rows = await LLMResultRepository.get_for_target(target_name)

    results = [
        {
            "function_name": row.function_name,
            "containing_function": row.containing_function,
            "entrypoint": row.entrypoint,
            "status": row.status,
            "analysis": row.analysis,
            "error": row.error,
            "model_name": row.model_name,
            "elapsed_ms": row.elapsed_ms,
            "modified_at": row.modified_at.isoformat(),
        }
        for row in rows
    ]

    return create_success_response(
        data={"target_name": target_name, "count": len(results), "results": results},
        message=f"LLM results retrieved for '{target_name}'",
    )
