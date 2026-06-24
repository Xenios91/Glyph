# Binary Similarity Analysis

## Overview

The Binary Similarity feature computes pairwise similarity scores across multiple uploaded binaries, enabling analysts to identify related malware families, shared code libraries, or repackaged binaries.

## How It Works

The similarity computation pipeline follows these steps:

1. **Binary Selection** — User selects two or more binaries from the library.
2. **Function Extraction** — For each binary, previously extracted functions are loaded from the database.
3. **Tokenization** — Each function's decompiled code is tokenized using the same `TokenizeStep` used in the main processing pipeline.
4. **Filtering** — Tokens are normalized (address normalization, function/variable name standardization, comment removal) via `FilterStep`.
5. **Pairwise Comparison** — For every unique pair of binaries, each function in binary A is compared against each function in binary B using a combined similarity metric.
6. **Scoring** — Similarity scores are aggregated per binary pair, producing an overall similarity percentage.
7. **Persistence** — Results are saved to the database for later retrieval and dashboard visualization.

## Similarity Metric

The similarity between two functions is computed using a weighted combination of:

- **Jaccard Similarity (40%)** — Set-based overlap of unique tokens. Measures vocabulary similarity.
- **LCS Ratio (60%)** — Longest Common Subsequence ratio. Measures structural/sequential similarity.

```
similarity = 0.4 * jaccard + 0.6 * lcs_ratio
```

The LCS component is weighted higher because it captures the ordering of tokens, which is a stronger indicator of shared code structure.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/tasks/similarity-computation` | Start a new similarity computation |
| GET | `/api/v1/tasks/similarity-computations` | List all saved computations |
| GET | `/api/v1/tasks/similarity-computations/{id}` | Get computation details |
| DELETE | `/api/v1/tasks/similarity-computations/{id}` | Delete a computation |

### Starting a Computation

```bash
curl -X POST http://localhost:8000/api/v1/tasks/similarity-computation \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "binary_ids": [1, 2, 3],
    "task_name": "malware_family_analysis",
    "match_threshold": 0.7
  }'
```

**Response:**

```json
{
  "success": true,
  "data": {
    "task_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "similarity_computation",
    "binary_id": 1,
    "status": "starting"
  },
  "message": "Similarity computation queued successfully"
}
```

### Retrieving Results

```bash
curl http://localhost:8000/api/v1/tasks/similarity-computations/1 \
  -H "Authorization: Bearer <token>"
```

**Response:**

```json
{
  "success": true,
  "data": {
    "computation_id": 1,
    "task_name": "malware_family_analysis",
    "binary_count": 3,
    "total_comparisons": 3,
    "status": "completed",
    "matrix": [
      {
        "binary_a_id": 1,
        "binary_a_name": "sample_a.exe",
        "binary_b_id": 2,
        "binary_b_name": "sample_b.exe",
        "overall_similarity": 0.85,
        "matched_function_count": 12,
        "total_function_comparisons": 150
      },
      {
        "binary_a_id": 1,
        "binary_a_name": "sample_a.exe",
        "binary_b_id": 3,
        "binary_b_name": "sample_c.exe",
        "overall_similarity": 0.23,
        "matched_function_count": 2,
        "total_function_comparisons": 150
      }
    ]
  },
  "message": "Similarity computation retrieved"
}
```

## Similarity Dashboard

The similarity results are visualized in a dedicated dashboard (`/similarity-dashboard`) that displays:

- Pairwise similarity scores in a matrix view
- Matched function counts per binary pair
- Overall similarity percentages
- Filtering by similarity threshold

## Interpretation Guide

| Score Range | Interpretation |
|-------------|----------------|
| 0.90 – 1.00 | Very likely the same binary (repacked or lightly modified) |
| 0.70 – 0.89 | Strongly related (shared libraries, same compiler, same family) |
| 0.40 – 0.69 | Moderately related (some shared code patterns) |
| 0.00 – 0.39 | Unrelated or minimally related |

## Implementation Details

- **Service**: [`app/services/binary_similarity_service.py`](../app/services/binary_similarity_service.py)
- **Core Algorithm**: [`app/services/code_reuse_detector.py`](../app/services/code_reuse_detector.py)
- **Pipeline Steps**: Uses `TokenizeStep` and `FilterStep` from [`app/processing/steps.py`](../app/processing/steps.py)
- **Task Execution**: Queued as background tasks via [`app/api/v1/endpoints/tasks.py`](../app/api/v1/endpoints/tasks.py)
