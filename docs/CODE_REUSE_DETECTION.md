# Code Reuse Detection

## Overview

The Code Reuse Detection feature identifies shared code patterns between a source binary and a target binary by comparing decompiled function tokens. This is useful for detecting malware families, shared libraries, and code reuse across different binaries.

## How It Works

The code reuse detection pipeline follows these steps:

1. **Source Functions** — Functions from the source binary are already tokenized and filtered (from a previous analysis pipeline run).
2. **Target Loading** — Functions from the target binary are loaded from the database.
3. **Target Tokenization** — Target function code is tokenized using `TokenizeStep`.
4. **Target Filtering** — Tokens are normalized using `FilterStep` (same process as the source).
5. **Pairwise Comparison** — Each source function is compared against each target function.
6. **Match Reporting** — Function pairs exceeding the similarity threshold are reported with their scores.

## Similarity Algorithm

The core similarity metric combines two approaches:

### Jaccard Similarity

Measures the overlap of unique tokens between two functions:

```
jaccard = |A ∩ B| / |A ∪ B|
```

This captures vocabulary similarity but ignores token ordering.

### Longest Common Subsequence (LCS) Ratio

Measures the structural similarity by finding the longest subsequence of tokens that appears in both functions in the same order:

```
lcs_ratio = lcs_length / max(len(A), len(B))
```

The implementation uses a space-optimized dynamic programming approach.

### Combined Score

```
similarity = 0.4 * jaccard + 0.6 * lcs_ratio
```

The LCS component is weighted higher because shared token ordering is a stronger indicator of code reuse than shared vocabulary alone.

## API Usage

Code reuse detection is triggered through the task execution endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "binary_id": 2,
    "task_type": "code_reuse",
    "task_name": "compare_with_sample"
  }'
```

The task runs as a background job. Monitor progress via:

```bash
curl http://localhost:8000/api/v1/tasks/{task_uuid}/status \
  -H "Authorization: Bearer <token>"
```

Retrieve results when complete:

```bash
curl http://localhost:8000/api/v1/tasks/{task_uuid}/results \
  -H "Authorization: Bearer <token>"
```

## Response Format

A completed code reuse task returns matched function pairs:

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "result": {
      "target_binary_id": 2,
      "target_binary_name": "target.exe",
      "matched_functions": [
        {
          "source_function": "func_401000",
          "target_function": "func_00401200",
          "similarity_score": 0.87
        }
      ],
      "total_comparisons": 200,
      "match_count": 5
    }
  }
}
```

## Threshold Configuration

The default match threshold is `0.7`. This can be adjusted when calling the comparison functions programmatically:

```python
from app.services.code_reuse_detector import compare_binaries

result = await compare_binaries(
    source_functions=filtered_source,
    target_binary_id=2,
    match_threshold=0.5,  # Lower threshold = more matches
)
```

## Implementation Details

- **Service**: [`app/services/code_reuse_detector.py`](../app/services/code_reuse_detector.py)
- **Key Functions**:
  - [`compute_similarity()`](../app/services/code_reuse_detector.py:42) — Core similarity metric
  - [`compare_binaries()`](../app/services/code_reuse_detector.py:77) — Full binary comparison pipeline
  - [`_longest_common_subsequence()`](../app/services/code_reuse_detector.py:12) — Space-optimized LCS
- **Pipeline Integration**: Uses `TokenizeStep` and `FilterStep` from the processing pipeline for consistent token normalization
