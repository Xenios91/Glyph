"""Unit tests for the unified response helpers in ``app.utils.responses``.

Covers the ISO-8601 metadata timestamp serializer, the ``PaginatedResponse``
``total_pages`` derivation, and the ``create_error_response`` shape (with and
without optional ``details``/``request_id``).
"""

from datetime import UTC, datetime

from app.utils.responses import (
    Metadata,
    PaginatedResponse,
    create_error_response,
    create_paginated_response,
    create_success_response,
)


class TestMetadataTimestamp:
    """Metadata timestamp serialization."""

    def test_metadata_timestamp_iso(self) -> None:
        """The serialized timestamp must be an ISO-8601 string."""
        metadata = Metadata(timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
        dumped = metadata.model_dump()
        assert dumped["timestamp"] == "2026-01-02T03:04:05+00:00"
        # The serializer output must round-trip through datetime.fromisoformat.
        assert datetime.fromisoformat(dumped["timestamp"]) == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    def test_metadata_default_timestamp_is_utc(self) -> None:
        """A default-constructed Metadata must carry a UTC timestamp."""
        metadata = Metadata()
        assert metadata.timestamp.tzinfo is not None
        assert metadata.timestamp.utcoffset() == datetime.now(UTC).utcoffset()


class TestPaginatedResponse:
    """PaginatedResponse total_pages derivation."""

    def test_paginated_total_pages_computed(self) -> None:
        """total_pages must be derived from total/page_size when not supplied."""
        response = PaginatedResponse(
            items=["a", "b"],
            total=10,
            page=1,
            page_size=3,
            total_pages=0,  # sentinel: validator must compute the real value
        )
        assert response.total_pages == 4  # ceil(10 / 3)

    def test_paginated_total_pages_explicit_wins(self) -> None:
        """An explicit positive total_pages must be preserved."""
        response = PaginatedResponse(
            items=["a"],
            total=10,
            page=1,
            page_size=3,
            total_pages=7,
        )
        assert response.total_pages == 7

    def test_paginated_total_items_zero(self) -> None:
        """Zero total items must yield zero total pages."""
        response = PaginatedResponse(items=[], total=0, page=1, page_size=10, total_pages=0)
        assert response.total_pages == 0

    def test_create_paginated_response_factory(self) -> None:
        """The factory must compute total_pages consistently."""
        response = create_paginated_response(items=["x"], total=25, page=2, page_size=10)
        assert response.total_pages == 3
        assert response.page == 2
        assert response.page_size == 10
        assert response.total == 25


class TestErrorResponse:
    """create_error_response shape."""

    def test_error_response_shape_without_details(self) -> None:
        """Without details/request_id the error dict carries only code+message."""
        response = create_error_response("NOT_FOUND", "Resource not found")
        assert response.success is False
        assert response.error == {"code": "NOT_FOUND", "message": "Resource not found"}
        assert "details" not in response.error
        assert response.metadata.request_id is None

    def test_error_response_shape_with_details_and_request_id(self) -> None:
        """details and request_id must be attached when provided."""
        response = create_error_response(
            "VALIDATION_ERROR",
            "Invalid input",
            details={"field": "name", "reason": "too long"},
            request_id="req-123",
        )
        assert response.error["code"] == "VALIDATION_ERROR"
        assert response.error["message"] == "Invalid input"
        assert response.error["details"] == {"field": "name", "reason": "too long"}
        assert response.metadata.request_id == "req-123"


class TestSuccessResponse:
    """create_success_response shape."""

    def test_success_response_with_request_id(self) -> None:
        """request_id must be threaded into the metadata when provided."""
        response = create_success_response(data={"ok": True}, message="done", request_id="req-9")
        assert response.success is True
        assert response.data == {"ok": True}
        assert response.message == "done"
        assert response.metadata.request_id == "req-9"

    def test_success_response_without_request_id(self) -> None:
        """Without request_id the metadata must not carry one."""
        response = create_success_response(data=None)
        assert response.success is True
        assert response.data is None
        assert response.metadata.request_id is None
