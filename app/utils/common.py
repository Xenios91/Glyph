"""Utility functions for code formatting and other utilities."""

from typing import Any


import re

def format_code(code: str) -> str:
    """Format Ghidra C code: removes comments and enforces proper indentation."""
    
    # 1. Remove Comments (Both /* */ and //)
    # This regex handles multi-line comments and single-line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    code = re.sub(r'//.*', '', code)

    # 2. Split into signature and body
    parts = code.split("{", 1)
    if len(parts) != 2:
        return code.strip()

    function_signature = parts[0].strip()
    # Ensure the signature doesn't have internal double-spaces from removed comments
    function_signature = " ".join(function_signature.split())
    
    function_body = parts[1].rsplit("}", 1)[0] # Extract only what's inside the braces

    # 3. Clean up whitespace and unnecessary Ghidra-isms
    function_body = function_body.replace(" ( ", "(").replace(" ) ", ")")
    function_body = function_body.replace(" ;", ";")

    # 4. Tokenization (Handles strings and control characters)
    tokens = []
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
            # Handle string literals (prevent breaking on ';' inside strings)
            start = i
            i += 1
            while i < len(function_body) and function_body[i] != '"':
                if function_body[i] == '\\': i += 1 # Skip escaped quotes
                i += 1
            tokens.append(function_body[start:i+1])
            current_token = ""
        else:
            current_token += char
        i += 1

    if current_token.strip():
        tokens.append(current_token.strip())

    # 5. Rebuild with Indentation Logic
    result = []
    indent_level = 1
    
    # Start with signature and opening brace
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

    # Append any remaining content
    if current_line.strip() and current_line.strip() != "}":
        final_output.append(current_line.rstrip())
    
    # Ensure the very last closing brace is there if not already
    if not final_output[-1].strip() == "}":
        final_output.append("}")

    # Final cleanup of empty lines
    return "\n".join(line for line in final_output if line.strip())


def build_prediction_details_response(
    task_name: str,
    model_name: str,
    function_name: str,
    model_tokens: str,
    prediction_tokens: str,
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
