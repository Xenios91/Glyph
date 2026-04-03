"""Shared type annotations for FastAPI endpoints.

This module provides Pydantic Annotated types with built-in validation
for common parameters across API endpoints.
"""

from typing_extensions import Annotated

from pydantic import StringConstraints


# Common string constraints for API parameters
ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
"""Validated model name - stripped, 1-128 characters."""

FunctionName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]
"""Validated function name - stripped, 1-256 characters."""

TaskName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
"""Validated task name - stripped, 1-128 characters."""

UUID = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
"""Validated UUID string - stripped, 1-64 characters."""

BinaryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]
"""Validated binary filename - stripped, 1-256 characters."""

MLClassType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
"""Validated ML class type - stripped, 1-64 characters."""

StatusMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
"""Validated status message - stripped, 1-512 characters."""
