"""Unified response format for Glyph API."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, field_serializer

T = TypeVar("T")


class Metadata(BaseModel):
    """Response metadata."""

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp in UTC")
    request_id: str | None = Field(
        default=None,
        description="Unique request identifier for tracing")

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize timestamp to ISO format string.

        Args:
            value: The datetime value to serialize.

        Returns:
            ISO format string representation of the datetime.
        """
        return value.isoformat()


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response.

    Type parameter T represents the data payload type.
    """

    success: bool = Field(True, description="Response status indicator")
    data: T | None = Field(default=None, description="Response data payload")
    message: str | None = Field(
        default=None, description="Optional human-readable message"
    )
    metadata: SerializeAsAny[Metadata] = Field(default_factory=Metadata, description="Response metadata")


class ErrorResponse(BaseModel):
    """Standardized error response."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(False, description="Response status indicator")
    error: dict[str, Any] = Field(..., description="Error details")
    metadata: SerializeAsAny[Metadata] = Field(default_factory=Metadata, description="Response metadata")


class ErrorDetails(BaseModel):
    """Error details for ErrorResponse."""

    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error context"
    )


def create_success_response(
    data: T | None = None,
    message: str | None = None,
    request_id: str | None = None) -> SuccessResponse[T]:
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
        metadata=Metadata(request_id=request_id) if request_id else Metadata())


def create_error_response(
    error_code: str,
    error_message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None) -> ErrorResponse:
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
        metadata=Metadata(request_id=request_id) if request_id else Metadata())
