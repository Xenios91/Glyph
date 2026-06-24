# Dangerous Functions Detection

## Overview

The Dangerous Functions feature scans decompiled binary functions against a curated catalog of known insecure/dangerous API calls, identifying potentially vulnerable code patterns with severity ratings, CWE references, and safe alternatives.

## How It Works

1. **Function Loading** — Decompiled functions are loaded from the database for a given model, prediction task, or binary.
2. **Catalog Matching** — Each function's token list is scanned for references to dangerous function names from the catalog.
3. **Context Extraction** — When a match is found, the surrounding code lines are extracted to show how the dangerous function is used.
4. **Report Generation** — Results are aggregated into a report with severity breakdowns and individual findings.

## Dangerous Functions Catalog

The catalog ([`app/services/dangerous_functions_catalog.py`](../app/services/dangerous_functions_catalog.py)) contains entries for well-known dangerous functions organized by vulnerability category:

| Category | Examples |
|----------|----------|
| Memory Manipulation | `VirtualAllocEx`, `WriteProcessMemory`, `HeapCreate` |
| Buffer Overflow | `strcpy`, `strcat`, `sprintf`, `gets`, `scanf` |
| Integer Overflow | `atoi`, `strtol`, `wcstol` |
| Race Conditions | `tmpfile`, `tempnam`, `mktemp` |
| Cryptographic Weakness | `MD5_Init`, `SHA1_Update`, `RC4_setkey` |
| Information Disclosure | `getenv`, `system`, `popen` |
| Privilege Escalation | `SetTokenInformation`, `AdjustTokenPrivileges` |
| Code Injection | `eval`, `exec`, `WScript.Shell` |

Each catalog entry includes:

- **Function Name** — The dangerous API call
- **Category** — Vulnerability category
- **Severity** — Risk level (`critical`, `high`, `medium`, `low`)
- **CWE ID** — Common Weakness Enumeration reference
- **Description** — Why the function is dangerous
- **Safe Alternative** — Recommended replacement

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dangerous-functions/catalog` | List all catalog entries |
| GET | `/api/v1/dangerous-functions/catalog/{name}` | Get single catalog entry |
| GET | `/api/v1/dangerous-functions/available-models` | List scannable models |
| POST | `/api/v1/dangerous-functions/scan` | Run a scan |

### Browsing the Catalog

```bash
curl http://localhost:8000/api/v1/dangerous-functions/catalog \
  -H "Authorization: Bearer <token>"
```

Filter by category:

```bash
curl "http://localhost:8000/api/v1/dangerous-functions/catalog?category=Buffer+Overflow" \
  -H "Authorization: Bearer <token>"
```

### Running a Scan

Scan a model's functions:

```bash
curl -X POST http://localhost:8000/api/v1/dangerous-functions/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"modelName": "trojan_detector"}'
```

Scan a prediction task:

```bash
curl -X POST http://localhost:8000/api/v1/dangerous-functions/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"taskName": "predict_sample_001"}'
```

Scan a binary directly:

```bash
curl -X POST http://localhost:8000/api/v1/dangerous-functions/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"binaryId": 5}'
```

### Scan Response

```json
{
  "success": true,
  "data": {
    "model_name": "trojan_detector",
    "total_functions_scanned": 150,
    "total_found": 12,
    "critical_count": 2,
    "high_count": 5,
    "medium_count": 4,
    "low_count": 1,
    "results": [
      {
        "function_name": "strcpy",
        "containing_function": "FUN_00401230",
        "entrypoint": "0x401230",
        "category": "Buffer Overflow",
        "severity": "high",
        "cwe": "CWE-120",
        "description": "Buffer overflow via unbounded string copy",
        "safe_alternative": "strncpy or strcpy_s",
        "usage_context": [
          "char buffer[64];",
          "strcpy(buffer, user_input);"
        ],
        "containing_function_code": "int FUN_00401230(char *param) { ... }"
      }
    ]
  },
  "message": "Scan completed"
}
```

## Severity Levels

| Severity | Description |
|----------|-------------|
| **Critical** | Direct exploitation path (e.g., remote code execution) |
| **High** | Significant risk with common exploitation patterns |
| **Medium** | Context-dependent risk requiring additional conditions |
| **Low** | Minor risk or deprecated but not directly exploitable |

## Task-Based Scanning

Dangerous function scanning can also be run as a background task through the tasks endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "binary_id": 5,
    "task_type": "dangerous_functions",
    "task_name": "security_audit"
  }'
```

## Implementation Details

- **Scanner Service**: [`app/services/dangerous_function_scanner.py`](../app/services/dangerous_function_scanner.py)
- **Catalog**: [`app/services/dangerous_functions_catalog.py`](../app/services/dangerous_functions_catalog.py)
- **API Endpoints**: [`app/api/v1/endpoints/dangerous_functions.py`](../app/api/v1/endpoints/dangerous_functions.py)
- **Key Classes**:
  - [`ScanResult`](../app/services/dangerous_function_scanner.py:23) — Individual finding
  - [`ScanReport`](../app/services/dangerous_function_scanner.py:52) — Aggregated report
  - [`scan_functions()`](../app/services/dangerous_function_scanner.py:120) — Core scanning function
  - [`generate_report()`](../app/services/dangerous_function_scanner.py:200) — Report aggregation
