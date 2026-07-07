"""Dangerous function scanner service.

Scans decompiled function data against the dangerous function catalog
to identify potentially vulnerable code patterns. Extracts usage context
from decompiled tokens to show how dangerous functions are called.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.services.dangerous_functions_catalog import (
    Severity,
    get_severity_order,
)


@dataclass
class ScanResult:
    """A single result from a dangerous function scan.

    Attributes:
        function_name: Name of the dangerous function found (e.g., "strcpy").
        containing_function: Name of the function that uses it
            (e.g., "FUN_00401230" or "process_input").
        entrypoint: Memory address/offset of the containing function.
        category: Vulnerability category.
        severity: Risk level.
        cwe: CWE identifier.
        description: Why this function is dangerous.
        safe_alternative: Recommended replacement.
        usage_context: Decompiled code lines showing how the function is used.
        containing_function_code: Full decompiled code of the containing function.

    """

    function_name: str
    containing_function: str
    entrypoint: str
    category: str
    severity: Severity
    cwe: str
    description: str
    safe_alternative: str
    usage_context: list[str] = field(default_factory=lambda: list[str]())
    containing_function_code: str = ""


@dataclass
class ScanReport:
    """Aggregated report from scanning a set of functions.

    Attributes:
        model_name: Name of the model/binary scanned.
        total_functions_scanned: Total number of functions analyzed.
        total_found: Total dangerous function matches.
        critical_count: Number of Critical severity matches.
        high_count: Number of High severity matches.
        medium_count: Number of Medium severity matches.
        low_count: Number of Low severity matches.
        results: Individual scan results sorted by severity.

    """

    model_name: str
    total_functions_scanned: int
    total_found: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    results: list[ScanResult] = field(default_factory=lambda: list[ScanResult]())


def _extract_usage_context(tokens: list[str], dangerous_function_name: str) -> list[str]:
    """Extract lines from decompiled tokens that call the dangerous function.

    Joins the token list into a readable string, splits into lines,
    and returns lines that contain a call to the dangerous function.
    Only matches actual function calls (name followed by '('), not
    occurrences inside string literals or comments.

    Args:
        tokens: List of tokens from the decompiled function.
        dangerous_function_name: Name of the dangerous function to search for.

    Returns:
        List of code lines calling the dangerous function.

    """
    if not tokens:
        return []

    code_text = " ".join(str(t) for t in tokens)
    # Normalize whitespace
    code_text = re.sub(r"\s+", " ", code_text).strip()

    # Split by semicolons to get statement-level granularity
    statements = [s.strip() for s in code_text.split(";") if s.strip()]

    # Match actual function calls: function name followed by '(' with optional whitespace
    # Uses word boundary before the name to avoid matching partial identifiers
    # and requires '(' after to ensure it's a call, not just a mention in a string
    pattern = re.compile(r"\b" + re.escape(dangerous_function_name) + r"\s*\(", re.IGNORECASE)
    matching_lines: list[str] = []

    for stmt in statements:
        if pattern.search(stmt):
            # Limit each line to 300 chars for display
            if len(stmt) > 300:
                stmt = stmt[:300] + "..."
            matching_lines.append(stmt)

    # Also check for function calls with pointer/variable references
    # e.g., if the dangerous function was assigned to a function pointer
    for stmt in statements:
        # Match patterns like: (*func_ptr)(args) where func_ptr might point to dangerous func
        if "(*" in stmt and pattern.search(stmt) and stmt not in matching_lines and len(matching_lines) < 10:
            truncated = stmt[:300] + "..." if len(stmt) > 300 else stmt
            matching_lines.append(truncated)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_lines: list[str] = []
    for line in matching_lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    # Limit to 10 lines max for display
    return unique_lines[:10]


def _scan_function_names(functions: list[dict[str, Any]]) -> list[ScanResult]:
    """Scan function names against the dangerous function catalog.

    Previously detected functions whose names directly match dangerous function
    names from the catalog (e.g., a function named 'strcpy'). However, this
    produced misleading self-references like "sprintf found in sprintf" since
    such functions are typically library exports or import stubs, not code
    that uses the dangerous function.

    The body scan (_scan_function_bodies) already properly detects dangerous
    function calls within function bodies and skips self-references, so this
    name-based scan is no longer needed.

    Args:
        functions: List of function dictionaries.

    Returns:
        Empty list (name-based scan is deprecated in favor of body scan).

    """
    # Name-based scan removed to avoid self-referencing false positives.
    # The body scan (_scan_function_bodies) handles all real detections.
    return []


def scan_functions(functions: list[dict[str, Any]]) -> list[ScanResult]:
    """Scan a list of decompiled functions for calls to dangerous functions.

    Scans each function's name and decompiled token list for references to
    dangerous functions from the catalog.

    Args:
        functions: List of function dictionaries from Ghidra decompilation.
            Each dict should have keys: 'functionName', 'lowAddress', 'tokenList'.

    Returns:
        List of ScanResult sorted by severity (Critical first).

    """
    # Scan function names for direct matches
    name_results = _scan_function_names(functions)

    # Scan function bodies for dangerous function calls
    body_results = _scan_function_bodies(functions)

    # Combine results
    results = name_results + body_results

    # Sort by severity
    results.sort(key=lambda r: get_severity_order(r.severity))

    logger.info(
        "Scan complete: {} dangerous functions found across {} functions scanned",
        len(results),
        len(functions),
    )

    return results


def _get_function_body_context(tokens: list[str], max_lines: int | None = None) -> list[str]:
    """Extract function body context from decompiled tokens.

    Joins tokens into readable lines, limits to max_lines, and truncates
    long lines for display purposes.

    Args:
        tokens: List of tokens from the decompiled function.
        max_lines: Maximum number of lines to return.

    Returns:
        List of code lines from the function body.

    """
    if not tokens:
        return []

    code_text = " ".join(str(t) for t in tokens)
    # Normalize whitespace
    code_text = re.sub(r"\s+", " ", code_text).strip()

    # Split by semicolons to get statement-level granularity
    statements = [s.strip() for s in code_text.split(";") if s.strip()]

    # Truncate long lines
    lines: list[str] = []
    for stmt in statements:
        if len(stmt) > 300:
            stmt = stmt[:300] + "..."
        lines.append(stmt)

    if max_lines is not None:
        lines = lines[:max_lines]

    return lines


def _format_full_function_code(tokens: list[str]) -> str:
    """Format the full decompiled function body from tokens into readable code.

    Uses format_code from app.utils.common for proper indentation and formatting.

    Args:
        tokens: Token list from decompiled function.

    Returns:
        Formatted function code as a multi-line string.

    """
    if not tokens:
        return ""

    from app.utils.common import format_code

    code_text = " ".join(str(t) for t in tokens)
    code_text = re.sub(r"\s+", " ", code_text).strip()

    return format_code(code_text)


def _scan_function_bodies(functions: list[dict[str, Any]]) -> list[ScanResult]:
    """Scan function bodies for calls to dangerous functions.

    Even if a function is not itself named after a dangerous function,
    its body may call one. This scans all function token lists for
    references to dangerous functions.

    Args:
        functions: List of function dictionaries.

    Returns:
        Additional ScanResults for dangerous function calls found in bodies.

    """
    from app.services.dangerous_functions_catalog import FUNCTION_LOOKUP

    results: list[ScanResult] = []
    total_funcs = len(functions)
    funcs_with_tokens = 0
    funcs_with_match = 0

    for func_info in functions:
        func_name = func_info.get("functionName", "")
        tokens = func_info.get("tokenList", [])
        if not tokens:
            continue
        funcs_with_tokens += 1

        code_text = " ".join(str(t) for t in tokens)
        code_text = re.sub(r"\s+", " ", code_text).strip()

        # Check for each dangerous function in the code text
        for _, entry in FUNCTION_LOOKUP.items():
            # Skip if the containing function IS the dangerous function itself
            if func_name.lower() == entry.name.lower():
                continue

            found = False

            # Primary: Match actual function calls - name followed by '(' with optional whitespace
            # This avoids false positives from string literals containing the function name
            # e.g., "The system is down" won't match system()
            call_pattern = re.compile(r"\b" + re.escape(entry.name) + r"\s*\(", re.IGNORECASE)
            if call_pattern.search(code_text):
                found = True

            # Fallback: Check for function pointer assignments that might reference
            # the dangerous function, e.g., "func_ptr = system" or "&system"
            if not found:
                ptr_pattern = re.compile(r"(?:=\s*|&\s*)" + re.escape(entry.name) + r"(?![a-zA-Z0-9_])", re.IGNORECASE)
                if ptr_pattern.search(code_text):
                    # Only consider this a match if it looks like an assignment or address-of
                    # and NOT inside a quoted string (basic heuristic: check for nearby quotes)
                    matches = list(ptr_pattern.finditer(code_text))
                    for m in matches:
                        start = m.start()
                        # Count quotes before this match to detect if inside a string
                        preceding_text = code_text[:start]
                        quote_count = preceding_text.count('"') - preceding_text.count('\\"')
                        if quote_count % 2 == 0:  # Even quotes means we're outside a string
                            found = True
                            break

            if found:
                funcs_with_match += 1
                usage_context = _extract_usage_context(tokens, entry.name)
                result = ScanResult(
                    function_name=entry.name,
                    containing_function=func_name,
                    entrypoint=func_info.get("lowAddress", "0x0"),
                    category=entry.category,
                    severity=entry.severity,
                    cwe=entry.cwe,
                    description=entry.description,
                    safe_alternative=entry.safe_alternative,
                    usage_context=usage_context,
                    containing_function_code=_format_full_function_code(tokens),
                )
                results.append(result)
                logger.debug(
                    "Body scan: found '{}' in function '{}' (entrypoint {})",
                    entry.name,
                    func_name,
                    func_info.get("lowAddress", "0x0"),
                )

    # Sort by severity
    results.sort(key=lambda r: get_severity_order(r.severity))

    logger.info(
        "Body scan: found {} dangerous function calls in {} functions ({} had tokens, {} had matches)",
        len(results),
        total_funcs,
        funcs_with_tokens,
        funcs_with_match,
    )

    return results


def generate_report(
    model_name: str,
    functions: list[dict[str, Any]],
    scan_results: list[ScanResult] | None = None,
) -> ScanReport:
    """Generate a scan report from the scan results.

    Args:
        model_name: Name of the model/binary scanned.
        functions: Original list of functions scanned.
        scan_results: Pre-computed scan results. If None, scan is performed.

    Returns:
        ScanReport with aggregated counts and results.

    """
    if scan_results is None:
        scan_results = scan_functions(functions)

    critical = sum(1 for r in scan_results if r.severity == "Critical")
    high = sum(1 for r in scan_results if r.severity == "High")
    medium = sum(1 for r in scan_results if r.severity == "Medium")
    low = sum(1 for r in scan_results if r.severity == "Low")

    return ScanReport(
        model_name=model_name,
        total_functions_scanned=len(functions),
        total_found=len(scan_results),
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        results=scan_results,
    )
