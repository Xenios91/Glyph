# Glyph

## An architecture independent binary analysis tool powered by machine learning

Glyph decompiles 32- and 64-bit ELF binaries with Ghidra and applies machine learning and natural language processing techniques to fingerprint functions across system architectures. Beyond cross-architecture function fingerprinting, Glyph provides:

- **Model training & prediction** — train scikit-learn classifiers on known binaries, then use them to identify and classify functions in unknown binaries.
- **Dangerous function scanning** — detect risky API usage against a curated CWE catalog with severity ratings, plus optional LLM-assisted analysis of each finding.
- **Binary similarity** — compute pairwise similarity scores across multiple binaries to surface malware families, shared libraries, and repackaged samples.
- **Code reuse detection** — identify shared code patterns between a source binary and a target binary.
- **Call graph visualization** — explore how functions relate to one another within a binary.
- **Binary library** — persistent, per-user storage and management of uploaded binaries.

All capabilities are available through a modern web UI and a fully authenticated REST API (JWT tokens or API keys), with long-running work executed as background tasks.

## Version 0.3.0

### Features

- LLM-assisted analysis of dangerous function findings via any OpenAI-compatible chat completions endpoint (OpenAI, Ollama, vLLM, and more)
- Per-user LLM endpoint configuration with built-in connectivity testing from the Profile page
- Persistent LLM analysis results with retrieval, per-finding retry, and deletion
- Enhanced dangerous functions scanner UI with per-row AI status badges and an analysis modal
- Health check endpoints (`/health` and `/ready`) for orchestrator integration
- Security hardening: HSTS header, request body size limits, production JWT secret enforcement, and hardened refresh token cookies
- PyGhidra integration to reduce setup requirements

### LLM-Assisted Analysis

Glyph 0.3.0 adds optional LLM-assisted analysis to the dangerous functions scanner. After a scan, findings can be sent to a user-configured OpenAI-compatible chat completions endpoint. For each finding, the LLM reviews the decompiled call site and reports on:

1. **Exploitability** — whether the usage is plausibly exploitable given the taint paths and controls visible in the code
2. **Risk assessment** — confidence level and agreement (or disagreement) with the catalog severity rating, with justification
3. **Remediation** — concrete, actionable fixes for that specific call site

Any server exposing the OpenAI chat completions API works — for example `https://api.openai.com`, or a local runtime such as Ollama or vLLM exposing `/v1/chat/completions`. The endpoint can be configured globally in the `llm` block of [`config.yml`](config.yml), or per user from the **Profile → LLM** tab (with a one-click endpoint connectivity test). Analyses are persisted per target and call site, so previously analyzed findings keep their status badges across sessions and can be re-analyzed or deleted at any time.

> **Note:** Code snippets from your binaries are sent to the configured endpoint when LLM analysis runs. Use a local or trusted endpoint if that is a concern.

**What the LLM can see.** Each analysis is a single chat completions request scoped to one finding. The request contains only:

- The finding's metadata — dangerous function, containing function, entrypoint, category, severity, and CWE
- The catalog description and recommended safe alternative from Glyph's built-in catalog
- The decompiled lines containing the call (call-site context)
- The full decompiled code of the containing function

The LLM does not receive the rest of the binary, other findings, other users' data, or any access to Glyph's database, API, or filesystem — it only sees the prompt text and returns text. The endpoint connectivity test from the Profile page sends a minimal "ok" prompt and no binary data.

See [docs/DANGEROUS_FUNCTIONS.md](docs/DANGEROUS_FUNCTIONS.md) for the full LLM configuration reference and API examples.


### Recognition

![Black Hat Arsenal 2022](https://raw.githubusercontent.com/toolswatch/badges/master/arsenal/usa/2022.svg)

Glyph was also featured in **Black Hat Arsenal 2023** and **Defcon Demo Labs**.

### Continuous Integration

[![CodeQL](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml)
[![Ruff](https://github.com/Xenios91/Glyph/actions/workflows/ruff.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/ruff.yml)

### Resources

- **Wiki**: [Glyph Wiki](https://github.com/Xenios91/Glyph/wiki)
- **API Documentation**: [Interactive Swagger UI](http://localhost:8000/docs)

## Requirements

- Python version 3.11+
- [Ghidra](https://ghidra-sre.org/) 12.0 or later (required for binary analysis via PyGhidra)

## Getting Started

Follow these steps to get Glyph up and running locally.

### 1. Clone the Repository

```bash
git clone https://github.com/Xenios91/Glyph.git
cd Glyph
```

### 2. Install Ghidra

Glyph uses PyGhidra for binary decompilation and analysis. You must install Ghidra before running the application:

1. Download Ghidra from [https://ghidra-sre.org/](https://ghidra-sre.org/)
2. Extract the archive to your desired installation directory
3. Set the `GHIDRA_INSTALL_DIR` environment variable to point to the Ghidra installation directory:

```bash
# Linux/macOS
export GHIDRA_INSTALL_DIR=/opt/ghidra/ghidra_12.0_PUBLIC

# Windows (Command Prompt)
set GHIDRA_INSTALL_DIR=C:\Ghidra\ghidra_12.0_PUBLIC

# Windows (PowerShell)
$env:GHIDRA_INSTALL_DIR="C:\Ghidra\ghidra_12.0_PUBLIC"
```

> **Note:** Replace the path above with your actual Ghidra installation directory. The directory should contain `support/`, `GhidraRun`, and other Ghidra runtime files.

### 3. Set Up a Virtual Environment

```bash
python -m venv glyph_venv
source glyph_venv/bin/activate  # On Windows: glyph_venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install .
```

> **Note:** PyGhidra (used for Ghidra decompilation) is not included in the base install. Install it separately, e.g. `pip install pyghidra`, before running analysis.

### 5. Configure the Application

Before running Glyph, you **must** update the [`config.yml`](config.yml) file with your own settings:

- **`jwt_secret_key`**: Replace the default value (`change-me-in-production`) with a strong, randomly generated secret key. This key is used to sign JWT tokens for authentication and **should never be used in production with the default value**.

Example configuration:

```yaml
cpu_cores: 2
jwt_secret_key: your-strong-random-secret-key-here
llm:
  enabled: false
  base_url: https://api.openai.com
  api_path: /v1/chat/completions
  model: your-model
  api_key: your-key
  timeout_seconds: 120
  temperature: 0.1
  max_concurrent: 5
logging:
  level: INFO
  format: json
  console:
    enabled: true
    level: INFO
    colorize: true
  file:
    path: logs/glyph.log
    rotation: 50 MB
    retention: 10 days
  request_tracing:
    enabled: true
    header_name: X-Request-ID
  module_levels:
    app.auth: INFO
    app.database: WARNING
    app.processing: DEBUG
    uvicorn: INFO
max_file_size_mb: 512
prediction_probability_threshold: 50.0
```

The `llm` block is optional and disabled by default. It configures the OpenAI-compatible endpoint used for LLM-assisted analysis of dangerous function findings. Individual users can override these global defaults with their own endpoint settings from the **Profile → LLM** tab. The full field reference is available in [docs/DANGEROUS_FUNCTIONS.md](docs/DANGEROUS_FUNCTIONS.md).

### 6. Run the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag enables auto-reloading on code changes (useful for development). The server will start on `http://localhost:8000`.

For production, run without `--reload`:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 7. Access the Application

- **Web UI**: Open [http://localhost:8000](http://localhost:8000) in your browser.
- **API Documentation**: Open [http://localhost:8000/docs](http://localhost:8000/docs) to view the interactive Swagger UI.
- **Health Checks**: Open [http://localhost:8000/health](http://localhost:8000/health) for the liveness probe, or [http://localhost:8000/ready](http://localhost:8000/ready) for the readiness probe (useful for Kubernetes and other orchestrators).

## About

Reverse engineering is an important task performed by security researchers to identify vulnerable and malicious functions in IoT (Internet of Things) devices, which are often shared across multiple devices of many system architectures. Common techniques for identifying the reuse of these functions do not perform cross-architecture identification unless specific data, such as unique strings, is available to identify a piece of code.

Utilizing machine learning and natural language processing techniques, Glyph allows you to upload an ELF binary (32 & 64 bit) for cross-architecture function fingerprinting. Upon analysis, a web-based function symbol table is created and presented to the user to aid in the analysis of binary executables and shared objects.

![Main Page](https://i.imgur.com/1xwYFCz.png)
