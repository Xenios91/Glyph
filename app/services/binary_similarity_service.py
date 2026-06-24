"""Binary similarity computation service.

Provides batch pairwise similarity computation across multiple binaries
with result persistence and caching.
"""

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from loguru import logger

from app.services.code_reuse_detector import FunctionDict


@dataclass
class SimilarityMatrixEntry:
    """Single entry in a similarity matrix.

    Attributes:
        binary_a_id: First binary in the pair.
        binary_b_id: Second binary in the pair.
        overall_similarity: Average similarity score across matched functions.
        matched_function_count: Number of function pairs above threshold.
        total_function_comparisons: Total function pairs compared.
    """

    binary_a_id: int
    binary_b_id: int
    overall_similarity: float
    matched_function_count: int
    total_function_comparisons: int


@dataclass
class BinaryFunctionEmbeddings:
    """Pre-computed token embeddings for a single binary.

    Attributes:
        binary_id: Database id of the binary.
        binary_name: Human-readable name of the binary.
        filtered_functions: List of filtered function dicts with token lists.
    """

    binary_id: int
    binary_name: str
    filtered_functions: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())


class BinarySimilarityService:
    """Service for computing and managing binary similarity data.

    Uses the existing compute_similarity() method from code_reuse_detector
    with in-memory tokenization and filtering via the pipeline framework.
    """

    @staticmethod
    async def _prepare_binary_functions(
        binary_id: int,
    ) -> BinaryFunctionEmbeddings | None:
        """Load, tokenize, and filter functions for a single binary.

        Args:
            binary_id: Database id of the binary.

        Returns:
            BinaryFunctionEmbeddings with filtered functions, or None on error.
        """
        from app.database.sql_service import SQLUtil
        from app.processing.pipeline import PipelineContext
        from app.processing.steps import FilterStep, TokenizeStep

        raw_functions = await SQLUtil.get_binary_functions(binary_id)
        if not raw_functions:
            logger.warning("No functions found for binary {}", binary_id)
            return None

        binary_name = await SQLUtil.get_binary_name(binary_id)

        # Build function dicts from raw BinaryFunction records
        function_dicts: list[FunctionDict] = [
            {
                "functionName": bf.function_name,
                "lowAddress": bf.entrypoint,
                "tokenList": bf.raw_code.split(),
                "raw_code": bf.raw_code,
            }
            for bf in raw_functions
        ]

        # Run tokenize and filter pipeline steps in-memory
        context = PipelineContext(
            uuid=f"similarity_prep_{binary_id}",
            binary_path="",
            pipeline_type="similarity",
            metadata={"binary_id": binary_id},
        )
        context.set("functions", function_dicts)

        tokenize_step = TokenizeStep()
        context = await tokenize_step.execute(context)
        if context.error:
            logger.error("Tokenization failed for binary {}: {}", binary_id, context.error)
            return None

        filter_step = FilterStep()
        context = await filter_step.execute(context)
        if context.error:
            logger.error("Filtering failed for binary {}: {}", binary_id, context.error)
            return None

        filtered_functions = context.get("filtered_functions", [])
        return BinaryFunctionEmbeddings(
            binary_id=binary_id,
            binary_name=binary_name or f"binary_{binary_id}",
            filtered_functions=filtered_functions,
        )

    @staticmethod
    async def compute_similarity_matrix(
        binary_ids: list[int],
        match_threshold: float = 0.7,
    ) -> list[SimilarityMatrixEntry]:
        """Compute pairwise similarity for a set of binaries.

        Prepares all binaries upfront (tokenize + filter), then computes
        the full pairwise similarity matrix using the existing
        compute_similarity() from code_reuse_detector.

        Args:
            binary_ids: List of binary IDs to compare.
            match_threshold: Minimum similarity score to count a match.

        Returns:
            List of SimilarityMatrixEntry for all unique pairs.
        """
        from app.services.code_reuse_detector import compute_similarity

        if len(binary_ids) < 2:
            logger.warning("At least 2 binary IDs required for similarity computation")
            return []

        # Prepare all binaries upfront
        embeddings_map: dict[int, BinaryFunctionEmbeddings] = {}
        for bid in binary_ids:
            result = await BinarySimilarityService._prepare_binary_functions(bid)
            if result is not None:
                embeddings_map[bid] = result

        if len(embeddings_map) < 2:
            logger.warning("Fewer than 2 valid binaries available for comparison")
            return []

        # Compute pairwise similarity
        entries: list[SimilarityMatrixEntry] = []
        valid_ids = list(embeddings_map.keys())

        for id_a, id_b in combinations(valid_ids, 2):
            emb_a = embeddings_map[id_a]
            emb_b = embeddings_map[id_b]

            matched_count = 0
            total_comparisons = 0
            similarity_scores: list[float] = []

            for func_a in emb_a.filtered_functions:
                tokens_a = func_a.get("tokenList", [])
                if not tokens_a:
                    continue

                best_score = 0.0
                for func_b in emb_b.filtered_functions:
                    tokens_b = func_b.get("tokenList", [])
                    if not tokens_b:
                        continue

                    total_comparisons += 1
                    score = compute_similarity(tokens_a, tokens_b)
                    if score > best_score:
                        best_score = score

                if best_score >= match_threshold:
                    matched_count += 1
                    similarity_scores.append(best_score)

            overall = (
                round(sum(similarity_scores) / len(similarity_scores), 4)
                if similarity_scores
                else 0.0
            )

            entries.append(
                SimilarityMatrixEntry(
                    binary_a_id=id_a,
                    binary_b_id=id_b,
                    overall_similarity=overall,
                    matched_function_count=matched_count,
                    total_function_comparisons=total_comparisons,
                )
            )

        logger.info(
            "Similarity matrix computed: {} pairs from {} binaries",
            len(entries),
            len(valid_ids),
        )
        return entries

    @staticmethod
    def get_similarity_color(score: float) -> str:
        """Get a color string for a similarity score.

        Uses a white -> yellow -> red gradient for visualization.

        Args:
            score: Similarity score between 0.0 and 1.0.

        Returns:
            Hex color string.
        """
        clamped = max(0.0, min(1.0, score))

        if clamped < 0.5:
            # White to yellow
            t = clamped * 2  # 0 to 1
            r = int(255)
            g = int(255 * (1 - t) + 255 * t)
            b = int(255 * (1 - t))
        else:
            # Yellow to red
            t = (clamped - 0.5) * 2  # 0 to 1
            r = int(255)
            g = int(255 * (1 - t))
            b = int(0)

        return f"#{r:02x}{g:02x}{b:02x}"
