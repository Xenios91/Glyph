"""Tests for BinarySimilarityService and similarity API endpoints."""

from typing import Any

import pytest
import pytest_asyncio
from app.api.v1.endpoints.tasks import (
    SimilarityComputationRequest,
    SimilarityMatrixResponse,
    SimilarityPairResponse,
)
from app.database.models import (
    Base,
    Binary,
    BinaryFunction,
    SimilarityPair,
    User,
)
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    get_async_session,
    init_async_databases,
)
from app.database.sql_service import SQLUtil
from app.services.binary_similarity_service import (
    BinarySimilarityService,
    SimilarityMatrixEntry,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Database lifecycle fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", autouse=True)
async def similarity_db_lifecycle():
    """Initialize and cleanup in-memory databases for similarity tests."""
    await init_async_databases()

    # Fresh tables for binaries, intelligence, and auth databases.
    for db_name in ("binaries", "intelligence", "auth"):
        target_tables = DB_TABLE_MAP.get(db_name)
        if target_tables and db_name in async_engines:
            async with async_engines[db_name].begin() as conn:
                await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
                await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


# ---------------------------------------------------------------------------
# Fixtures – database sessions with seed data
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def binaries_session() -> Any:
    """Provide a binaries database session and clean up after each test."""
    target_tables = DB_TABLE_MAP.get("binaries")
    if target_tables and "binaries" in async_engines:
        async with async_engines["binaries"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    session = await get_async_session("binaries")
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def intelligence_session() -> Any:
    """Provide an intelligence database session and clean up after each test."""
    target_tables = DB_TABLE_MAP.get("intelligence")
    if target_tables and "intelligence" in async_engines:
        async with async_engines["intelligence"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    session = await get_async_session("intelligence")
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def auth_session() -> Any:
    """Provide an auth database session with a test user."""
    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    session = await get_async_session("auth")
    try:
        # Insert a test user
        user = User(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="dummy",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def seeded_binaries(binaries_session: Any) -> list[int]:
    """Seed two binaries with functions and return their IDs."""
    # Create binaries
    bin_a = Binary(
        name="binary_a",
        uploaded_by=1,
        file_path="/tmp/a.bin",
        file_size=1024,
        mime_type="application/x-executable",
    )
    binaries_session.add(bin_a)
    await binaries_session.flush()

    bin_b = Binary(
        name="binary_b",
        uploaded_by=1,
        file_path="/tmp/b.bin",
        file_size=2048,
        mime_type="application/x-executable",
    )
    binaries_session.add(bin_b)
    await binaries_session.flush()

    # Create functions for binary_a
    func_a1 = BinaryFunction(
        binary_id=bin_a.id,
        function_name="func_a1",
        raw_code="int main() { return 0; }",
        entrypoint="0x401000",
    )
    func_a2 = BinaryFunction(
        binary_id=bin_a.id,
        function_name="func_a2",
        raw_code='void helper() { printf("hello"); }',
        entrypoint="0x401100",
    )
    binaries_session.add(func_a1)
    binaries_session.add(func_a2)

    # Create functions for binary_b
    func_b1 = BinaryFunction(
        binary_id=bin_b.id,
        function_name="func_b1",
        raw_code="int main() { return 0; }",
        entrypoint="0x401000",
    )
    func_b2 = BinaryFunction(
        binary_id=bin_b.id,
        function_name="func_b2",
        raw_code="void other() { exit(1); }",
        entrypoint="0x401200",
    )
    binaries_session.add(func_b1)
    binaries_session.add(func_b2)

    await binaries_session.commit()
    return [bin_a.id, bin_b.id]


# ---------------------------------------------------------------------------
# Tests – BinarySimilarityService.get_similarity_color()
# ---------------------------------------------------------------------------


class TestGetSimilarityColor:
    """Tests for the similarity color gradient helper."""

    def test_score_zero_returns_white(self) -> None:
        """Score 0.0 should produce white (#ffffff)."""
        color = BinarySimilarityService.get_similarity_color(0.0)
        assert color == "#ffffff"

    def test_score_one_returns_red(self) -> None:
        """Score 1.0 should produce red (#ff0000)."""
        color = BinarySimilarityService.get_similarity_color(1.0)
        assert color == "#ff0000"

    def test_score_half_returns_yellow(self) -> None:
        """Score 0.5 should produce yellow (#ffff00)."""
        color = BinarySimilarityService.get_similarity_color(0.5)
        assert color == "#ffff00"

    def test_score_quarter_returns_intermediate(self) -> None:
        """Score 0.25 should be between white and yellow."""
        color = BinarySimilarityService.get_similarity_color(0.25)
        # t = 0.5 -> r=255, g=255, b=127 -> #ffff7f
        assert color == "#ffff7f"

    def test_score_three_quarters_returns_intermediate(self) -> None:
        """Score 0.75 should be between yellow and red."""
        color = BinarySimilarityService.get_similarity_color(0.75)
        # t = 0.5 -> r=255, g=127, b=0 -> #ff7f00
        assert color == "#ff7f00"

    def test_negative_score_clamped_to_zero(self) -> None:
        """Negative scores should be clamped to 0.0."""
        assert BinarySimilarityService.get_similarity_color(-0.5) == "#ffffff"

    def test_score_above_one_clamped(self) -> None:
        """Scores above 1.0 should be clamped to 1.0."""
        assert BinarySimilarityService.get_similarity_color(1.5) == "#ff0000"

    def test_returns_hex_format(self) -> None:
        """Color must be a 7-character hex string."""
        color = BinarySimilarityService.get_similarity_color(0.33)
        assert color.startswith("#")
        assert len(color) == 7


# ---------------------------------------------------------------------------
# Tests – BinarySimilarityService._prepare_binary_functions()
# ---------------------------------------------------------------------------


class TestPrepareBinaryFunctions:
    """Tests for loading, tokenizing, and filtering binary functions."""

    async def test_returns_none_for_nonexistent_binary(self) -> None:
        """Binary ID with no functions should return None."""
        # pyright: ignore[reportPrivateUsage]
        result = await BinarySimilarityService._prepare_binary_functions(9999)  # pyright: ignore[reportPrivateUsage]
        assert result is None

    async def test_returns_embeddings_for_valid_binary(self, seeded_binaries: list[int]) -> None:
        """Valid binary should return BinaryFunctionEmbeddings with filtered functions."""
        # pyright: ignore[reportPrivateUsage]
        result = await BinarySimilarityService._prepare_binary_functions(seeded_binaries[0])  # pyright: ignore[reportPrivateUsage]
        assert result is not None
        assert result.binary_id == seeded_binaries[0]
        assert len(result.filtered_functions) > 0

    async def test_embeddings_have_binary_name(self, seeded_binaries: list[int]) -> None:
        """Embeddings should carry the binary's human-readable name."""
        # pyright: ignore[reportPrivateUsage]
        result = await BinarySimilarityService._prepare_binary_functions(seeded_binaries[0])  # pyright: ignore[reportPrivateUsage]
        assert result is not None
        assert result.binary_name == "binary_a"

    async def test_filtered_functions_have_token_list(self, seeded_binaries: list[int]) -> None:
        """Each filtered function must contain a tokenList key."""
        # pyright: ignore[reportPrivateUsage]
        result = await BinarySimilarityService._prepare_binary_functions(seeded_binaries[0])  # pyright: ignore[reportPrivateUsage]
        assert result is not None
        for func in result.filtered_functions:
            assert "tokenList" in func


# ---------------------------------------------------------------------------
# Tests – BinarySimilarityService.compute_similarity_matrix()
# ---------------------------------------------------------------------------


class TestComputeSimilarityMatrix:
    """Tests for pairwise similarity computation."""

    async def test_empty_input_returns_empty(self) -> None:
        """Empty list should return empty result."""
        result = await BinarySimilarityService.compute_similarity_matrix([])
        assert result == []

    async def test_single_binary_returns_empty(self) -> None:
        """Single binary ID should return empty (need at least 2)."""
        result = await BinarySimilarityService.compute_similarity_matrix([1])
        assert result == []

    async def test_returns_entries_for_two_binaries(self, seeded_binaries: list[int]) -> None:
        """Two binaries with functions should produce one matrix entry."""
        result = await BinarySimilarityService.compute_similarity_matrix(seeded_binaries)
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry, SimilarityMatrixEntry)
        assert entry.binary_a_id == seeded_binaries[0]
        assert entry.binary_b_id == seeded_binaries[1]
        assert entry.total_function_comparisons > 0

    async def test_similarity_score_in_range(self, seeded_binaries: list[int]) -> None:
        """Overall similarity must be between 0.0 and 1.0."""
        result = await BinarySimilarityService.compute_similarity_matrix(seeded_binaries)
        assert len(result) == 1
        assert 0.0 <= result[0].overall_similarity <= 1.0

    async def test_identical_functions_produce_high_similarity(self, seeded_binaries: list[int]) -> None:
        """Binaries sharing identical function tokens should have non-zero similarity."""
        # Binary 1 and 2 exist in seeded data; func_a1 and func_b1 are identical
        result = await BinarySimilarityService.compute_similarity_matrix(seeded_binaries)
        if result:
            assert result[0].overall_similarity > 0

    async def test_match_threshold_filters_matches(self, seeded_binaries: list[int]) -> None:
        """Higher threshold should reduce matched_function_count."""
        # With threshold 0.0, all functions match.
        result_low = await BinarySimilarityService.compute_similarity_matrix(seeded_binaries, match_threshold=0.0)
        # With threshold 1.0, only perfect matches count.
        result_high = await BinarySimilarityService.compute_similarity_matrix(seeded_binaries, match_threshold=1.0)
        assert len(result_low) == 1
        assert len(result_high) == 1
        # matched count at low threshold >= matched count at high threshold
        assert result_low[0].matched_function_count >= result_high[0].matched_function_count


# ---------------------------------------------------------------------------
# Tests – Similarity API Request/Response Schemas
# ---------------------------------------------------------------------------


class TestSimilarityAPISchemas:
    """Tests for similarity computation request/response Pydantic schemas."""

    def test_similarity_computation_request_schema_defaults(self) -> None:
        """Schema should apply default match_threshold of 0.7."""
        req = SimilarityComputationRequest(
            task_name="test_task",
            binary_ids=[1, 2],
        )
        assert req.match_threshold == 0.7
        assert req.task_name == "test_task"
        assert req.binary_ids == [1, 2]

    def test_similarity_computation_request_validates_threshold_range(self) -> None:
        """match_threshold must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="test",
                binary_ids=[1, 2],
                match_threshold=-0.1,
            )

        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="test",
                binary_ids=[1, 2],
                match_threshold=1.5,
            )

    def test_similarity_computation_request_requires_min_two_binaries(self) -> None:
        """binary_ids must have at least 2 entries."""
        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="test",
                binary_ids=[1],
            )

    def test_similarity_computation_request_requires_task_name(self) -> None:
        """task_name must be non-empty."""
        with pytest.raises(ValidationError):
            SimilarityComputationRequest(
                task_name="",
                binary_ids=[1, 2],
            )

    def test_similarity_pair_response_fields(self) -> None:
        """SimilarityPairResponse should have all expected fields."""
        pair = SimilarityPairResponse(
            binary_a_id=1,
            binary_a_name="a.bin",
            binary_b_id=2,
            binary_b_name="b.bin",
            overall_similarity=0.85,
            matched_function_count=3,
            total_function_comparisons=10,
        )
        assert pair.binary_a_id == 1
        assert pair.binary_b_id == 2
        assert pair.overall_similarity == 0.85
        assert pair.matched_function_count == 3
        assert pair.total_function_comparisons == 10

    def test_similarity_matrix_response_fields(self) -> None:
        """SimilarityMatrixResponse should have all expected fields."""
        resp = SimilarityMatrixResponse(
            computation_id=1,
            task_name="test",
            binary_count=3,
            total_comparisons=3,
            status="completed",
            matrix=[
                SimilarityPairResponse(
                    binary_a_id=1,
                    binary_a_name="a.bin",
                    binary_b_id=2,
                    binary_b_name="b.bin",
                    overall_similarity=0.5,
                    matched_function_count=1,
                    total_function_comparisons=4,
                )
            ],
        )
        assert resp.computation_id == 1
        assert resp.binary_count == 3
        assert resp.status == "completed"
        assert len(resp.matrix) == 1


# ---------------------------------------------------------------------------
# Tests – SQL CRUD for similarity models
# ---------------------------------------------------------------------------


class TestSQLSimilarityCRUD:
    """Tests for SQLUtil similarity model CRUD methods."""

    async def test_create_and_get_computation(self, intelligence_session: Any) -> None:
        """Create a computation and retrieve it."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="test_task",
            computed_by=1,
            binary_count=2,
        )
        assert comp.id > 0

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert fetched.task_name == "test_task"
        assert fetched.status == "pending"
        assert fetched.binary_count == 2
        assert fetched.computed_by == 1

    async def test_list_computations_filters_by_user(self, intelligence_session: Any) -> None:
        """List computations should filter by computed_by user ID."""
        await SQLUtil.create_similarity_computation(
            task_name="task_user1",
            computed_by=1,
            binary_count=2,
        )
        await SQLUtil.create_similarity_computation(
            task_name="task_user2",
            computed_by=2,
            binary_count=3,
        )

        results_user1 = await SQLUtil.list_similarity_computations(computed_by=1)
        assert len(results_user1) == 1
        assert results_user1[0].task_name == "task_user1"

        results_user2 = await SQLUtil.list_similarity_computations(computed_by=2)
        assert len(results_user2) == 1
        assert results_user2[0].task_name == "task_user2"

    async def test_save_and_retrieve_pairs(self, intelligence_session: Any) -> None:
        """Save similarity pairs and verify they are returned with the computation."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="pair_test",
            computed_by=1,
            binary_count=2,
        )

        pair = SimilarityPair(
            binary_a_id=1,
            binary_b_id=2,
            overall_similarity=0.85,
            matched_function_count=3,
            total_function_comparisons=10,
        )
        await SQLUtil.save_similarity_pairs(
            computation_id=comp.id,
            pairs=[pair],
        )

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert len(fetched.pairs) == 1
        assert fetched.pairs[0].overall_similarity == 0.85

    async def test_update_status(self, intelligence_session: Any) -> None:
        """Update computation status and verify."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="status_test",
            computed_by=1,
            binary_count=2,
        )

        await SQLUtil.update_similarity_computation_status(
            computation_id=comp.id,
            status="completed",
            total_comparisons=5,
        )

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert fetched.status == "completed"
        assert fetched.total_comparisons == 5

    async def test_delete_computation_removes_pairs(self, intelligence_session: Any) -> None:
        """Deleting a computation should also delete its pairs."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="delete_test",
            computed_by=1,
            binary_count=2,
        )

        pair = SimilarityPair(
            binary_a_id=1,
            binary_b_id=2,
            overall_similarity=0.5,
            matched_function_count=1,
            total_function_comparisons=4,
        )
        await SQLUtil.save_similarity_pairs(
            computation_id=comp.id,
            pairs=[pair],
        )

        await SQLUtil.delete_similarity_computation(comp.id)

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is None

    async def test_list_computations_all(self, intelligence_session: Any) -> None:
        """List without user filter should return all computations."""
        await SQLUtil.create_similarity_computation(
            task_name="global1",
            computed_by=1,
            binary_count=2,
        )
        await SQLUtil.create_similarity_computation(
            task_name="global2",
            computed_by=2,
            binary_count=3,
        )

        all_comps = await SQLUtil.list_similarity_computations()
        assert len(all_comps) == 2

    async def test_update_status_nonexistent_no_error(self, intelligence_session: Any) -> None:
        """Updating a nonexistent computation should not raise an exception."""
        # Should return silently without error
        await SQLUtil.update_similarity_computation_status(
            computation_id=9999,
            status="completed",
        )

    async def test_create_computation_sets_defaults(self, intelligence_session: Any) -> None:
        """New computation should have total_comparisons=0 and status=pending."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="defaults_test",
            computed_by=1,
            binary_count=4,
        )
        assert comp.total_comparisons == 0
        assert comp.status == "pending"

    async def test_create_computation_custom_status(self, intelligence_session: Any) -> None:
        """Can create computation with custom initial status."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="custom_status",
            computed_by=1,
            binary_count=2,
            status="processing",
        )
        assert comp.status == "processing"

    async def test_save_multiple_pairs(self, intelligence_session: Any) -> None:
        """Can save multiple pairs in a single call."""
        comp = await SQLUtil.create_similarity_computation(
            task_name="multi_pair",
            computed_by=1,
            binary_count=3,
        )

        pairs = [
            SimilarityPair(
                binary_a_id=1,
                binary_b_id=2,
                overall_similarity=0.8,
                matched_function_count=2,
                total_function_comparisons=6,
            ),
            SimilarityPair(
                binary_a_id=1,
                binary_b_id=3,
                overall_similarity=0.3,
                matched_function_count=1,
                total_function_comparisons=6,
            ),
            SimilarityPair(
                binary_a_id=2,
                binary_b_id=3,
                overall_similarity=0.5,
                matched_function_count=1,
                total_function_comparisons=6,
            ),
        ]
        await SQLUtil.save_similarity_pairs(
            computation_id=comp.id,
            pairs=pairs,
        )

        fetched = await SQLUtil.get_similarity_computation(comp.id)
        assert fetched is not None
        assert len(fetched.pairs) == 3

    async def test_list_computations_ordered_by_created_at_desc(self, intelligence_session: Any) -> None:
        """Computations should be ordered newest first."""
        await SQLUtil.create_similarity_computation(
            task_name="first",
            computed_by=1,
            binary_count=2,
        )
        await SQLUtil.create_similarity_computation(
            task_name="second",
            computed_by=1,
            binary_count=2,
        )

        results = await SQLUtil.list_similarity_computations(computed_by=1)
        assert len(results) == 2
        # Most recent first
        assert results[0].task_name == "second"
        assert results[1].task_name == "first"
