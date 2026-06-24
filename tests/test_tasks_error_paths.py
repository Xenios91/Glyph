"""Error path tests for tasks API v1 endpoints.

Covers Pydantic model validation failures and edge cases
that are not exercised by the existing endpoint tests.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.api.types import TaskType


# ---------------------------------------------------------------------------
# TaskExecutionRequest validation
# ---------------------------------------------------------------------------


class TestTaskExecutionRequestValidation:
    """Tests for TaskExecutionRequest Pydantic model validation."""

    def test_binary_id_required(self) -> None:
        """Missing binary_id should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                task_type=TaskType.CODE_REUSE,
                task_name="test",
            )

    def test_binary_id_must_be_positive(self) -> None:
        """binary_id must be greater than 0."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=0,
                task_type=TaskType.CODE_REUSE,
                task_name="test",
            )

    def test_binary_id_negative_rejected(self) -> None:
        """Negative binary_id should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=-1,
                task_type=TaskType.CODE_REUSE,
                task_name="test",
            )

    def test_task_type_required(self) -> None:
        """Missing task_type should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=1,
                task_name="test",
            )

    def test_task_type_invalid_value(self) -> None:
        """Invalid task_type should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=1,
                task_type="invalid_task",  # type: ignore[arg-type]
                task_name="test",
            )

    def test_task_name_required(self) -> None:
        """Missing task_name should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.CODE_REUSE,
            )

    def test_task_name_empty_rejected(self) -> None:
        """Empty task_name should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.CODE_REUSE,
                task_name="",
            )

    def test_task_name_whitespace_only_accepted(self) -> None:
        """Whitespace-only task_name passes min_length check (not stripped)."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        # task_name uses plain str (no strip_whitespace), so "   " has length 3
        req = TaskExecutionRequest(
            binary_id=1,
            task_type=TaskType.CODE_REUSE,
            task_name="   ",
        )
        assert req.task_name == "   "

    def test_task_name_too_long_rejected(self) -> None:
        """task_name exceeding max_length should raise validation error."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        with pytest.raises(ValidationError):
            TaskExecutionRequest(
                binary_id=1,
                task_type=TaskType.CODE_REUSE,
                task_name="x" * 129,
            )

    def test_valid_request_minimal(self) -> None:
        """Minimal valid request should succeed."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        req = TaskExecutionRequest(
            binary_id=1,
            task_type=TaskType.CODE_REUSE,
            task_name="my_task",
        )
        assert req.binary_id == 1
        assert req.task_type == TaskType.CODE_REUSE
        assert req.model_name is None
        assert req.ml_class_type is None

    def test_valid_request_ml_training(self) -> None:
        """Valid ML training request should succeed."""
        from app.api.v1.endpoints.tasks import TaskExecutionRequest

        req = TaskExecutionRequest(
            binary_id=1,
            task_type=TaskType.ML_TRAINING,
            task_name="train_model",
            model_name="malware_detector",
            ml_class_type="RandomForestClassifier",
        )
        assert req.model_name == "malware_detector"
        assert req.ml_class_type == "RandomForestClassifier"


# ---------------------------------------------------------------------------
# SimilarityComputationRequest validation
# ---------------------------------------------------------------------------


class TestSimilarityComputationRequestValidation:
    """Tests for SimilarityComputationRequest Pydantic model validation."""

    def test_task_name_required(self) -> None:
        """Missing task_name should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                binary_ids=[1, 2],
            )

    def test_task_name_empty_rejected(self) -> None:
        """Empty task_name should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="",
                binary_ids=[1, 2],
            )

    def test_task_name_too_long_rejected(self) -> None:
        """task_name exceeding max_length should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="x" * 129,
                binary_ids=[1, 2],
            )

    def test_binary_ids_required(self) -> None:
        """Missing binary_ids should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="compare",
            )

    def test_binary_ids_must_have_at_least_two(self) -> None:
        """binary_ids must have at least 2 entries."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="compare",
                binary_ids=[1],
            )

    def test_binary_ids_empty_rejected(self) -> None:
        """Empty binary_ids list should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="compare",
                binary_ids=[],
            )

    def test_match_threshold_out_of_range_below(self) -> None:
        """match_threshold below 0.0 should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="compare",
                binary_ids=[1, 2],
                match_threshold=-0.1,
            )

    def test_match_threshold_out_of_range_above(self) -> None:
        """match_threshold above 1.0 should raise validation error."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="compare",
                binary_ids=[1, 2],
                match_threshold=1.5,
            )

    def test_valid_request_minimal(self) -> None:
        """Minimal valid request should succeed."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        req = SimilarityComputationRequest(
            task_name="compare_binaries",
            binary_ids=[1, 2],
        )
        assert req.task_name == "compare_binaries"
        assert req.binary_ids == [1, 2]
        assert req.match_threshold == 0.7  # default

    def test_valid_request_with_threshold(self) -> None:
        """Valid request with custom threshold should succeed."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        req = SimilarityComputationRequest(
            task_name="compare_binaries",
            binary_ids=[1, 2, 3],
            match_threshold=0.5,
        )
        assert req.match_threshold == 0.5
        assert len(req.binary_ids) == 3

    def test_valid_request_boundary_thresholds(self) -> None:
        """Boundary values for match_threshold should succeed."""
        from app.api.v1.endpoints.tasks import SimilarityComputationRequest

        req_zero = SimilarityComputationRequest(
            task_name="compare",
            binary_ids=[1, 2],
            match_threshold=0.0,
        )
        assert req_zero.match_threshold == 0.0

        req_one = SimilarityComputationRequest(
            task_name="compare",
            binary_ids=[1, 2],
            match_threshold=1.0,
        )
        assert req_one.match_threshold == 1.0


# ---------------------------------------------------------------------------
# TaskExecutionResponse validation
# ---------------------------------------------------------------------------


class TestTaskExecutionResponseValidation:
    """Tests for TaskExecutionResponse Pydantic model."""

    def test_response_fields(self) -> None:
        """TaskExecutionResponse should have expected fields."""
        from app.api.v1.endpoints.tasks import TaskExecutionResponse

        resp = TaskExecutionResponse(
            task_uuid="abc-123",
            task_type="code_reuse",
            binary_id=1,
            status="starting",
        )
        assert resp.task_uuid == "abc-123"
        assert resp.task_type == "code_reuse"
        assert resp.binary_id == 1
        assert resp.status == "starting"


# ---------------------------------------------------------------------------
# SimilarityPairResponse validation
# ---------------------------------------------------------------------------


class TestSimilarityPairResponseValidation:
    """Tests for SimilarityPairResponse Pydantic model."""

    def test_pair_response_fields(self) -> None:
        """SimilarityPairResponse should have expected fields."""
        from app.api.v1.endpoints.tasks import SimilarityPairResponse

        resp = SimilarityPairResponse(
            binary_a_id=1,
            binary_a_name="binary_a",
            binary_b_id=2,
            binary_b_name="binary_b",
            overall_similarity=0.85,
            matched_function_count=5,
            total_function_comparisons=10,
        )
        assert resp.binary_a_id == 1
        assert resp.overall_similarity == 0.85
        assert resp.matched_function_count == 5


# ---------------------------------------------------------------------------
# CodeReuseResults validation
# ---------------------------------------------------------------------------


class TestCodeReuseResultsValidation:
    """Tests for CodeReuseResults Pydantic model."""

    def test_code_reuse_results_fields(self) -> None:
        """CodeReuseResults should have expected fields."""
        from app.api.v1.endpoints.tasks import CodeReuseResults, CodeReuseComparison, CodeReuseMatch

        match = CodeReuseMatch(
            source_function_name="main",
            target_function_name="main_copy",
            similarity_score=0.95,
            source_tokens="int main",
            target_tokens="int main",
        )
        comparison = CodeReuseComparison(
            target_binary_id=2,
            target_binary_name="target.bin",
            matched_functions=[match],
            overall_similarity=0.95,
        )
        results = CodeReuseResults(
            task_uuid="abc-123",
            source_binary_id=1,
            source_binary_name="source.bin",
            comparisons=[comparison],
        )
        assert results.task_uuid == "abc-123"
        assert len(results.comparisons) == 1
        assert results.comparisons[0].matched_functions[0].similarity_score == 0.95
