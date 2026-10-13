"""Background task runner functions for Glyph API v1.

Contains the pipeline execution functions invoked by the task endpoints
in ``app.api.v1.endpoints.tasks`` via ``BackgroundTasks``.
"""

from typing import Any

from loguru import logger

from app.api.types import TaskType
from app.database.models import SimilarityPair
from app.processing.task_management import TaskManager
from app.services.prediction_service import PredictionService
from app.utils.background_tasks import create_background_task, remove_task_delayed
from app.utils.common import binary_function_to_dict
from app.utils.request_context import (
    CapturedContext,
    clear_request_context,
    restore_request_context,
)


async def run_code_reuse_task(
    binary_id: int,
    task_uuid: str,
    task_name: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute code reuse detection pipeline.

    Loads raw functions from the source binary, applies in-memory
    tokenization and filtering, then compares against all other
    binaries in the database.

    Args:
        binary_id: Source binary id.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        captured_ctx: Captured request context.

    """
    from app.database.binary_repository import BinaryRepository
    from app.processing.pipeline import PipelineContext
    from app.processing.steps import FilterStep, TokenizeStep
    from app.services.code_reuse_detector import compare_binaries

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Load source binary functions
        source_functions = await BinaryRepository.get_functions(binary_id)
        if not source_functions:
            TaskManager.set_status(task_uuid, "error")
            logger.error("No functions found for source binary {}", binary_id)
            return

        source_name = await BinaryRepository.get_name(binary_id)

        # Tokenize and filter source functions in-memory
        source_context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type="code_reuse",
            metadata={"binary_id": binary_id, "task_name": task_name},
        )

        source_dicts = [binary_function_to_dict(bf) for bf in source_functions]
        source_context.set("functions", source_dicts)

        tokenize_step = TokenizeStep()
        source_context = await tokenize_step.execute(source_context)
        if source_context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Tokenization failed: {}", source_context.error)
            return

        filter_step = FilterStep()
        source_context = await filter_step.execute(source_context)
        if source_context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Filtering failed: {}", source_context.error)
            return

        filtered_source = source_context.get("filtered_functions", [])

        # Get all other binaries to compare against
        all_binary_ids = await BinaryRepository.get_all_ids()
        target_ids = [bid for bid in all_binary_ids if bid != binary_id]

        if not target_ids:
            logger.info("No other binaries to compare against for binary {}", binary_id)
            TaskManager.set_status(task_uuid, "completed")
            # Store empty results
            TaskManager.set_task_result(
                task_uuid,
                {
                    "task_uuid": task_uuid,
                    "source_binary_id": binary_id,
                    "source_binary_name": source_name,
                    "comparisons": [],
                },
            )
            return

        # Compare against each target binary
        comparisons: list[dict[str, Any]] = []
        for target_id in target_ids:
            result = await compare_binaries(filtered_source, target_id)
            if result:
                comparisons.append(result)  # type: ignore[arg-type]

        TaskManager.set_status(task_uuid, "completed")

        results = {
            "task_uuid": task_uuid,
            "source_binary_id": binary_id,
            "source_binary_name": source_name,
            "comparisons": comparisons,
        }
        TaskManager.set_task_result(task_uuid, results)

        logger.info(
            "Code reuse detection completed: {} comparisons for binary {}",
            len(comparisons),
            binary_id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Code reuse task failed")
        raise
    finally:
        create_background_task(remove_task_delayed(task_uuid))
        clear_request_context()


async def run_dangerous_functions_task(
    binary_id: int,
    task_uuid: str,
    task_name: str,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute dangerous function scanning pipeline.

    Loads raw functions from the binary, applies in-memory tokenization
    and filtering, then scans against the dangerous function catalog.

    Args:
        binary_id: Binary id to scan.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        captured_ctx: Captured request context.

    """
    from app.database.binary_repository import BinaryRepository
    from app.processing.pipeline import PipelineContext
    from app.processing.steps import FilterStep, TokenizeStep
    from app.services.dangerous_function_scanner import generate_report

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Load binary functions
        binary_functions = await BinaryRepository.get_functions(binary_id)
        if not binary_functions:
            TaskManager.set_status(task_uuid, "error")
            logger.error("No functions found for binary {}", binary_id)
            return

        binary_name = await BinaryRepository.get_name(binary_id)

        # Build function dicts for pipeline processing
        function_dicts = [binary_function_to_dict(bf) for bf in binary_functions]

        # Run tokenize and filter steps
        context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type="dangerous_functions",
            metadata={"binary_id": binary_id, "task_name": task_name},
        )
        context.set("functions", function_dicts)

        tokenize_step = TokenizeStep()
        context = await tokenize_step.execute(context)
        if context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Tokenization failed: {}", context.error)
            return

        filter_step = FilterStep()
        context = await filter_step.execute(context)
        if context.error:
            TaskManager.set_status(task_uuid, "error")
            logger.error("Filtering failed: {}", context.error)
            return

        filtered_functions = context.get("filtered_functions", [])

        # Scan for dangerous functions
        report = generate_report(binary_name or f"binary_{binary_id}", filtered_functions)

        TaskManager.set_status(task_uuid, "completed")

        # Store results
        result = {
            "task_uuid": task_uuid,
            "binary_id": binary_id,
            "binary_name": binary_name,
            "model_name": binary_name or f"binary_{binary_id}",
            "total_functions_scanned": report.total_functions_scanned,
            "total_found": report.total_found,
            "critical_count": report.critical_count,
            "high_count": report.high_count,
            "medium_count": report.medium_count,
            "low_count": report.low_count,
            "results": [
                {
                    "function_name": r.function_name,
                    "containing_function": r.containing_function,
                    "entrypoint": r.entrypoint,
                    "category": r.category,
                    "severity": r.severity,
                    "cwe": r.cwe,
                    "description": r.description,
                    "safe_alternative": r.safe_alternative,
                    "usage_context": r.usage_context,
                    "containing_function_code": r.containing_function_code,
                }
                for r in report.results
            ],
        }
        TaskManager.set_task_result(task_uuid, result)

        logger.info(
            "Dangerous function scan completed: {} dangerous functions found in binary {}",
            report.total_found,
            binary_id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Dangerous function scan task failed")
        raise
    finally:
        create_background_task(remove_task_delayed(task_uuid))
        clear_request_context()


async def run_ml_task(
    binary_id: int,
    task_uuid: str,
    task_type: TaskType,
    task_name: str,
    model_name: str,
    ml_class_type: str | None = None,
    captured_ctx: CapturedContext | None = None,
    user_id: int | None = None,
) -> None:
    """Execute ML training or prediction pipeline.

    Loads raw functions from the binary, applies in-memory processing,
    and trains or predicts using the specified model.

    Args:
        binary_id: Binary id to analyze.
        task_uuid: Task UUID for progress tracking.
        task_type: ml_training or ml_prediction.
        task_name: Human-readable task name.
        model_name: ML model name.
        ml_class_type: Classification type (for training).
        captured_ctx: Captured request context.

    """
    from app.processing.pipeline import PipelineContext

    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        pipeline_type = "ml_training" if task_type == TaskType.ML_TRAINING else "ml_prediction"

        context = PipelineContext(
            uuid=task_uuid,
            binary_path="",
            pipeline_type=pipeline_type,
            metadata={
                "binary_id": binary_id,
                "model_name": model_name,
                "task_name": task_name,
                "ml_class_type": ml_class_type,
                "user_id": user_id,
            },
        )
        context.set("binary_id", binary_id)

        if task_type == TaskType.ML_TRAINING:
            from app.processing.pipeline_configs import TRAINING_FROM_DB_PIPELINE

            pipeline = TRAINING_FROM_DB_PIPELINE
        else:
            from app.processing.pipeline_configs import PREDICTION_FROM_DB_PIPELINE

            pipeline = PREDICTION_FROM_DB_PIPELINE

        result = await pipeline.execute(context)

        if result.error:
            TaskManager.set_status(task_uuid, "error")
            logger.opt(exception=result.exc_info).error("ML pipeline failed: {}", result.error)
        else:
            # Persist results to the database
            filtered_functions = result.get("filtered_functions")
            if task_type == TaskType.ML_TRAINING:
                if filtered_functions:
                    from app.database.function_repository import FunctionRepository
                    from app.services.request_handler import TrainingRequest

                    training_data = {
                        "binaryName": f"binary_{binary_id}",
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    try:
                        training_request = TrainingRequest(
                            req_uuid=task_uuid,
                            model_name=model_name,
                            data=training_data,
                        )
                        functions = training_request.get_functions() or []
                        if functions:
                            await FunctionRepository.save(model_name, functions, user_id=user_id)
                        logger.info(
                            "Functions saved for model '{}' ({} functions)",
                            model_name,
                            len(filtered_functions),
                        )
                    except Exception:
                        logger.exception("Failed to save functions for model '{}'", model_name)
                        raise
            elif task_type == TaskType.ML_PREDICTION:
                predictions = result.get("predictions")
                if predictions and filtered_functions:
                    from app.services.request_handler import PredictionRequest

                    prediction_data = {
                        "binaryName": f"binary_{binary_id}",
                        "taskName": task_name,
                        "functionsMap": {
                            "functions": filtered_functions,
                            "erroredFunctions": result.get("errored_functions", []),
                        },
                    }
                    try:
                        prediction_request = PredictionRequest(
                            req_uuid=task_uuid,
                            model_name=model_name,
                            data=prediction_data,
                        )
                        prediction_request.user_id = user_id
                        await PredictionService.save_prediction_functions(prediction_request, predictions)
                        logger.info(
                            "Predictions saved for task '{}' ({} predictions)",
                            task_name,
                            len(predictions),
                        )
                    except Exception:
                        logger.exception("Failed to save predictions for task '{}'", task_name)
                        raise

            TaskManager.set_status(task_uuid, "completed")
            logger.info("ML {} pipeline completed for binary {}", task_type.value, binary_id)

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("ML task failed")
        raise
    finally:
        create_background_task(remove_task_delayed(task_uuid))
        clear_request_context()


async def run_similarity_computation_task(
    binary_ids: list[int],
    task_uuid: str,
    task_name: str,
    match_threshold: float,
    user_id: int,
    captured_ctx: CapturedContext | None = None,
) -> None:
    """Execute similarity matrix computation across a set of binaries.

    Computes pairwise similarity for all unique binary pairs using the
    existing compute_similarity() method with in-memory tokenization
    and filtering. Results are persisted to the intelligence database.

    Args:
        binary_ids: List of binary IDs to compare.
        task_uuid: Task UUID for progress tracking.
        task_name: Human-readable task name.
        match_threshold: Minimum similarity score to count a match.
        user_id: ID of the user who initiated the computation.
        captured_ctx: Captured request context.

    """
    from app.database.similarity_repository import SimilarityRepository
    from app.services.binary_similarity_service import BinarySimilarityService

    computation: Any | None = None
    try:
        if captured_ctx is not None:
            restore_request_context(captured_ctx, override_task_id=task_uuid)

        TaskManager.set_status(task_uuid, "processing")

        # Create the computation record
        computation = await SimilarityRepository.create(
            task_name=task_name,
            computed_by=user_id,
            binary_count=len(binary_ids),
        )

        # Compute the similarity matrix
        entries = await BinarySimilarityService.compute_similarity_matrix(
            binary_ids=binary_ids,
            match_threshold=match_threshold,
        )

        # Persist pair results
        pairs = [
            SimilarityPair(
                binary_a_id=entry.binary_a_id,
                binary_b_id=entry.binary_b_id,
                overall_similarity=entry.overall_similarity,
                matched_function_count=entry.matched_function_count,
                total_function_comparisons=entry.total_function_comparisons,
            )
            for entry in entries
        ]
        await SimilarityRepository.save_pairs(
            computation_id=computation.id,
            pairs=pairs,
        )

        # Mark computation completed
        await SimilarityRepository.update_status(
            computation_id=computation.id,
            status="completed",
            total_comparisons=len(entries),
        )

        TaskManager.set_status(task_uuid, "completed")

        # Store lightweight result reference
        result = {
            "task_uuid": task_uuid,
            "computation_id": computation.id,
            "binary_count": len(binary_ids),
            "pairs_computed": len(entries),
        }
        TaskManager.set_task_result(task_uuid, result)

        logger.info(
            "Similarity computation completed: {} pairs from {} binaries (computation_id={})",
            len(entries),
            len(binary_ids),
            computation.id,
        )

    except Exception:
        TaskManager.set_status(task_uuid, "error")
        logger.exception("Similarity computation task failed")
        # Mark computation as errored if it was created
        if computation is not None:
            try:
                await SimilarityRepository.update_status(
                    computation_id=computation.id,
                    status="error",
                )
            except Exception:
                logger.exception("Failed to persist error state for similarity computation")
        raise
    finally:
        create_background_task(remove_task_delayed(task_uuid))
        clear_request_context()
