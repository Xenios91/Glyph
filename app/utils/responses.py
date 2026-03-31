"""Unified response format for Glyph API."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Metadata(BaseModel):
    """Response metadata."""

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp in UTC",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier for tracing",
    )


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response.

    Type parameter T represents the data payload type.
    """

    success: bool = Field(True, description="Response status indicator")
    data: Optional[T] = Field(default=None, description="Response data payload")
    message: Optional[str] = Field(
        default=None, description="Optional human-readable message"
    )
    metadata: Metadata = Field(default_factory=Metadata, description="Response metadata")


class ErrorResponse(BaseModel):
    """Standardized error response."""

    success: bool = Field(False, description="Response status indicator")
    error: dict[str, Any] = Field(..., description="Error details")
    metadata: Metadata = Field(default_factory=Metadata, description="Response metadata")

    class Config:
        frozen = True


class ErrorDetails(BaseModel):
    """Error details for ErrorResponse."""

    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )


def create_success_response(
    data: Optional[T] = None,
    message: Optional[str] = None,
    request_id: Optional[str] = None,
) -> SuccessResponse[T]:
    """Factory function to create a success response.

    Args:
        data: The data payload to include in the response.
        message: Optional human-readable message.
        request_id: Optional request identifier for tracing.

    Returns:
        A SuccessResponse instance.
    """
    return SuccessResponse(
        success=True,
        data=data,
        message=message,
        metadata=Metadata(request_id=request_id) if request_id else Metadata(),
    )


def create_error_response(
    error_code: str,
    error_message: str,
    details: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> ErrorResponse:
    """Factory function to create an error response.

    Args:
        error_code: A machine-readable error code identifier.
        error_message: A human-readable error message.
        details: Optional additional error context.
        request_id: Optional request identifier for tracing.

    Returns:
        An ErrorResponse instance.
    """
    error_details = ErrorDetails(code=error_code, message=error_message, details=details)
    return ErrorResponse(
        success=False,
        error=error_details.model_dump(),
        metadata=Metadata(request_id=request_id) if request_id else Metadata(),
    )
