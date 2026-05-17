# Glyph

## An architecture independent binary analysis tool for fingerprinting functions through NLP

## Version 0.1.0

### Features

- PyGhidra integration to reduce setup requirements
- FastAPI-based server
- New UI theme
- Extended configuration options
- Bug fixes and improved Dockerization
- Improved test coverage
- Pydantic implementation
- Anti-XSS protection
- Anti-CSRF protection
- User accounts


![Black Hat Arsenal 2022](https://raw.githubusercontent.com/toolswatch/badges/master/arsenal/usa/2022.svg)

### Black Hat Arsenal 2023 & Defcon Demo Labs

[![CodeQL](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml)
[![Pylint](https://github.com/Xenios91/Glyph/actions/workflows/pylint.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/pylint.yml)

Glyph Wiki: https://github.com/Xenios91/Glyph/wiki

Glyph API Documentation: http://localhost:8000/docs

## Requirements

- Python version 3.11+
- [Ghidra](https://ghidra-sre.org/) 10.x or later (required for binary analysis via PyGhidra)

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
export GHIDRA_INSTALL_DIR=/opt/ghidra/ghidra_11.0_PUBLIC

# Windows (Command Prompt)
set GHIDRA_INSTALL_DIR=C:\Ghidra\ghidra_11.0_PUBLIC

# Windows (PowerShell)
$env:GHIDRA_INSTALL_DIR="C:\Ghidra\ghidra_11.0_PUBLIC"
```

> **Note:** Replace the path above with your actual Ghidra installation directory. The directory should contain `support/`, `GhidraRun`, and other Ghidra runtime files.

### 3. Set Up a Virtual Environment

```bash
python -m venv glyph_venv
source glyph_venv/bin/activate  # On Windows: glyph_venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure the Application

Before running Glyph, you **must** update the [`config.yml`](config.yml) file with your own settings:

- **`jwt_secret_key`**: Replace the default value (`change-me-in-production`) with a strong, randomly generated secret key. This key is used to sign JWT tokens for authentication and **should never be used in production with the default value**.

Example configuration:

```yaml
cpu_cores: 2
jwt_secret_key: your-strong-random-secret-key-here
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

## About

Reverse engineering is an important task performed by security researchers to identify vulnerable functions and malicious functions in IoT (Internet of Things) devices that are often shared across multiple devices of many system architectures. Common techniques to currently identify the reuse of these functions do not perform cross-architecture identification unless specific data such as unique strings are identified that may be of use in identifying a piece of code. Utilizing natural language processing techniques, Glyph allows you to upload an ELF binary (32 & 64 bit) for cross-architecture function fingerprinting, upon analysis, a web-based function symbol table will be created and presented to the user to aid in their analysis of binary executables/shared objects.

![Main Page](https://i.imgur.com/Gb9OFNN.png)
