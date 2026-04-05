"""Shared type annotations for FastAPI endpoints."""

from typing_extensions import Annotated

from pydantic import StringConstraints


ModelName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]

FunctionName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]

TaskName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]

UUID = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]

BinaryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256)
]

MLClassType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]

StatusMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512)
]
