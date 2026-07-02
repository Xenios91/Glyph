"""Analysis service for Glyph application.

Orchestrates binary analysis pipelines including code reuse detection,
dangerous function scanning, ML training/prediction, and similarity
computation workflows.
"""

from typing import Any

from loguru import logger

from app.database.binary_repository import BinaryRepository
from app.database.models import SimilarityPair
from app.database.similarity_repository import SimilarityRepository
from app.processing.pipeline import PipelineContext
from app.processing.pipeline_configs import (
    PREDICTION_FROM_DB_PIPELINE,
    TRAINING_FROM_DB_PIPELINE,
)
from app.services.binary_similarity_service import (
    BinarySimilarityService,
    SimilarityMatrixEntry,
)
from app.services.code_reuse_detector import compare_binaries
from app.services.dangerous_function_scanner import (
    ScanResult,
    generate_report,
)
from app.services.request_handler import PredictionRequest, TrainingRequest


class AnalysisService:
    """Service for orchestrating binary analysis pipelines.

    Coordinates pipeline execution for code reuse detection, dangerous
    function scanning, ML training/prediction, and similarity computation.
    Uses repository pattern for data access and delegates to specialized
    services for domain-specific logic.
    """

    # --- Code Reuse Analysis ---

    @staticmethod
    async def run_code_reuse_analysis(
        binary_id: int,
    ) -> dict[str, Any]:
        """Execute code reuse detection for a binary against all others.

        Loads raw functions from the source binary, applies in-memory
        tokenization and filtering, then compares against all other
        binaries in the database.

        Args:
            binary_id: Source binary id.

        Returns:
            Dictionary containing comparison results with keys:
            - source_binary_id
            - source_binary_name
            - comparisons (list of match dicts)
        """
        source_functions = await BinaryRepository.get_functions(binary_id)
        if not source_functions:
            logger.warning("No functions found for source binary {}", binary_id)
            return {
                "source_binary_id": binary_id,
                "source_binary_name": None,
                "comparisons": [],
            }

        source_name = await BinaryRepository.get_name(binary_id)

        # Build function dicts for pipeline processing
        source_dicts = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in source_functions
        ]

        # Tokenize and filter in-memory
        context = PipelineContext(
            uuid="",
            binary_path="",
            pipeline_type="code_reuse",
            metadata={"binary_id": binary_id},
        )
        context.set("functions", source_dicts)

        from app.processing.steps import FilterStep, TokenizeStep

        tokenize_step = TokenizeStep()
        context = await tokenize_step.execute(context)
        if context.error:
            logger.error("Tokenization failed for code reuse: {}", context.error)
            return {
                "source_binary_id": binary_id,
                "source_binary_name": source_name,
                "comparisons": [],
            }

        filter_step = FilterStep()
        context = await filter_step.execute(context)
        if context.error:
            logger.error("Filtering failed for code reuse: {}", context.error)
            return {
                "source_binary_id": binary_id,
                "source_binary_name": source_name,
                "comparisons": [],
            }

        filtered_source = context.get("filtered_functions", [])

        # Get all other binaries to compare against
        all_binary_ids = await BinaryRepository.get_all_ids()
        target_ids = [bid for bid in all_binary_ids if bid != binary_id]

        if not target_ids:
            logger.info("No other binaries to compare against for binary {}", binary_id)
            return {
                "source_binary_id": binary_id,
                "source_binary_name": source_name,
                "comparisons": [],
            }

        # Compare against each target binary
        comparisons: list[dict[str, Any]] = []
        for target_id in target_ids:
            result = await compare_binaries(filtered_source, target_id)
            if result:
                comparisons.append(result)  # type: ignore[arg-type]

        logger.info(
            "Code reuse detection completed: {} comparisons for binary {}",
            len(comparisons),
            binary_id,
        )

        return {
            "source_binary_id": binary_id,
            "source_binary_name": source_name,
            "comparisons": comparisons,
        }

    # --- Dangerous Functions Scan ---

    @staticmethod
    async def run_dangerous_functions_scan(
        binary_id: int,
    ) -> dict[str, Any]:
        """Execute dangerous function scanning for a binary.

        Loads raw functions from the binary, applies in-memory tokenization
        and filtering, then scans against the dangerous function catalog.

        Args:
            binary_id: Binary id to scan.

        Returns:
            Dictionary containing scan results.
        """
        binary_functions = await BinaryRepository.get_functions(binary_id)
        if not binary_functions:
            logger.warning("No functions found for binary {}", binary_id)
            return {
                "binary_id": binary_id,
                "binary_name": None,
                "total_functions_scanned": 0,
                "total_found": 0,
                "results": [],
            }

        binary_name = await BinaryRepository.get_name(binary_id)

        # Build function dicts for pipeline processing
        function_dicts = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in binary_functions
        ]

        # Run tokenize and filter steps
        context = PipelineContext(
            uuid="",
            binary_path="",
            pipeline_type="dangerous_functions",
            metadata={"binary_id": binary_id},
        )
        context.set("functions", function_dicts)

        from app.processing.steps import FilterStep, TokenizeStep

        tokenize_step = TokenizeStep()
        context = await tokenize_step.execute(context)
        if context.error:
            logger.error("Tokenization failed for dangerous functions scan: {}", context.error)
            return {
                "binary_id": binary_id,
                "binary_name": binary_name,
                "total_functions_scanned": 0,
                "total_found": 0,
                "results": [],
            }

        filter_step = FilterStep()
        context = await filter_step.execute(context)
        if context.error:
            logger.error("Filtering failed for dangerous functions scan: {}", context.error)
            return {
                "binary_id": binary_id,
                "binary_name": binary_name,
                "total_functions_scanned": 0,
                "total_found": 0,
                "results": [],
            }

        filtered_functions = context.get("filtered_functions", [])

        # Scan for dangerous functions
        model_name = binary_name or f"binary_{binary_id}"
        report = generate_report(model_name, filtered_functions)

        result: dict[str, Any] = {
            "binary_id": binary_id,
            "binary_name": binary_name,
            "model_name": model_name,
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

        logger.info(
            "Dangerous function scan completed: {} dangerous functions found in binary {}",
            report.total_found,
            binary_id,
        )

        return result

    # --- ML Operations ---

    @staticmethod
    async def run_ml_training(
        binary_id: int,
        model_name: str,
    ) -> dict[str, Any]:
        """Execute ML training pipeline from database-stored functions.

        Args:
            binary_id: Binary id to train on.
            model_name: Name for the new model.

        Returns:
            Dictionary with training results including filtered_functions count.
        """
        context = PipelineContext(
            uuid="",
            binary_path="",
            pipeline_type="ml_training",
            metadata={
                "binary_id": binary_id,
                "model_name": model_name,
            },
        )
        context.set("binary_id", binary_id)

        result = await TRAINING_FROM_DB_PIPELINE.execute(context)

        if result.error:
            logger.error("ML training pipeline failed: {}", result.error)
            return {"error": result.error, "filtered_functions": []}

        filtered_functions = result.get("filtered_functions") or []

        # Save functions to model database
        if filtered_functions:
            training_data = {
                "binaryName": f"binary_{binary_id}",
                "functionsMap": {
                    "functions": filtered_functions,
                    "erroredFunctions": result.get("errored_functions", []),
                },
            }
            training_request = TrainingRequest(
                req_uuid="",
                model_name=model_name,
                data=training_data,
            )
            from app.database.function_repository import FunctionRepository

            functions = training_request.get_functions() or []
            if functions:
                await FunctionRepository.save(model_name, functions)
            logger.info(
                "Functions saved for model '{}' ({} functions)",
                model_name,
                len(filtered_functions),
            )

        logger.info("ML training pipeline completed for binary {}", binary_id)
        return {
            "filtered_functions": filtered_functions,
            "errored_functions": result.get("errored_functions", []),
        }

    @staticmethod
    async def run_ml_prediction(
        binary_id: int,
        model_name: str,
        task_name: str,
    ) -> dict[str, Any]:
        """Execute ML prediction pipeline from database-stored functions.

        Args:
            binary_id: Binary id to predict on.
            model_name: Trained model name to use.
            task_name: Name for the prediction task.

        Returns:
            Dictionary with prediction results.
        """
        context = PipelineContext(
            uuid="",
            binary_path="",
            pipeline_type="ml_prediction",
            metadata={
                "binary_id": binary_id,
                "model_name": model_name,
                "task_name": task_name,
            },
        )
        context.set("binary_id", binary_id)

        result = await PREDICTION_FROM_DB_PIPELINE.execute(context)

        if result.error:
            logger.error("ML prediction pipeline failed: {}", result.error)
            return {"error": result.error, "predictions": []}

        filtered_functions = result.get("filtered_functions") or []
        predictions = result.get("predictions") or []

        # Save predictions to database
        if predictions and filtered_functions:
            prediction_data = {
                "binaryName": f"binary_{binary_id}",
                "taskName": task_name,
                "functionsMap": {
                    "functions": filtered_functions,
                    "erroredFunctions": result.get("errored_functions", []),
                },
            }
            prediction_request = PredictionRequest(
                req_uuid="",
                model_name=model_name,
                data=prediction_data,
            )
            from app.database.prediction_repository import PredictionRepository

            functions = prediction_request.get_functions() or []
            if functions and len(functions) == len(predictions):
                for ctr, function in enumerate(functions):
                    updated_function = function.copy()
                    updated_function["prediction"] = predictions[ctr]
                    functions[ctr] = updated_function
                await PredictionRepository.save(task_name, model_name, functions)
            elif functions:
                logger.warning(
                    "Mismatch between functions (%d) and predictions (%d) for task '%s'",
                    len(functions),
                    len(predictions),
                    task_name,
                )
            logger.info(
                "Predictions saved for task '{}' ({} predictions)",
                task_name,
                len(predictions),
            )

        logger.info("ML prediction pipeline completed for binary {}", binary_id)
        return {
            "predictions": predictions,
            "filtered_functions": filtered_functions,
            "errored_functions": result.get("errored_functions", []),
        }

    # --- Similarity Computation ---

    @staticmethod
    async def run_similarity_computation(
        binary_ids: list[int],
        task_name: str,
        match_threshold: float,
        user_id: int,
    ) -> dict[str, Any]:
        """Execute similarity matrix computation across a set of binaries.

        Computes pairwise similarity for all unique binary pairs and
        persists results to the intelligence database.

        Args:
            binary_ids: List of binary IDs to compare.
            task_name: Human-readable name for this computation.
            match_threshold: Minimum similarity score to count a match.
            user_id: ID of the user who initiated the computation.

        Returns:
            Dictionary with computation_id and pairs_computed count.
        """
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

        logger.info(
            "Similarity computation completed: {} pairs from {} binaries (computation_id={})",
            len(entries),
            len(binary_ids),
            computation.id,
        )

        return {
            "computation_id": computation.id,
            "binary_count": len(binary_ids),
            "pairs_computed": len(entries),
        }

    @staticmethod
    async def run_similarity_computation_with_error_handling(
        binary_ids: list[int],
        task_name: str,
        match_threshold: float,
        user_id: int,
    ) -> dict[str, Any]:
        """Execute similarity computation with error state persistence.

        Wrapper around run_similarity_computation that catches errors
        and marks the computation record as failed.

        Args:
            binary_ids: List of binary IDs to compare.
            task_name: Human-readable name for this computation.
            match_threshold: Minimum similarity score to count a match.
            user_id: ID of the user who initiated the computation.

        Returns:
            Dictionary with computation_id and result status.
        """
        computation_id: int | None = None
        try:
            result = await AnalysisService.run_similarity_computation(
                binary_ids=binary_ids,
                task_name=task_name,
                match_threshold=match_threshold,
                user_id=user_id,
            )
            computation_id = result["computation_id"]
            return {**result, "status": "completed"}
        except Exception:
            logger.exception("Similarity computation task failed")
            # Mark computation as errored if it was created
            if computation_id is not None:
                try:
                    await SimilarityRepository.update_status(
                        computation_id=computation_id,
                        status="error",
                    )
                except Exception:
                    logger.exception("Failed to persist error state for similarity computation")
            raise

    # --- Similarity CRUD ---

    @staticmethod
    async def list_similarity_computations(
        user_id: int | None = None,
    ) -> list[Any]:
        """List similarity computations, optionally filtered by user.

        Args:
            user_id: Optional user ID filter.

        Returns:
            List of SimilarityComputation instances.
        """
        return await SimilarityRepository.list_all(computed_by=user_id)

    @staticmethod
    async def get_similarity_computation(
        computation_id: int,
    ) -> Any | None:
        """Retrieve a similarity computation with its pairs.

        Args:
            computation_id: Database id.

        Returns:
            SimilarityComputation instance with loaded pairs, or None.
        """
        return await SimilarityRepository.get(computation_id)

    @staticmethod
    async def get_similarity_computation_with_check(
        computation_id: int,
        user_id: int,
    ) -> Any:
        """Get similarity computation with ownership verification.

        Args:
            computation_id: Database id.
            user_id: Requesting user's ID.

        Returns:
            SimilarityComputation instance.

        Raises:
            Exception: If computation not found or user doesn't own it.
        """
        from app.exceptions import (
            SimilarityComputationAccessError,
            SimilarityComputationNotFoundError,
        )

        comp = await SimilarityRepository.get(computation_id)
        if comp is None:
            raise SimilarityComputationNotFoundError(computation_id)
        if comp.computed_by != user_id:
            raise SimilarityComputationAccessError(computation_id, user_id)
        return comp

    @staticmethod
    async def delete_similarity_computation(
        computation_id: int,
        user_id: int,
    ) -> None:
        """Delete similarity computation with ownership verification.

        Args:
            computation_id: Database id.
            user_id: Requesting user's ID.

        Raises:
            Exception: If computation not found or user doesn't own it.
        """
        from app.exceptions import (
            SimilarityComputationAccessError,
            SimilarityComputationNotFoundError,
        )

        comp = await SimilarityRepository.get(computation_id)
        if comp is None:
            raise SimilarityComputationNotFoundError(computation_id)
        if comp.computed_by != user_id:
            raise SimilarityComputationAccessError(computation_id, user_id)

        await SimilarityRepository.delete(computation_id)
        logger.info("Similarity computation {} deleted by user {}", computation_id, user_id)
