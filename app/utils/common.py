"""Utility functions for code formatting and other utilities."""

from typing import Any


def format_code(code: str) -> str:
    """Format C code for browser display."""
    function_signature = code.split("{")[0].strip()
    function_signature = f"{function_signature}" + " \n{\n"

    function_body = " { ".join(code.split("{")[1:])
    function_body = function_body.replace("{", "\n{\n")
    function_body = function_body.replace("}", "\n}\n")
    function_body = function_body.replace(" ( ", "(")
    function_body = function_body.replace(" ) ", ")")
    function_body = function_body.replace(" ;", ";")
    function_body = function_body.replace(";", ";\n")
    function_body = function_body.replace("\n \n", "\n")

    formatted_code = f"{function_signature}{function_body}"

    return formatted_code


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

