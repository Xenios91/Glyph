"""Utility functions for code formatting and other utilities."""

from typing import Any


import re

def format_code(code: str) -> str:
    """Format Ghidra C code: removes comments and enforces proper indentation.
    
    Returns raw, unescaped code. HTML escaping is handled by Jinja2 auto-escaping
    when rendered in templates, and JSON responses remain clean for API consumers.
    """
    
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    code = re.sub(r'//.*', '', code)

    parts = code.split("{", 1)
    if len(parts) != 2:
        return code.strip()

    function_signature = " ".join(parts[0].strip().split())
    
    function_body = parts[1].rsplit("}", 1)[0]

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
                if function_body[i] == '\\': i += 1
                i += 1
            tokens.append(function_body[start:i+1])
            current_token = ""
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
    task_name: str,
    model_name: str,
    function_name: str,
    model_tokens: str,
    prediction_tokens: str) -> dict[str, Any]:
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
