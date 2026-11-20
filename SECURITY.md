# Security Policy

## Supported Versions

We actively monitor and provide security patches for the following versions of **Glyph**. If you are running an unsupported version, we highly recommend upgrading to the latest release to ensure your environment remains secure.

| Version | Supported          |
| ------- | ------------------ |
| **0.3.x** | :white_check_mark: |
| < 0.1.0   | :x:                |

---

## Reporting a Vulnerability

We take the security of our tools seriously. If you believe you have found a security vulnerability in **Glyph**, please follow the steps below to report it responsibly.

### How to Report
**Do not open a public GitHub issue** for security vulnerabilities. Instead, please report them via one of the following methods:

* **GitHub Private Reporting:** Use the [Private Vulnerability Reporting](https://github.com/xenios91/glyph/security/advisories/new) feature on this repository.
* **Email:** Send a detailed report to the maintainer via the contact information on the **xenios91** profile.

### What to Include
To help us triage the issue quickly, please include:
* A detailed description of the vulnerability.
* Steps to reproduce the issue (proof-of-concept code or scripts are highly encouraged).
* An assessment of the potential impact.

### Our Process
* **Acknowledgement:** You can expect an initial response within **72 hours** of your report.
* **Updates:** We will provide progress updates at least once a week while the issue is being investigated.
* **Public Disclosure:** Once a fix is verified and released, we will coordinate a public disclosure/security advisory. We kindly ask that you refrain from disclosing the vulnerability publicly until a patch has been made available.

---

## SSRF Protection for the LLM Analysis Endpoint

The LLM-assisted analysis feature (`POST /api/v1/dangerous-functions/llm-analysis`) sends scan findings to a user-configured, OpenAI-compatible chat completions endpoint. Because that endpoint is user-controlled, a naive implementation would be an SSRF oracle: an attacker could point it at internal services or the cloud metadata endpoint and read (or at least probe) responses through the error surface.

Glyph therefore validates the configured endpoint against a shared SSRF guard ([`app/utils/ssrf_guard.py`](app/utils/ssrf_guard.py)) **before** any request is made. The guard resolves the host and rejects any address that is not a public, routable address. A rejected endpoint is reported as a proper `503` with error code `LLM_ENDPOINT_BLOCKED` *before* the streaming response is created (no mid-stream failure, no partial response).

### Local LLM carve-out

Local LLM runtimes (the default `base_url` is `http://localhost:11434` for Ollama) must remain usable, so the LLM path opts into a **local carve-out** (`allow_local=True`) on the guard. The carve-out is opt-in and scoped to the LLM path only; every other caller of the shared guard remains strictly public-only.

**Permitted for the LLM endpoint:**

- Loopback: `127.0.0.0/8` and `::1`
- The hostname `localhost` (any port)
- RFC1918 private LAN: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`

**Still blocked (returns `503` `LLM_ENDPOINT_BLOCKED`):**

- Link-local `169.254.0.0/16` — including the cloud metadata endpoint `169.254.169.254` (kept blocked to prevent SSRF-to-metadata)
- All other non-public / reserved / unspecified addresses (e.g. `0.0.0.0`, `::`)
- Anything that would otherwise trip the guard

The carve-out deliberately does **not** cover link-local, CGNAT (`100.64.0.0/10`), or unspecified addresses, so the metadata endpoint and other sensitive local ranges remain inaccessible even from the LLM path.
