"""Behavioral scanner service.

Scans decompiled function data against the behavioral signature catalog to
identify malware-associated behaviors (anti-debugging, anti-sandbox/anti-VM,
process injection, credential harvesting, network C2, persistence, and
obfuscation/anti-analysis). Extracts usage context from decompiled tokens to
show how each detected behavior manifests in the code.

Pattern semantics per detection method:
    - ``api_call``: matches a real call (``name(``) plus a function-pointer
      fallback (``= name`` / ``&name`` outside string literals), mirroring the
      dangerous function scanner's matching approach.
    - ``string_pattern``: case-insensitive regex matched only against string
      literals (quoted segments) in the decompiled code.
    - ``code_heuristic``: compound regex over the normalized function body
      (e.g., two APIs co-occurring in one function).
    - ``import_check``: reserved; no v1 entries use it.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Final

from loguru import logger

from app.services.behavioral_signatures_catalog import (
    BehavioralSignatureEntry,
    DetectionMethod,
    Severity,
    get_all_entries,
    get_severity_order,
)

# Evidence display limits: at most this many statements, each at most this
# many characters (mirrors the dangerous function scanner).
MAX_EVIDENCE_STATEMENTS = 10
MAX_EVIDENCE_LENGTH = 300

# Quoted string literals, including wide (L"...") literals. Handles escaped
# quotes and backslashes inside the literal.
_STRING_LITERAL_RE = re.compile(r'(?:L|l)?"((?:[^"\\]|\\.)*)"')


@dataclass
class BehavioralScanResult:
    """A single result from a behavioral scan.

    Attributes:
        signature_id: Stable id of the matched signature (e.g., "BEHAV-001").
        behavior_name: Human-readable behavior name.
        category: Behavior category.
        severity: Risk level.
        detection_method: How the signature was detected.
        containing_function: Name of the function exhibiting the behavior.
        entrypoint: Memory address/offset of the containing function.
        mitre_technique: Optional MITRE ATT&CK technique id.
        description: What the behavior means and why it matters.
        matched_evidence: Decompiled statements that triggered the signature
            (capped at 10 statements, 300 chars each).
        containing_function_code: Full decompiled code of the containing function.

    """

    signature_id: str
    behavior_name: str
    category: str
    severity: Severity
    detection_method: DetectionMethod
    containing_function: str
    entrypoint: str
    mitre_technique: str
    description: str
    matched_evidence: list[str] = field(default_factory=lambda: list[str]())
    containing_function_code: str = ""


@dataclass
class BehavioralScanReport:
    """Aggregated report from scanning a set of functions.

    Attributes:
        model_name: Name of the model/binary scanned.
        total_functions_scanned: Total number of functions analyzed.
        total_found: Total behavioral matches.
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
    results: list[BehavioralScanResult] = field(default_factory=lambda: list[BehavioralScanResult]())


@dataclass(frozen=True)
class _CompiledSignature:
    """A catalog entry with its patterns precompiled once at module import.

    Attributes:
        entry: The catalog entry this was compiled from.
        api_call_patterns: Compiled call patterns (``\\bname\\s*\\(``).
        api_ptr_patterns: Compiled function-pointer fallback patterns.
        string_patterns: Compiled case-insensitive string-literal regexes.
        heuristic_patterns: Compiled compound body regexes.

    """

    entry: BehavioralSignatureEntry
    api_call_patterns: tuple[re.Pattern[str], ...] = ()
    api_ptr_patterns: tuple[re.Pattern[str], ...] = ()
    string_patterns: tuple[re.Pattern[str], ...] = ()
    heuristic_patterns: tuple[re.Pattern[str], ...] = ()


def _compile_signature(entry: BehavioralSignatureEntry) -> _CompiledSignature:
    """Precompile the patterns of a single catalog entry.

    Args:
        entry: The catalog entry to compile.

    Returns:
        A _CompiledSignature with the patterns compiled per detection method.

    """
    if entry.detection_method == "api_call":
        call_patterns = tuple(
            re.compile(r"\b" + re.escape(pattern) + r"\s*\(", re.IGNORECASE) for pattern in entry.patterns
        )
        ptr_patterns = tuple(
            re.compile(r"(?:=\s*|&\s*)" + re.escape(pattern) + r"(?![a-zA-Z0-9_])", re.IGNORECASE)
            for pattern in entry.patterns
        )
        return _CompiledSignature(entry=entry, api_call_patterns=call_patterns, api_ptr_patterns=ptr_patterns)
    if entry.detection_method == "string_pattern":
        string_patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern in entry.patterns)
        return _CompiledSignature(entry=entry, string_patterns=string_patterns)
    if entry.detection_method == "code_heuristic":
        heuristic_patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern in entry.patterns)
        return _CompiledSignature(entry=entry, heuristic_patterns=heuristic_patterns)
    # import_check is reserved for a future version; no v1 entries use it.
    return _CompiledSignature(entry=entry)


# All signatures compiled once at module import.
_COMPILED_SIGNATURES: Final[tuple[_CompiledSignature, ...]] = tuple(
    _compile_signature(entry) for entry in get_all_entries()
)


def _normalize_code_text(tokens: list[str]) -> str:
    """Join decompiled tokens into a single whitespace-normalized code string.

    Args:
        tokens: List of tokens from the decompiled function.

    Returns:
        The joined, whitespace-normalized code text.

    """
    code_text = " ".join(str(t) for t in tokens)
    return re.sub(r"\s+", " ", code_text).strip()


def _split_statements(code_text: str) -> list[str]:
    """Split normalized code text into statement-level fragments.

    Args:
        code_text: Whitespace-normalized decompiled code.

    Returns:
        List of non-empty statements (split on semicolons).

    """
    return [s.strip() for s in code_text.split(";") if s.strip()]


def _truncate_statement(stmt: str) -> str:
    """Truncate a statement to the display limit.

    Args:
        stmt: The statement to truncate.

    Returns:
        The statement, capped at MAX_EVIDENCE_LENGTH characters.

    """
    if len(stmt) > MAX_EVIDENCE_LENGTH:
        return stmt[:MAX_EVIDENCE_LENGTH] + "..."
    return stmt


def _dedupe_cap(lines: list[str]) -> list[str]:
    """Deduplicate statements (preserving order) and cap the list length.

    Args:
        lines: Candidate evidence statements.

    Returns:
        Unique statements, capped at MAX_EVIDENCE_STATEMENTS.

    """
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique.append(line)
    return unique[:MAX_EVIDENCE_STATEMENTS]


def _extract_string_literals(code_text: str) -> list[str]:
    """Extract the contents of quoted string literals from decompiled code.

    Args:
        code_text: Whitespace-normalized decompiled code.

    Returns:
        List of string literal contents (without the surrounding quotes).

    """
    return [m.group(1) for m in _STRING_LITERAL_RE.finditer(code_text)]


def _match_api_call(compiled: _CompiledSignature, code_text: str) -> bool:
    """Match an api_call signature against a normalized function body.

    Primary: a real call (name followed by '('). Fallback: a function-pointer
    reference (``= name`` / ``&name``) that is not inside a quoted string.

    Args:
        compiled: The compiled signature.
        code_text: Whitespace-normalized decompiled code.

    Returns:
        True when any of the signature's API patterns is found.

    """
    for call_pattern in compiled.api_call_patterns:
        if call_pattern.search(code_text):
            return True

    for ptr_pattern in compiled.api_ptr_patterns:
        for m in ptr_pattern.finditer(code_text):
            # Only consider this a match if it looks like an assignment or
            # address-of and NOT inside a quoted string (basic heuristic:
            # count quotes before the match).
            preceding_text = code_text[: m.start()]
            quote_count = preceding_text.count('"') - preceding_text.count('\\"')
            if quote_count % 2 == 0:  # Even quotes means we're outside a string
                return True

    return False


def _match_string_pattern(compiled: _CompiledSignature, literals: list[str]) -> bool:
    """Match a string_pattern signature against string literals only.

    Args:
        compiled: The compiled signature.
        literals: Contents of the string literals in the function body.

    Returns:
        True when any pattern matches any string literal (case-insensitive).

    """
    for pattern in compiled.string_patterns:
        for literal in literals:
            if pattern.search(literal):
                return True
    return False


def _match_code_heuristic(compiled: _CompiledSignature, code_text: str) -> bool:
    """Match a code_heuristic signature over the normalized function body.

    Args:
        compiled: The compiled signature.
        code_text: Whitespace-normalized decompiled code.

    Returns:
        True when any compound pattern matches the body.

    """
    return any(pattern.search(code_text) for pattern in compiled.heuristic_patterns)


def _evidence_for_api_call(statements: list[str], compiled: _CompiledSignature) -> list[str]:
    """Extract evidence statements for an api_call match.

    Prefers statements containing a real call; when only the function-pointer
    fallback matched, uses statements containing an out-of-string pointer
    reference.

    Args:
        statements: Statement-level fragments of the function body.
        compiled: The compiled signature.

    Returns:
        Evidence statements, capped and deduplicated.

    """
    matching: list[str] = []
    for stmt in statements:
        if any(p.search(stmt) for p in compiled.api_call_patterns):
            matching.append(_truncate_statement(stmt))

    if not matching:
        for stmt in statements:
            for p in compiled.api_ptr_patterns:
                m = p.search(stmt)
                if m is None:
                    continue
                preceding_text = stmt[: m.start()]
                quote_count = preceding_text.count('"') - preceding_text.count('\\"')
                if quote_count % 2 == 0:
                    matching.append(_truncate_statement(stmt))
                    break

    return _dedupe_cap(matching)


def _evidence_for_string_pattern(
    statements: list[str],
    literals: list[str],
    compiled: _CompiledSignature,
) -> list[str]:
    """Extract evidence statements for a string_pattern match.

    Args:
        statements: Statement-level fragments of the function body.
        literals: Contents of the string literals in the function body.
        compiled: The compiled signature.

    Returns:
        Statements containing a matching string literal, capped and deduplicated.

    """
    matched_literals: set[str] = set()
    for literal in literals:
        for pattern in compiled.string_patterns:
            if pattern.search(literal):
                matched_literals.add(literal.lower())

    matching: list[str] = []
    for stmt in statements:
        for lit in _extract_string_literals(stmt):
            if lit.lower() in matched_literals:
                matching.append(_truncate_statement(stmt))
                break

    return _dedupe_cap(matching)


def _evidence_for_code_heuristic(statements: list[str]) -> list[str]:
    """Extract evidence statements for a code_heuristic match.

    The compound pattern spans the whole body, so the function's own
    statements are the evidence.

    Args:
        statements: Statement-level fragments of the function body.

    Returns:
        The (truncated) statements, capped and deduplicated.

    """
    return _dedupe_cap([_truncate_statement(stmt) for stmt in statements])


def _extract_evidence(
    detection_method: DetectionMethod,
    statements: list[str],
    literals: list[str],
    compiled: _CompiledSignature,
) -> list[str]:
    """Dispatch evidence extraction to the per-method matcher.

    Args:
        detection_method: The signature's detection method.
        statements: Statement-level fragments of the function body.
        literals: Contents of the string literals in the function body.
        compiled: The compiled signature.

    Returns:
        Evidence statements (capped at 10 statements, 300 chars each).

    """
    if detection_method == "api_call":
        return _evidence_for_api_call(statements, compiled)
    if detection_method == "string_pattern":
        return _evidence_for_string_pattern(statements, literals, compiled)
    if detection_method == "code_heuristic":
        return _evidence_for_code_heuristic(statements)
    # import_check is reserved; no v1 entries use it.
    return []


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


def _scan_function_bodies(functions: list[dict[str, Any]]) -> list[BehavioralScanResult]:
    """Scan function bodies for malware-associated behaviors.

    Each function's decompiled token list is normalized once, and every
    signature in the catalog is matched against it using the signature's
    detection method.

    Args:
        functions: List of function dictionaries.

    Returns:
        BehavioralScanResults for all behavior matches found in bodies.

    """
    results: list[BehavioralScanResult] = []
    total_funcs = len(functions)
    funcs_with_tokens = 0
    funcs_with_match = 0

    for func_info in functions:
        func_name = func_info.get("functionName", "")
        tokens = func_info.get("tokenList", [])
        if not tokens:
            continue
        funcs_with_tokens += 1

        # Normalize the function's code text once and run all signatures
        # against it.
        code_text = _normalize_code_text(tokens)
        if not code_text:
            continue
        statements = _split_statements(code_text)
        literals = _extract_string_literals(code_text)

        for compiled in _COMPILED_SIGNATURES:
            entry = compiled.entry
            if entry.detection_method == "api_call":
                found = _match_api_call(compiled, code_text)
            elif entry.detection_method == "string_pattern":
                found = _match_string_pattern(compiled, literals)
            elif entry.detection_method == "code_heuristic":
                found = _match_code_heuristic(compiled, code_text)
            else:  # import_check is reserved; never matches in v1.
                found = False

            if found:
                funcs_with_match += 1
                results.append(
                    BehavioralScanResult(
                        signature_id=entry.signature_id,
                        behavior_name=entry.name,
                        category=entry.category,
                        severity=entry.severity,
                        detection_method=entry.detection_method,
                        containing_function=func_name,
                        entrypoint=func_info.get("lowAddress", "0x0"),
                        mitre_technique=entry.mitre_technique,
                        description=entry.description,
                        matched_evidence=_extract_evidence(
                            entry.detection_method, statements, literals, compiled
                        ),
                        containing_function_code=_format_full_function_code(tokens),
                    )
                )
                logger.debug(
                    "Behavioral scan: found '{}' ({}) in function '{}' (entrypoint {})",
                    entry.name,
                    entry.signature_id,
                    func_name,
                    func_info.get("lowAddress", "0x0"),
                )

    logger.info(
        "Behavioral scan: found {} behavior matches in {} functions ({} had tokens, {} had matches)",
        len(results),
        total_funcs,
        funcs_with_tokens,
        funcs_with_match,
    )

    return results


def scan_functions(functions: list[dict[str, Any]]) -> list[BehavioralScanResult]:
    """Scan a list of decompiled functions for malware-associated behaviors.

    Scans each function's decompiled token list against the behavioral
    signature catalog.

    Args:
        functions: List of function dictionaries from Ghidra decompilation.
            Each dict should have keys: 'functionName', 'lowAddress', 'tokenList'.

    Returns:
        List of BehavioralScanResult sorted by severity (Critical first).

    """
    results = _scan_function_bodies(functions)

    # Sort by severity
    results.sort(key=lambda r: get_severity_order(r.severity))

    logger.info(
        "Scan complete: {} behaviors found across {} functions scanned",
        len(results),
        len(functions),
    )

    return results


def generate_report(
    model_name: str,
    functions: list[dict[str, Any]],
    scan_results: list[BehavioralScanResult] | None = None,
) -> BehavioralScanReport:
    """Generate a behavioral scan report from the scan results.

    Args:
        model_name: Name of the model/binary scanned.
        functions: Original list of functions scanned.
        scan_results: Pre-computed scan results. If None, scan is performed.

    Returns:
        BehavioralScanReport with aggregated counts and results.

    """
    if scan_results is None:
        scan_results = scan_functions(functions)

    critical = sum(1 for r in scan_results if r.severity == "Critical")
    high = sum(1 for r in scan_results if r.severity == "High")
    medium = sum(1 for r in scan_results if r.severity == "Medium")
    low = sum(1 for r in scan_results if r.severity == "Low")

    return BehavioralScanReport(
        model_name=model_name,
        total_functions_scanned=len(functions),
        total_found=len(scan_results),
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        results=scan_results,
    )
