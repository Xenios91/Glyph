"""Code reuse detection service for comparing binaries.

Provides similarity-based function comparison between decompiled binaries
using token-level analysis (Jaccard similarity + LCS ratio).
"""

from typing import Any, TypedDict

from loguru import logger


class FunctionDict(TypedDict, total=False):
    """Typed dict representing a decompiled function.

    Attributes:
        functionName: Name of the function.
        lowAddress: Entry point address of the function.
        tokenList: List of tokens from decompiled code.
        tokens: Space-separated token string.
        raw_code: Raw decompiled C source code.
        returnType: Return type of the function.
        parameterCount: Number of function parameters.
        highAddress: End address of the function body.
        error: Error message if decompilation failed.
    """

    functionName: str
    lowAddress: str
    tokenList: list[str]
    tokens: str
    raw_code: str
    returnType: str
    parameterCount: int
    highAddress: str
    error: str


class CodeReuseComparisonResult(TypedDict):
    """Result of a code reuse comparison between binaries.

    Attributes:
        target_binary_id: Database id of the target binary.
        target_binary_name: Human-readable name of the target binary.
        matched_functions: List of matched function pairs with similarity scores.
        overall_similarity: Average similarity score across all matched functions.
    """

    target_binary_id: int
    target_binary_name: str
    matched_functions: list[dict[str, Any]]
    overall_similarity: float


def _longest_common_subsequence(a: list[str], b: list[str]) -> int:
    """Compute the length of the longest common subsequence.

    Uses a space-optimized DP approach.

    Args:
        a: First token sequence.
        b: Second token sequence.

    Returns:
        Length of the LCS.
    """
    if not a or not b:
        return 0

    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)

    return prev[n]


def compute_similarity(source_tokens: list[str], target_tokens: list[str], threshold: float = 0.7) -> float:
    """Compute similarity score between two filtered token sequences.

    Combines Jaccard similarity on token sets with LCS ratio on
    token sequences using a weighted formula.

    Args:
        source_tokens: Filtered tokens from the source function.
        target_tokens: Filtered tokens from the target function.
        threshold: Minimum score to consider a match (informational).

    Returns:
        Float similarity score between 0.0 and 1.0.
    """
    if not source_tokens or not target_tokens:
        return 0.0

    # Jaccard similarity on token sets
    source_set = set(source_tokens)
    target_set = set(target_tokens)
    intersection = len(source_set & target_set)
    union = len(source_set | target_set)
    jaccard = intersection / union if union > 0 else 0.0

    # LCS ratio on token sequences
    lcs_length = _longest_common_subsequence(source_tokens, target_tokens)
    max_len = max(len(source_tokens), len(target_tokens))
    lcs_ratio = lcs_length / max_len if max_len > 0 else 0.0

    # Weighted combination (LCS weighted higher for structural similarity)
    return 0.4 * jaccard + 0.6 * lcs_ratio


async def compare_binaries(
    source_functions: list[FunctionDict],
    target_binary_id: int,
    match_threshold: float = 0.7,
) -> CodeReuseComparisonResult | None:
    """Compare source functions against all functions in a target binary.

    Loads raw functions from the target binary, applies in-memory
    tokenization and filtering, then computes pairwise similarity
    scores against the source functions.

    Args:
        source_functions: Pre-filtered source function dicts (from FilterStep
                          output, containing ``tokenList`` and ``tokens`` keys).
        target_binary_id: Database id of the target binary.
        match_threshold: Minimum similarity score to report a match.

    Returns:
        Comparison result dict with target metadata and matched functions,
        or None if the target binary has no functions.
    """
    from app.database.sql_service import SQLUtil
    from app.processing.pipeline import PipelineContext
    from app.processing.steps import FilterStep, TokenizeStep

    # Load target binary functions
    target_functions = await SQLUtil.get_binary_functions(target_binary_id)
    if not target_functions:
        return None

    target_name = await SQLUtil.get_binary_name(target_binary_id)

    # Tokenize and filter target functions in-memory
    target_dicts: list[dict[str, Any]] = [
        {
            "functionName": bf.function_name,
            "lowAddress": bf.entrypoint,
            "tokenList": bf.raw_code.split(),
            "raw_code": bf.raw_code,
        }
        for bf in target_functions
    ]

    target_context = PipelineContext(
        uuid=f"reuse_target_{target_binary_id}",
        binary_path="",
        pipeline_type="code_reuse",
        metadata={"target_binary_id": target_binary_id},
    )
    target_context.set("functions", target_dicts)

    tokenize_step = TokenizeStep()
    target_context = await tokenize_step.execute(target_context)
    if target_context.error:
        logger.error("Target tokenization failed: {}", target_context.error)
        return None

    filter_step = FilterStep()
    target_context = await filter_step.execute(target_context)
    if target_context.error:
        logger.error("Target filtering failed: {}", target_context.error)
        return None

    filtered_target = target_context.get("filtered_functions", [])

    # Pairwise comparison
    matched_functions: list[dict[str, Any]] = []
    similarity_scores: list[float] = []

    for src_func in source_functions:
        src_tokens = src_func.get("tokenList", [])
        src_name = src_func.get("functionName", "unknown")
        src_token_str = src_func.get("tokens", " ".join(src_tokens))

        best_score = 0.0
        best_target_name = ""
        best_tgt_token_str = ""

        for tgt_func in filtered_target:
            tgt_tokens = tgt_func.get("tokenList", [])
            tgt_name = tgt_func.get("functionName", "unknown")
            tgt_token_str = tgt_func.get("tokens", " ".join(tgt_tokens))

            score = compute_similarity(src_tokens, tgt_tokens)
            if score > best_score:
                best_score = score
                best_target_name = tgt_name
                best_tgt_token_str = tgt_token_str

        if best_score >= match_threshold:
            similarity_scores.append(best_score)
            matched_functions.append(
                {
                    "source_function_name": src_name,
                    "target_function_name": best_target_name,
                    "similarity_score": round(best_score, 4),
                    "source_tokens": src_token_str,
                    "target_tokens": best_tgt_token_str,
                }
            )

    overall_similarity = round(sum(similarity_scores) / len(similarity_scores), 4) if similarity_scores else 0.0

    return {
        "target_binary_id": target_binary_id,
        "target_binary_name": target_name or "",
        "matched_functions": matched_functions,
        "overall_similarity": overall_similarity,
    }
