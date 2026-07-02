"""Unified response format for Glyph API."""

from datetime import UTC, datetime, timezone
from math import ceil
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny, field_serializer, field_validator

T = TypeVar("T")


class Metadata(BaseModel):
    """Response metadata."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Response timestamp in UTC")
    request_id: str | None = Field(default=None, description="Unique request identifier for tracing")

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
    message: str | None = Field(default=None, description="Optional human-readable message")
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
    details: dict[str, Any] | None = Field(default=None, description="Additional error context")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response wrapper.

    Use this when returning large collections that need pagination.
    Provides total count, current page, and total pages metadata.
    """

    items: list[T] = Field(..., description="Items on the current page")
    total: int = Field(..., description="Total number of items across all pages")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    page_size: int = Field(..., ge=1, le=200, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    @field_validator("total_pages", mode="before")
    @classmethod
    def compute_total_pages(cls, v: int | None, info: Any) -> int:
        """Compute total pages from total and page_size if not provided."""
        if v is not None and v > 0:
            return v
        total = info.data.get("total", 0)
        page_size = info.data.get("page_size", 1)
        return cast(int, ceil(total / page_size) if page_size > 0 else 0)


def create_paginated_response(
    items: list[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[T]:
    """Factory function to create a paginated response.

    Args:
        items: The items on the current page.
        total: Total number of items across all pages.
        page: Current page number (1-based).
        page_size: Number of items per page.

    Returns:
        A PaginatedResponse instance.
    """
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if page_size > 0 else 0,
    )


def create_success_response(
    data: T | None = None, message: str | None = None, request_id: str | None = None
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
        success=True, data=data, message=message, metadata=Metadata(request_id=request_id) if request_id else Metadata()
    )


def create_error_response(
    error_code: str, error_message: str, details: dict[str, Any] | None = None, request_id: str | None = None
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
