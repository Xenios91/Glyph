"""Shared type annotations for FastAPI endpoints."""

from enum import Enum

from typing_extensions import Annotated

from pydantic import StringConstraints


class TaskType(str, Enum):
    """Types of analysis tasks that can be performed on a binary."""

    CODE_REUSE = "code_reuse"
    ML_TRAINING = "ml_training"
    ML_PREDICTION = "ml_prediction"


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
