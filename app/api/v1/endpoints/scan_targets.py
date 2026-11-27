"""Shared scan-target resolution for the scan endpoints.

Both the dangerous-function and behavioral scan endpoints resolve the scan
target (a model, a prediction task, or a binary) in an identical way: look up
the resource, enforce ownership, and load its functions as a list of dicts.
This module centralizes that logic so the two endpoints do not diverge.

The repositories are passed in by the caller (dependency injection) so each
endpoint module keeps its own references to ``ModelRepository`` /
``PredictionRepository`` / ``FunctionRepository`` / ``BinaryRepository``. That
matters because the endpoint tests patch those names in the *endpoint* module's
namespace; passing them as arguments keeps the patched references in play.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from loguru import logger

from app.auth.dependencies import assert_binary_owned, assert_owned, can_access
from app.database.models import User
from app.utils.common import binary_function_to_dict, functions_to_dicts
from app.utils.secure_deserializer import SecureDeserializationError, secure_load_bytes


@dataclass(frozen=True)
class ScanTarget:
    """A resolved scan target.

    Attributes:
        target_name: Stable name of the scanned target (model/binary/task name).
        functions_data: Function dicts to scan (may be empty).
        report_owner_id: Owner of the produced report (None for unowned/legacy).

    """

    target_name: str
    functions_data: list[dict[str, Any]] = field(default_factory=list)
    report_owner_id: int | None = None


async def resolve_scan_target(
    *,
    model_name: str | None,
    task_name: str | None,
    binary_id: int | None,
    current_user: User,
    model_repository: Any,
    prediction_repository: Any,
    function_repository: Any,
    binary_repository: Any,
) -> ScanTarget:
    """Resolve which target to scan and load its functions.

    Exactly one of ``model_name``, ``task_name`` or ``binary_id`` should be
    provided; ``model_name`` takes precedence, then ``binary_id``, then
    ``task_name`` (matching the historical endpoint behavior). Ownership is
    enforced for the selected resource before any of its data is exposed.

    Args:
        model_name: Name of a stored model to scan.
        task_name: Name of a prediction task to scan.
        binary_id: Database id of a binary to scan.
        current_user: The authenticated user performing the scan.
        model_repository: ``ModelRepository``-like object (``.get(name)``).
        prediction_repository: ``PredictionRepository``-like object
            (``.get_for_user(name, user_id)``).
        function_repository: ``FunctionRepository``-like object
            (``.get_functions(model_name)``).
        binary_repository: ``BinaryRepository``-like object (``.get(binary_id)``
            and ``.get_functions(binary_id)``).

    Returns:
        A :class:`ScanTarget` with the target name, its functions, and the
        report owner id.

    Raises:
        HTTPException: 404 when the target does not exist, 400 when no target
            is provided, 500 when a prediction payload cannot be loaded, and
            403 (via the ownership helpers) when the caller does not own the
            target.

    """
    if model_name:
        model_row = await model_repository.get(model_name)
        if model_row is None:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
        assert_owned(model_row, current_user, "model")

        # Get functions for this model (scoped to accessible rows)
        functions = await function_repository.get_functions(model_name)
        functions = [f for f in functions if can_access(f, current_user)]
        return ScanTarget(
            target_name=model_name,
            functions_data=functions_to_dicts(functions),
            report_owner_id=model_row.user_id,
        )

    if binary_id is not None:
        binary = await binary_repository.get(binary_id=binary_id)
        if binary is None:
            raise HTTPException(status_code=404, detail=f"Binary {binary_id} not found")
        assert_binary_owned(binary, current_user)

        binary_functions = await binary_repository.get_functions(binary_id=binary_id)
        return ScanTarget(
            target_name=binary.name,
            functions_data=[binary_function_to_dict(bf) for bf in binary_functions],
            report_owner_id=binary.uploaded_by,
        )

    if task_name:
        # Get the caller's own prediction with this task name. Scoped to the
        # caller so a same-named row owned by another user is never matched
        # (the old "load all, take first match" could assert the wrong row
        # once task names became per-user).
        prediction = await prediction_repository.get_for_user(task_name, current_user.id)
        if prediction is None:
            raise HTTPException(status_code=404, detail=f"Prediction task '{task_name}' not found")

        # Enforce prediction ownership before exposing any prediction data.
        assert_owned(prediction, current_user, "prediction")

        # Deserialize prediction functions (off the event loop; handles both
        # compressed and legacy uncompressed payloads).
        raw_data: Any = None
        try:
            raw_data = await asyncio.to_thread(secure_load_bytes, prediction.functions_data)
            if not isinstance(raw_data, list):
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
            logger.exception("Failed to deserialize prediction data for task '{}'", task_name)
            raise HTTPException(status_code=500, detail="Failed to load prediction data")
        return ScanTarget(
            target_name=task_name,
            functions_data=raw_data,
            report_owner_id=prediction.user_id,
        )

    raise HTTPException(status_code=400, detail="One of 'modelName', 'taskName', or 'binaryId' must be provided")
