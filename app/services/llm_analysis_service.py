"""LLM analysis service for Glyph.

Sends dangerous function findings to a user-configured OpenAI-compatible
chat completions endpoint and reports the results back to the caller.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx2 as httpx
from loguru import logger

from app.config.settings import LLMConfig

TEST_PROMPT = "Reply with the single word: ok."


class LLMNotConfiguredError(Exception):
    """Raised when the LLM endpoint is disabled or missing required values."""


class LLMRequestError(Exception):
    """Raised when a request to the LLM endpoint fails."""


@dataclass
class LLMTestResult:
    """Result of a connection test against the configured LLM endpoint."""

    ok: bool
    model: str = ""
    elapsed_ms: int = 0
    error: str = ""


SYSTEM_PROMPT = (
    "You are a senior binary-analysis security engineer reviewing decompiled code for "
    "risky function usage. For the finding provided, answer in concise Markdown: "
    "1) Exploitability: is this usage plausibly exploitable given the taint paths and "
    "controls visible in the code? Explain what you see. "
    "2) Risk assessment: state your confidence and whether you agree or disagree with "
    "the catalog severity, with justification. "
    "3) Remediation: give concrete, actionable fixes for this specific call site. "
    "If the provided code is insufficient to judge, say so explicitly instead of guessing."
)


@dataclass
class FindingAnalysis:
    """Outcome of analyzing a single finding against the configured LLM endpoint."""

    status: Literal["success", "error"]
    analysis: str = ""
    error: str = ""
    model: str = ""
    elapsed_ms: int = 0


def build_endpoint_url(llm: LLMConfig) -> str:
    """Build the full URL of the chat completions endpoint.

    The base URL must be host-only (scheme, hostname, and optional port).
    The configured ``api_path`` is appended. When the configured port equals
    the scheme default it is omitted from the URL.

    Args:
        llm: The LLM configuration to build the URL from.

    Returns:
        The fully qualified endpoint URL.

    Raises:
        LLMNotConfiguredError: If the LLM feature is disabled or the base URL
            is missing or malformed.

    """
    if not llm.enabled:
        raise LLMNotConfiguredError("LLM analysis is disabled")

    base_url = llm.base_url.strip()
    if not base_url:
        raise LLMNotConfiguredError("LLM base URL is not configured")

    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https"):
        raise LLMNotConfiguredError(f"Unsupported URL scheme in base URL: {parts.scheme!r}")
    if not parts.hostname:
        raise LLMNotConfiguredError("LLM base URL has no hostname")

    try:
        url_port = parts.port
    except ValueError:
        raise LLMNotConfiguredError("LLM base URL contains an invalid port") from None

    scheme_default = 443 if parts.scheme == "https" else 80
    port = url_port if url_port is not None else llm.port
    if port is not None and port == scheme_default:
        port = None

    host = parts.hostname
    if ":" in host:
        host = f"[{host}]"
    host_part = f"{host}:{port}" if port is not None else host

    api_path = llm.api_path.strip()
    if api_path and not api_path.startswith("/"):
        api_path = f"/{api_path}"

    return f"{parts.scheme}://{host_part}{api_path}"


async def test_llm_connection(llm: LLMConfig) -> LLMTestResult:
    """Send a minimal prompt to the configured endpoint to verify connectivity.

    Args:
        llm: The LLM configuration to test.

    Returns:
        LLMTestResult describing whether the endpoint responded correctly.

    Raises:
        LLMNotConfiguredError: If the endpoint URL cannot be built from config.

    """
    url = build_endpoint_url(llm)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if llm.api_key:
        headers["Authorization"] = f"Bearer {llm.api_key}"

    payload: dict[str, Any] = {
        "model": llm.model.strip(),
        "temperature": llm.temperature,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
    }
    if llm.max_tokens is not None:
        payload["max_tokens"] = llm.max_tokens

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=llm.timeout_seconds) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            error = f"Request timed out after {llm.timeout_seconds:g}s"
            logger.warning("LLM connection test failed: {}", error)
            return LLMTestResult(ok=False, error=error)
        except httpx.HTTPError as exc:
            error = f"Could not reach endpoint: {type(exc).__name__}"
            logger.warning("LLM connection test failed: {} ({})", error, exc)
            return LLMTestResult(ok=False, error=error)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    if response.status_code != 200:
        error = f"HTTP {response.status_code}: {response.text[:300]}"
        logger.warning("LLM connection test failed: {}", error)
        return LLMTestResult(ok=False, error=error)

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        error = f"Unexpected response format from endpoint ({type(exc).__name__})"
        logger.warning("LLM connection test failed: {}", error)
        return LLMTestResult(ok=False, error=error)

    if not isinstance(content, str) or not content.strip():
        logger.warning("LLM connection test failed: endpoint returned empty content")
        return LLMTestResult(ok=False, error="Endpoint returned empty content")

    model = str(body.get("model") or llm.model)
    logger.info(
        "LLM connection test succeeded: url={} status={} model={} elapsed_ms={}",
        url,
        response.status_code,
        model,
        elapsed_ms,
    )
    return LLMTestResult(ok=True, model=model, elapsed_ms=elapsed_ms)


def build_prompt(finding: dict[str, Any]) -> str:
    """Build the user message describing one scanner finding.

    Args:
        finding: Mapping of scanner finding fields: function_name, containing_function,
            entrypoint, category, severity, cwe, description, safe_alternative,
            usage_context, and containing_function_code.

    Returns:
        The user message text for the chat completions request.

    """
    lines: list[str] = [
        f"Dangerous function: {finding.get('function_name') or 'unknown'}",
        f"Containing function: {finding.get('containing_function') or 'unknown'}",
        f"Entrypoint: {finding.get('entrypoint') or 'unknown'}",
        f"Category: {finding.get('category') or 'unknown'}",
        f"Severity: {finding.get('severity') or 'unknown'}",
        f"CWE: {finding.get('cwe') or 'unknown'}",
    ]
    description = finding.get("description")
    if description:
        lines.append(f"Catalog description: {description}")
    safe_alternative = finding.get("safe_alternative")
    if safe_alternative:
        lines.append(f"Recommended safe alternative: {safe_alternative}")
    usage_context = finding.get("usage_context")
    if usage_context:
        lines.append("Call-site context (decompiled lines containing the call):")
        lines.extend(f"  {line}" for line in usage_context)
    code = finding.get("containing_function_code")
    if code:
        lines.append("Decompiled code of the containing function:")
        lines.append(str(code))
    lines.append("Analyze this call site and answer the three questions above.")
    return "\n".join(lines)


async def analyze_finding(llm: LLMConfig, finding: dict[str, Any]) -> FindingAnalysis:
    """Analyze a single finding with one chat completions call.

    Args:
        llm: The LLM configuration to send the request with.
        finding: Mapping of scanner finding fields (see build_prompt).

    Returns:
        FindingAnalysis with the model response, or an error status carrying the
        human-readable failure reason.

    Raises:
        LLMNotConfiguredError: If the endpoint URL cannot be built from config.

    """
    url = build_endpoint_url(llm)
    function_name = str(finding.get("function_name") or "unknown")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if llm.api_key:
        headers["Authorization"] = f"Bearer {llm.api_key}"

    payload: dict[str, Any] = {
        "model": llm.model.strip(),
        "temperature": llm.temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(finding)},
        ],
    }
    if llm.max_tokens is not None:
        payload["max_tokens"] = llm.max_tokens

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=llm.timeout_seconds) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            error = f"Request timed out after {llm.timeout_seconds:g}s"
            logger.warning("LLM analysis failed ({}): {}", function_name, error)
            return FindingAnalysis(status="error", error=error)
        except httpx.HTTPError as exc:
            error = f"Could not reach endpoint: {type(exc).__name__}"
            logger.warning("LLM analysis failed ({}): {} ({})", function_name, error, exc)
            return FindingAnalysis(status="error", error=error)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    if response.status_code != 200:
        error = f"HTTP {response.status_code}: {response.text[:300]}"
        logger.warning("LLM analysis failed ({}): {}", function_name, error)
        return FindingAnalysis(status="error", error=error)

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        error = f"Unexpected response format from endpoint ({type(exc).__name__})"
        logger.warning("LLM analysis failed ({}): {}", function_name, error)
        return FindingAnalysis(status="error", error=error)

    if not isinstance(content, str) or not content.strip():
        logger.warning("LLM analysis failed ({}): endpoint returned empty content", function_name)
        return FindingAnalysis(status="error", error="Endpoint returned empty content")

    model = str(body.get("model") or llm.model)
    logger.info(
        "LLM analysis succeeded: url={} function={} status={} model={} elapsed_ms={}",
        url,
        function_name,
        response.status_code,
        model,
        elapsed_ms,
    )
    return FindingAnalysis(status="success", analysis=content, model=model, elapsed_ms=elapsed_ms)


async def analyze_findings(
    llm: LLMConfig,
    findings: list[dict[str, Any]],
) -> list[FindingAnalysis]:
    """Analyze every finding, limiting in-flight requests to max_concurrent.

    Args:
        llm: The LLM configuration to send the requests with.
        findings: List of scanner finding mappings (see build_prompt).

    Returns:
        One FindingAnalysis per input finding, in the same order. Individual
        failures are reported in the corresponding result, never raised.

    Raises:
        LLMNotConfiguredError: If the endpoint URL cannot be built from config.

    """
    build_endpoint_url(llm)  # fail fast before scheduling any requests

    if not findings:
        return []

    semaphore = asyncio.Semaphore(llm.max_concurrent)

    async def _bounded(finding: dict[str, Any]) -> FindingAnalysis:
        async with semaphore:
            return await analyze_finding(llm, finding)

    return list(await asyncio.gather(*(_bounded(finding) for finding in findings)))
