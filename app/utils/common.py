"""Utility functions for code formatting and other utilities."""

import re
from typing import Any


def format_code(code: str) -> str:
    """Format Ghidra C code: removes comments and enforces proper indentation.

    Returns raw, unescaped code. HTML escaping is handled by Jinja2 auto-escaping
    when rendered in templates, and JSON responses remain clean for API consumers.
    """

    # Non-greedy pattern for C-style block comment removal.
    # Uses re.DOTALL so that '.' matches newlines, allowing multi-line comments
    # to be removed in a single pass. The non-greedy '*?' prevents excessive
    # backtracking on malformed input.
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    # Non-backtracking pattern for single-line comments.
    # Matches // ... up to end of line (excluding newline).
    code = re.sub(r"//[^\r\n]*", "", code)

    # Find the first '{' that is outside of string literals.
    # Comments were already removed above, so only strings need handling.
    opening_brace_pos = -1
    in_string = False
    for idx, ch in enumerate(code):
        if ch == '"':
            in_string = not in_string
        elif ch == "{" and not in_string:
            opening_brace_pos = idx
            break

    if opening_brace_pos == -1:
        return code.strip()

    function_signature = " ".join(code[:opening_brace_pos].strip().split())

    # Find the matching closing brace by tracking brace depth from the body.
    body_start = opening_brace_pos + 1
    depth = 1
    in_string = False
    end_pos = -1
    for idx in range(body_start, len(code)):
        ch = code[idx]
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_pos = idx
                    break

    if end_pos == -1:
        # No matching closing brace — fall back to original behavior.
        function_body = code[body_start:]
    else:
        function_body = code[body_start:end_pos]

    function_body = function_body.replace(" ( ", "(").replace(" ) ", ")")
    function_body = function_body.replace(" ;", ";")

    tokens: list[str] = []
    current_token = ""
    i = 0
    while i < len(function_body):
        char = function_body[i]
        if char in "{}();":
            if current_token.strip():
                tokens.append(current_token.strip())
            tokens.append(char)
            current_token = ""
        elif char == '"':
            start = i
            i += 1
            while i < len(function_body) and function_body[i] != '"':
                if function_body[i] == "\\":
                    i += 1
                i += 1
            tokens.append(function_body[start : i + 1])
            current_token = ""
            i += 1
            continue
        else:
            current_token += char
        i += 1

    if current_token.strip():
        tokens.append(current_token.strip())

    indent_level = 1

    final_output = [function_signature, "{"]

    current_line = "    " * indent_level

    for token in tokens:
        if token == "{":
            final_output.append(current_line.rstrip() + " {")
            indent_level += 1
            current_line = "    " * indent_level
        elif token == "}":
            if current_line.strip():
                final_output.append(current_line.rstrip())
            indent_level = max(0, indent_level - 1)
            current_line = ("    " * indent_level) + "}"
            final_output.append(current_line)
            current_line = "    " * indent_level
        elif token == ";":
            final_output.append(current_line.rstrip() + token)
            current_line = "    " * indent_level
        elif token == "(":
            current_line += token
        elif token == ")":
            current_line = current_line.rstrip() + token + " "
        else:
            current_line += token + " "

    if current_line.strip() and current_line.strip() != "}":
        final_output.append(current_line.rstrip())

    open_braces = sum(line.count("{") for line in final_output)
    close_braces = sum(line.count("}") for line in final_output)
    while close_braces < open_braces:
        final_output.append("}")
        close_braces += 1

    result = "\n".join(line for line in final_output if line.strip())
    return result


def build_prediction_details_response(
    task_name: str, model_name: str, function_name: str, model_tokens: str, prediction_tokens: str
) -> dict[str, Any]:
    """Build a standardized prediction details response.

    This function creates a consistent response structure for prediction details
    that can be used by both API and web endpoints.

    Args:
        task_name: Name of the task.
        model_name: Name of the model.
        function_name: Name of the function.
        model_tokens: Formatted model tokens.
        prediction_tokens: Formatted prediction tokens.

    Returns:
        Dictionary containing prediction details.
    """
    return {
        "task_name": task_name,
        "model_name": model_name,
        "function_name": function_name,
        "model_tokens": model_tokens,
        "prediction_tokens": prediction_tokens,
    }
