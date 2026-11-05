# Behavioral Scan

## Overview

The Behavioral Scan feature performs on-demand, malware-behavior analysis of decompiled binary functions against a curated catalog of 24 behavioral signatures (`BEHAV-001`…`BEHAV-024`). Unlike the [Dangerous Functions](DANGEROUS_FUNCTIONS.md) scanner — which flags individual unsafe API calls — the behavioral scanner looks for *behavioral patterns* that malware exhibits: anti-debugging, anti-sandbox / anti-VM evasion, process injection, credential harvesting, network C2, persistence, and obfuscation / anti-analysis.

Each match is reported with a severity rating, the behavior category, the detection method that fired, the containing function, and the matched evidence (the decompiled statements that triggered the signature).

## How It Works

1. **Function Loading** — Decompiled functions are loaded from the database for a given model, prediction task, or binary (the same three target types as the dangerous-function scanner).
2. **Signature Matching** — Each function is evaluated against every catalog signature using the signature's detection method:
   - **`api_call`** — matches a real call (`name(`) in the token list, with a function-pointer fallback (`= name` / `&name` outside string literals) for dynamically resolved or indirect calls.
   - **`string_pattern`** — matches a case-insensitive regular expression against **quoted string literals only** in the decompiled code (so identifiers and comments never match).
   - **`code_heuristic`** — matches a compound regular expression over the normalized function body, used for co-occurrence patterns (e.g., a timing API and a branch in the same function).
   - **`import_check`** — reserved for a future version; no v1 signature uses it.
3. **Evidence Extraction** — When a signature matches, the triggering statements are captured as matched evidence (capped at 10 statements, each truncated to 300 characters) along with the full decompiled code of the containing function.
4. **Report Generation** — Results are aggregated into a report with per-severity counts, sorted by severity (Critical → High → Medium → Low), and persisted to the `behavioral_scan_reports` table so they can be restored when the target is re-selected.

## Behavioral Signature Catalog

The catalog ([`app/services/behavioral_signatures_catalog.py`](../app/services/behavioral_signatures_catalog.py)) contains 24 signatures across 7 categories.

### Anti-Debugging

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-001 | Debugger presence check | Critical | `api_call` — `IsDebuggerPresent` | — |
| BEHAV-002 | Remote debugger check | High | `api_call` — `CheckRemoteDebuggerPresent` | — |
| BEHAV-003 | Process debug-port query | High | `api_call` — `NtQueryInformationProcess` | — |
| BEHAV-004 | Debug output abuse | Low | `api_call` — `OutputDebugString` | — |

### Anti-Sandbox / Anti-VM

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-005 | VM/hypervisor string fingerprint | Medium | `string_pattern` — `VMware\|VirtualBox\|VBox\|QEMU\|Xen\|Hyper-V\|Wine\|sandbox` | T1082 |
| BEHAV-006 | BIOS/hardware registry probe | High | `string_pattern` — `SystemBiosVendor\|SystemBiosDate\|HARDWARE\DESCRIPTION\System\BIOS` | T1012 |
| BEHAV-007 | Timing-based evasion | Medium | `code_heuristic` — timing API co-occurring with a branch | — |
| BEHAV-008 | Device enumeration | Medium | `api_call` — `SetupDiGetClassDevs` | T1082 |

### Process Injection

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-009 | Remote process memory write | Critical | `api_call` — `WriteProcessMemory` | T1055 |
| BEHAV-010 | Remote thread creation | Critical | `api_call` — `CreateRemoteThread` | T1055 |
| BEHAV-011 | Cross-process memory allocation | High | `api_call` — `VirtualAllocEx` | T1055 |

### Credential Harvesting

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-012 | Credential store access | High | `string_pattern` — `Login Data\|cookies\|keychain\|wallet\|id_rsa\|.ssh\|Credentials` | T1555 |
| BEHAV-013 | Secret string probing | Medium | `string_pattern` — `password\|api_key\|token\|AWS_SECRET` | T1552 |
| BEHAV-014 | Identity enumeration | Medium | `api_call` — `GetUserName`, `GetComputerName`, `GetDomainName` | T1033 |

### Network C2

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-015 | Hardcoded C2 address | High | `string_pattern` — `https?://\|IPv4` | T1071 |
| BEHAV-016 | Raw socket beaconing | High | `code_heuristic` — `connect` co-occurring with `send`/`recv` | T1071 |
| BEHAV-017 | WinHTTP C2 usage | Medium | `api_call` — `HttpOpen`, `HttpSendRequest` | T1071.001 |
| BEHAV-018 | Browser user-agent spoofing | Low | `string_pattern` — `Mozilla/` | T1071.001 |

### Persistence

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-019 | Registry run-key persistence | High | `string_pattern` — `CurrentVersion\Run(Once)?` | T1547.001 |
| BEHAV-020 | Windows service installation | High | `api_call` — `CreateService`, `OpenSCManager`, `StartService` | T1543.003 |
| BEHAV-021 | Scheduled task / WMI subscription | High | `string_pattern` — `schtasks\|__EventFilter\|__EventConsumer` | T1053.005 |

### Obfuscation / Anti-Analysis

| ID | Behavior | Severity | Method | MITRE ATT&CK |
|----|----------|----------|--------|--------------|
| BEHAV-022 | Dynamic API resolution | High | `api_call` — `GetProcAddress` | T1027 |
| BEHAV-023 | Runtime code protection/modification | Medium | `api_call` — `VirtualProtect` | T1027 |
| BEHAV-024 | Encoded/indirect command execution | Critical | `string_pattern` — `powershell -enc\|cmd /c\|rundll32\|regsvr32 /s /u /i\|certutil -decode` | T1059.001 |

Each catalog entry includes:

- **Signature ID** — Stable identifier (`BEHAV-001`…`BEHAV-024`)
- **Behavior Name** — Human-readable behavior name
- **Category** — Behavior category
- **Severity** — Risk level (`Critical`, `High`, `Medium`, `Low`)
- **Detection Method** — How the signature is detected
- **Patterns** — Patterns to match, interpreted per detection method
- **Description** — What the behavior means and why it matters
- **MITRE ATT&CK** — Optional technique reference

## API Endpoints

All endpoints live under the `/api/v1/behavioral-scans` prefix and require authentication (Bearer token) except the catalog endpoints.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/behavioral-scans/catalog` | List all catalog entries (optionally filtered by `?category=`) |
| GET | `/api/v1/behavioral-scans/catalog/{signature_id}` | Get a single catalog entry by id or name (404 when unknown) |
| GET | `/api/v1/behavioral-scans/available-models` | List models and prediction tasks available for scanning |
| POST | `/api/v1/behavioral-scans/scan` | Run a scan for a model, prediction task, or binary |
| GET | `/api/v1/behavioral-scans/scan-results` | Retrieve the last stored scan report for a target (null data when none) |
| DELETE | `/api/v1/behavioral-scans/scan-results` | Delete the stored scan report for a target |

### Browsing the Catalog

```bash
curl http://localhost:8000/api/v1/behavioral-scans/catalog \
  -H "Authorization: Bearer <token>"
```

Filter by category:

```bash
curl "http://localhost:8000/api/v1/behavioral-scans/catalog?category=Anti-Debugging" \
  -H "Authorization: Bearer <token>"
```

Get a single entry by id or behavior name:

```bash
curl http://localhost:8000/api/v1/behavioral-scans/catalog/BEHAV-001 \
  -H "Authorization: Bearer <token>"
```

### Listing Available Targets

```bash
curl http://localhost:8000/api/v1/behavioral-scans/available-models \
  -H "Authorization: Bearer <token>"
```

```json
{
  "success": true,
  "data": {
    "models": ["trojan_detector"],
    "prediction_tasks": ["predict_sample_001"]
  },
  "message": "Available targets retrieved"
}
```

### Running a Scan

Scan a model's functions:

```bash
curl -X POST http://localhost:8000/api/v1/behavioral-scans/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"modelName": "trojan_detector"}'
```

Scan a prediction task:

```bash
curl -X POST http://localhost:8000/api/v1/behavioral-scans/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"taskName": "predict_sample_001"}'
```

Scan a binary directly:

```bash
curl -X POST http://localhost:8000/api/v1/behavioral-scans/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"binaryId": 5}'
```

Exactly one of `modelName`, `taskName`, or `binaryId` must be provided; an empty body returns `400`. Unknown targets return `404`, and a target owned by another user returns `403`.

### Scan Response

```json
{
  "success": true,
  "data": {
    "model_name": "trojan_detector",
    "total_functions_scanned": 150,
    "total_found": 3,
    "critical_count": 1,
    "high_count": 2,
    "medium_count": 0,
    "low_count": 0,
    "results": [
      {
        "signature_id": "BEHAV-009",
        "behavior_name": "Remote process memory write",
        "category": "Process Injection",
        "severity": "Critical",
        "detection_method": "api_call",
        "containing_function": "FUN_00401230",
        "entrypoint": "0x401230",
        "mitre_technique": "T1055",
        "description": "Writes data into the memory of another process. ...",
        "matched_evidence": [
          "WriteProcessMemory(hProcess, remote, buf, len, 0);"
        ],
        "containing_function_code": "int FUN_00401230(...) { ... }"
      }
    ]
  },
  "message": "Scan complete: 3 behaviors found"
}
```

Results are sorted by severity (Critical first). `matched_evidence` is capped at 10 statements, each truncated to 300 characters.

### Retrieving Stored Results

```bash
curl "http://localhost:8000/api/v1/behavioral-scans/scan-results?target_name=trojan_detector" \
  -H "Authorization: Bearer <token>"
```

```json
{
  "success": true,
  "data": {
    "model_name": "trojan_detector",
    "total_functions_scanned": 150,
    "total_found": 3,
    "critical_count": 1,
    "high_count": 2,
    "medium_count": 0,
    "low_count": 0,
    "results": [
      { "signature_id": "BEHAV-009", "behavior_name": "Remote process memory write", "category": "Process Injection", "severity": "Critical", "detection_method": "api_call", "containing_function": "FUN_00401230", "entrypoint": "0x401230", "mitre_technique": "T1055", "description": "...", "matched_evidence": ["..."], "containing_function_code": "..." }
    ],
    "modified_at": "2026-09-18T12:04:11.123456+00:00"
  },
  "message": "Stored behavioral scan results retrieved for 'trojan_detector'"
}
```

The `data` payload is `null` when the target has never been scanned. Reports are scoped to the requesting user: a user can only retrieve or delete reports they own.

### Deleting Stored Results

```bash
curl -X DELETE "http://localhost:8000/api/v1/behavioral-scans/scan-results?target_name=trojan_detector" \
  -H "Authorization: Bearer <token>"
```

```json
{
  "success": true,
  "data": "deleted",
  "message": "Stored behavioral scan results deleted for 'trojan_detector'"
}
```

`data` is `"not_found"` when nothing was stored for the target.

## UI Usage

The scanner page (`/getBehavioralScan`, reachable from the **ANALYSIS** navbar dropdown) provides:

- **Target Type** selector — choose **Model (Training Data)**, **Prediction Task**, or **Binary (Library)**.
- **Target** selector — populated with the available targets of the chosen type.
- **Scan** button — enabled once a target is selected and no scan has been performed for it yet. Once a scan has occurred for the selected target (a fresh scan in this session or a stored report restored from the database), the button is disabled to avoid redundant scans. It is re-enabled when the stored results are deleted or a different target is selected.
- **Severity cards** — Critical / High / Medium / Low / Total Found counts, shown once a scan completes.
- **Results table** — one row per finding with the behavior name, category, containing function, and a severity badge. Columns are sortable; rows paginate. Clicking a row opens the **finding detail modal** with the behavior, category, containing function, severity, MITRE ATT&CK technique, description, matched evidence, and the containing function's decompiled code.
- **Stored results banner** — shown when the selected target has a stored report; offers **View Stored Results** and **Delete**.

Unlike the dangerous-functions page, the behavioral scan page has **no LLM analysis and no taint-analysis controls** — it is a pure signature-based scan.

## Limitations

- **ELF-only uploads** — The binary library (and therefore binary-target scans) only accepts ELF binaries. The catalog's signatures are largely Windows-API oriented, so a Windows PE sample cannot be uploaded and scanned directly; model and prediction targets (built from previously analyzed ELF functions) are the primary scan path.
- **No import-table checks in v1** — The `import_check` detection method is reserved for a future version; no v1 signature uses it. Behavior that is only visible in a binary's import table (and not in decompiled function bodies) is not detected.
- **String and heuristic signatures are heuristic** — `string_pattern` and `code_heuristic` signatures are inherently false-positive prone. A benign binary that references a string like `Mozilla/` (BEHAV-018) or contains an IP literal (BEHAV-015) will be flagged even without malicious intent. Treat these findings as indicators to investigate, not verdicts.
- **Decompiled-code fidelity** — Detection operates on decompiled C-like code. Obfuscated or heavily inlined code may evade `api_call` and `code_heuristic` matches that depend on recognizable call syntax.
- **Evidence caps** — Matched evidence is capped at 10 statements of 300 characters each; very large functions may have evidence truncated.

## How It Differs from the Dangerous Function Scan

| Aspect | Dangerous Function Scan | Behavioral Scan |
|--------|------------------------|-----------------|
| **Unit of analysis** | Individual unsafe API calls (`strcpy`, `system`, …) | Behavioral patterns across a function (anti-debug, injection, C2, …) |
| **Catalog** | Unsafe functions with CWE + safe alternatives | 24 behavioral signatures across 7 categories with MITRE ATT&CK |
| **Detection** | Token matching on function names | `api_call`, `string_pattern`, `code_heuristic` (co-occurrence) |
| **Follow-up tools** | LLM-assisted analysis + taint analysis | None (pure signature scan) |
| **Report persistence** | `scan_reports` table | `behavioral_scan_reports` table |
| **Endpoints** | `/api/v1/dangerous-functions/…` | `/api/v1/behavioral-scans/…` |
| **UI page** | `/getDangerousFunctions` | `/getBehavioralScan` |

The two scanners are complementary: the dangerous-function scan surfaces specific vulnerable API usage, while the behavioral scan surfaces malware-like *behaviors* (evasion, injection, persistence, C2) that may not involve any single "unsafe" function.

## Implementation Details

- **Scanner Service**: [`app/services/behavioral_scanner.py`](../app/services/behavioral_scanner.py)
- **Catalog**: [`app/services/behavioral_signatures_catalog.py`](../app/services/behavioral_signatures_catalog.py)
- **API Endpoints**: [`app/api/v1/endpoints/behavioral_scans.py`](../app/api/v1/endpoints/behavioral_scans.py)
- **Report Model**: [`BehavioralScanReport`](../app/database/models.py) — `behavioral_scan_reports` table
- **Report Repository**: [`app/database/behavioral_scan_report_repository.py`](../app/database/behavioral_scan_report_repository.py)
- **UI**: [`templates/get_behavioral_scan.html`](../templates/get_behavioral_scan.html), [`static/js/behavioral_scan.js`](../static/js/behavioral_scan.js), [`static/css/behavioral_scan_style.css`](../static/css/behavioral_scan_style.css)
- **Key Classes / Functions**:
  - [`BehavioralSignatureEntry`](../app/services/behavioral_signatures_catalog.py:31) — A single catalog signature
  - [`BehavioralScanResult`](../app/services/behavioral_scanner.py) — Individual finding
  - [`BehavioralScanReport`](../app/services/behavioral_scanner.py) — Aggregated report
  - [`scan_functions()`](../app/services/behavioral_scanner.py) — Core scanning function
  - [`generate_report()`](../app/services/behavioral_scanner.py) — Report aggregation and severity sorting
