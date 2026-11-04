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
| GET | `/api/v1/dangerous-functions/scan-results` | Retrieve the last stored scan report for a target (null data when none) |
| POST | `/api/v1/dangerous-functions/llm-analysis` | Analyze findings with the configured LLM endpoint |
| GET | `/api/v1/dangerous-functions/llm-results` | Retrieve stored LLM analysis results |
| DELETE | `/api/v1/dangerous-functions/llm-results` | Delete stored LLM analysis results for a target (keeps the scan report) |
| DELETE | `/api/v1/dangerous-functions/scan-results` | Delete the stored scan report **and** LLM results for a target |

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

## LLM-Assisted Analysis

Scanner findings can be sent to a user-configured **OpenAI-compatible** chat completions endpoint for deeper, context-aware analysis. For each finding, the LLM reviews the call site and reports on exploitability, its agreement (or disagreement) with the catalog severity rating, and concrete remediation for that specific call site.

### How It Works

1. **Scan** — Run a scan (see above) to obtain findings.
2. **Analyze** — `POST /llm-analysis` sends the scan's `results` array to the configured endpoint. One chat completion request is issued per finding, with parallelism bounded by `max_concurrent`.
3. **Persist** — When `save` is `true` (the default), every result (success and failure) is upserted to the database, keyed by target + function + containing function + entrypoint. Re-running the analysis for the same target updates the existing rows instead of duplicating them.
4. **Retrieve** — `GET /llm-results` returns the stored results for a target.

### LLM Configuration

The LLM endpoint is configured on the **Profile** page (LLM tab, with a one-click connectivity test) or globally in the `llm` block of `config.yml`. Per-user settings override the global defaults:

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | `false` | Enable LLM-assisted analysis |
| `base_url` | `https://api.openai.com` | Base URL of the endpoint (scheme + host) |
| `port` | *(scheme default)* | Explicit port; 443 for HTTPS and 80 for HTTP are omitted from the URL |
| `api_path` | `/v1/chat/completions` | Path of the chat completions endpoint |
| `model` | `gpt-4o-mini` | Model name sent in each request |
| `api_key` | *(empty)* | Sent as `Authorization: Bearer <key>` |
| `timeout_seconds` | `120` | Per-request timeout, 5-600 |
| `temperature` | `0.1` | Sampling temperature, 0.0-2.0 |
| `max_tokens` | *(none)* | Maximum tokens to generate per completion |
| `max_concurrent` | `5` | Maximum parallel analysis requests, 1-20 |

Any server exposing the OpenAI chat completions API works — for example `https://api.openai.com`, or a local runtime such as Ollama or vLLM exposing `/v1/chat/completions`. For each finding, Glyph sends `model`, `temperature`, `max_tokens` (when set), and a `messages` array containing a binary-analysis system prompt plus a user message with the catalog entry, call-site context, and decompiled code; the response text is read from `choices[0].message.content`.

Example `config.yml`:

```yaml
llm:
  enabled: true
  base_url: "https://api.openai.com"
  api_path: "/v1/chat/completions"
  model: "gpt-4o-mini"
  api_key: "sk-..."
  timeout_seconds: 120
  temperature: 0.1
  max_concurrent: 5
```

### Running an Analysis

Send the `results` array from a scan response:

```bash
curl -X POST http://localhost:8000/api/v1/dangerous-functions/llm-analysis \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "target_name": "trojan_detector",
    "save": true,
    "findings": [
      {
        "function_name": "strcpy",
        "containing_function": "FUN_00401230",
        "entrypoint": "0x401230",
        "category": "Buffer Overflow",
        "severity": "high",
        "cwe": "CWE-120",
        "description": "Buffer overflow via unbounded string copy",
        "safe_alternative": "strncpy or strcpy_s",
        "usage_context": ["char buffer[64];", "strcpy(buffer, user_input);"],
        "containing_function_code": "int FUN_00401230(char *param) { ... }"
      }
    ]
  }'
```

**Response:**

```json
{
  "success": true,
  "data": {
    "target_name": "trojan_detector",
    "model": "gpt-4o-mini",
    "total": 1,
    "succeeded": 1,
    "failed": 0,
    "saved": true,
    "results": {
      "0": {
        "status": "success",
        "analysis": "1) Exploitability: ...",
        "error": "",
        "model": "gpt-4o-mini",
        "elapsed_ms": 1832
      }
    }
  },
  "message": "LLM analysis complete: 1/1 succeeded"
}
```

`results` is keyed by the zero-based index of each finding in `findings`. Individual findings can fail (timeout, non-200 HTTP status, unexpected response format) while others succeed; failures are reported per result with `status: "error"` and an `error` message. When the LLM feature is disabled or its base URL is missing/malformed, the endpoint returns `503` with error code `LLM_NOT_CONFIGURED` before any request is made.

### Retrieving Stored Results

```bash
curl "http://localhost:8000/api/v1/dangerous-functions/llm-results?target_name=trojan_detector" \
  -H "Authorization: Bearer <token>"
```

```json
{
  "success": true,
  "data": {
    "target_name": "trojan_detector",
    "count": 1,
    "results": [
      {
        "function_name": "strcpy",
        "containing_function": "FUN_00401230",
        "entrypoint": "0x401230",
        "status": "success",
        "analysis": "1) Exploitability: ...",
        "error": "",
        "model_name": "gpt-4o-mini",
        "elapsed_ms": 1832,
        "modified_at": "2026-09-18T12:04:11.123456+00:00"
      }
    ]
  },
  "message": "LLM results retrieved for 'trojan_detector'"
}
```

An empty `results` list is a valid response when nothing has been saved for the target yet.

### Scanner Page

The scanner page (`/getDangerousFunctions`) exposes LLM analysis directly:

- **Scan** button — enabled once a target is selected and no scan has been performed for it yet. Once a scan has already occurred for the selected target (fresh scan in this session or a stored report restored from the database), the button is disabled to avoid redundant scans. It is re-enabled when the stored results are deleted or a different target is selected.

- **Check with LLM** button — enabled once a scan has produced at least one finding; sends the scan's findings to the configured endpoint and shows progress while running. If the LLM feature is not enabled, an error banner points at the Settings page.
- **LLM column** — each finding row shows a badge: `AI ✓` (green) for a successful analysis, `AI !` (red) for a failed one. The tooltip distinguishes stored results (`Stored <timestamp>`) from fresh ones (`New - just analyzed`).
- **LLM modal** — clicking a badge opens a modal with the finding details, the model used, elapsed time, and the analysis text. Failed findings show the error and a **Retry This Finding** button that re-runs analysis for that single finding.
- **Pre-population** — every scan loads the stored results for the target from `GET /llm-results`, so previously analyzed findings show their badges without re-running the LLM.
- **Stored results banner** — shown only when the selected target actually has a stored scan report (`GET /scan-results` returns non-null data). It offers **View Stored Results**, **Clear LLM Results**, and **Delete**.
- **Clear LLM Results** button — enabled only when the target has stored LLM analysis results; removes only those results (`DELETE /llm-results`), keeping the scan report and its findings.
- **Delete** button — removes both the stored scan report and the LLM analysis results (`DELETE /scan-results`), clearing the results table and LLM badges for the target and hiding the banner.

## Taint Analysis

Taint analysis answers a follow-up question after a scan: *which functions in the scanned binary can reach the dangerous-function call site (the sink)?* This surfaces entry points and input-receiving functions that could plausibly feed attacker-controlled data into the unsafe call.

### How It Works

- **Sink resolution** — Dangerous functions such as `strcpy` or `system` are external libc calls, so they are not nodes in the binary's call graph (the graph only contains the binary's own functions). The taint sink is therefore the in-binary function that *calls* the dangerous function:
  - If `function_name != containing_function` (a call inside a function body) → the sink is `containing_function`.
  - If `function_name == containing_function` (the finding is the function itself) → the sink is `function_name`.
- **Graph construction** — The binary's functions are loaded and a call graph is built via [`CallGraphService.build_graph_from_functions`](../app/services/call_graph_service.py).
- **Input-receiver detection** — A function is flagged as an *input receiver* when its decompiled `raw_code` calls a small built-in set of input functions (the `scanf` family, `gets`, `fgets`, `getline`, `fread`, `read`, `recv`, `receive`, `getchar`).
- **Backward reachability** — A backward breadth-first search from the sink's callers (with a visited set and a depth guard of `MAX_DEPTH = 16`) collects every function that can reach the sink.
- **Path enumeration** — Simple source → … → sink chains are enumerated from entry points and input receivers (capped at 50 paths) so the most relevant taint paths are shown first.
- **Cycle safety** — The traversal is cycle-safe (mutual recursion does not loop indefinitely).

> **Approximation, not proof.** Taint here is *call-graph reachability*, not intra-procedural data-flow tracking. The results are the set of functions that *can* reach the sink ("potentially tainted callers"), not proven data flows from an input to the sink.

### Running Taint Analysis

```bash
curl -X POST http://localhost:8000/api/v1/dangerous-functions/taint-analysis \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "binaryId": 5,
    "function_name": "strcpy",
    "containing_function": "FUN_00401230"
  }'
```

- `binaryId` (required): Database ID of the binary containing the sink.
- `function_name` (required): Dangerous function name from the scan finding.
- `containing_function` (optional): Function that contains the dangerous call site; used as the sink when it differs from `function_name`.

**Response:** `200 OK`

```json
{
  "success": true,
  "data": {
    "binary_id": 5,
    "sink_function": "FUN_00401230",
    "dangerous_function": "strcpy",
    "containing_function": "FUN_00401230",
    "total_tainted_callers": 2,
    "entry_points_reaching_sink": ["main"],
    "input_receivers_reaching_sink": ["read_input"],
    "tainted_callers": [
      {
        "function_name": "main",
        "entrypoint": "0x401000",
        "depth": 2,
        "call_count": 1,
        "is_entry_point": true,
        "is_input_receiver": false
      },
      {
        "function_name": "read_input",
        "entrypoint": "0x402000",
        "depth": 1,
        "call_count": 1,
        "is_entry_point": false,
        "is_input_receiver": true
      }
    ],
    "paths": [["main", "read_input", "FUN_00401230"]],
    "max_depth": 16
  },
  "message": "Taint analysis complete: 2 potentially tainted callers of sink 'FUN_00401230'"
}
```

**Errors:**
- `404` — The binary does not exist, or the resolved sink is not a function of the binary.
- `403` — The binary is owned by a different user.
- `422` — Missing `binaryId` or `function_name`, or an unexpected field is present.

A sink with no callers is a valid (empty) report: `total_tainted_callers` is `0` and the lists are empty.

### Scanner Page

The scanner page (`/getDangerousFunctions`) exposes taint analysis as a per-finding action:

- **Run Taint Analysis** button — lives in the finding-details (context) modal, which opens when a result row is clicked. It is enabled only when the scan target type is **binary** and a row is open; for model or task targets it is disabled with the tooltip *"Taint analysis requires a binary target"* (a `binaryId` only exists for binary targets).
- **Taint modal** — clicking the button POSTs to `POST /taint-analysis` and opens a modal showing the sink, the containing function, the target binary, the count of potentially tainted callers, the entry points and input receivers that can reach the sink, a table of tainted callers, and the enumerated taint paths.

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
- **Taint Analysis Service**: [`app/services/taint_analysis_service.py`](../app/services/taint_analysis_service.py)
- **Call Graph Service**: [`app/services/call_graph_service.py`](../app/services/call_graph_service.py)
- **LLM Analysis Service**: [`app/services/llm_analysis_service.py`](../app/services/llm_analysis_service.py)
- **LLM Result Repository**: [`app/database/llm_result_repository.py`](../app/database/llm_result_repository.py)
- **LLM Configuration**: [`LLMConfig`](../app/config/settings.py) — OpenAI-compatible endpoint settings (the `llm` block in `config.yml`)
- **Key Classes**:
  - [`ScanResult`](../app/services/dangerous_function_scanner.py:21) — Individual finding
  - [`ScanReport`](../app/services/dangerous_function_scanner.py:52) — Aggregated report
  - [`scan_functions()`](../app/services/dangerous_function_scanner.py:136) — Core scanning function
  - [`generate_report()`](../app/services/dangerous_function_scanner.py:325) — Report aggregation
  - [`analyze_findings()`](../app/services/llm_analysis_service.py:424) — LLM analysis fan-out for a batch of findings
  - [`test_llm_connection()`](../app/services/llm_analysis_service.py:194) — LLM endpoint connectivity test
