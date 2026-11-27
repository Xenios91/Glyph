"""Shared helpers for working with decompiled function tokens.

Both the dangerous-function scanner and the behavioral scanner normalize
decompiled token lists into a single whitespace-normalized code string, split
it into statement-level fragments, truncate long statements for display, and
deduplicate/cap the resulting evidence. This module holds those primitives so
the two scanners share one implementation instead of diverging copies.

The display limits (``MAX_EVIDENCE_STATEMENTS`` / ``MAX_EVIDENCE_LENGTH``) are
defined here and re-exported by the scanners that use them.
"""

import re
from typing import Final

# Evidence display limits: at most this many statements, each at most this
# many characters.
MAX_EVIDENCE_STATEMENTS: Final[int] = 10
MAX_EVIDENCE_LENGTH: Final[int] = 300

# Quoted string literals, including wide (L"...") literals. Handles escaped
# quotes and backslashes inside the literal.
_STRING_LITERAL_RE = re.compile(r'(?:L|l)?"((?:[^"\\]|\\.)*)"')


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
