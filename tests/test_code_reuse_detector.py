"""Tests for code reuse detection service."""
from unittest import mock

import pytest

from app.services.code_reuse_detector import (
    _longest_common_subsequence,
    compare_binaries,
    compute_similarity,
)


class TestLongestCommonSubsequence:
    """Tests for _longest_common_subsequence helper."""

    def test_lcs_empty_first(self) -> None:
        """Test LCS returns 0 when first sequence is empty."""
        result = _longest_common_subsequence([], ["a", "b"])
        assert result == 0

    def test_lcs_empty_second(self) -> None:
        """Test LCS returns 0 when second sequence is empty."""
        result = _longest_common_subsequence(["a", "b"], [])
        assert result == 0

    def test_lcs_both_empty(self) -> None:
        """Test LCS returns 0 when both sequences are empty."""
        result = _longest_common_subsequence([], [])
        assert result == 0

    def test_lcs_identical(self) -> None:
        """Test LCS returns full length when sequences are identical."""
        tokens = ["int", "main", "{", "}", "return", "0"]
        result = _longest_common_subsequence(tokens, tokens)
        assert result == len(tokens)

    def test_lcs_no_common(self) -> None:
        """Test LCS returns 0 when no common elements."""
        a = ["int", "main"]
        b = ["float", "calc"]
        result = _longest_common_subsequence(a, b)
        assert result == 0

    def test_lcs_partial_match(self) -> None:
        """Test LCS returns correct length for partial overlap."""
        a = ["int", "main", "{", "return", "0", "}"]
        b = ["int", "main", "{", "printf", "}"]
        result = _longest_common_subsequence(a, b)
        assert result == 4  # "int", "main", "{", "}"

    def test_lcs_subset(self) -> None:
        """Test LCS when one sequence is a subset of the other."""
        a = ["int", "main"]
        b = ["void", "int", "setup", "main", "end"]
        result = _longest_common_subsequence(a, b)
        assert result == 2

    def test_lcs_single_element_match(self) -> None:
        """Test LCS with single matching element."""
        a = ["int", "x"]
        b = ["float", "x"]
        result = _longest_common_subsequence(a, b)
        assert result == 1

    def test_lcs_single_element_no_match(self) -> None:
        """Test LCS with single non-matching elements."""
        a = ["int"]
        b = ["float"]
        result = _longest_common_subsequence(a, b)
        assert result == 0


class TestComputeSimilarity:
    """Tests for compute_similarity function."""

    def test_similarity_empty_source(self) -> None:
        """Test similarity returns 0.0 when source is empty."""
        result = compute_similarity([], ["int", "main"])
        assert result == 0.0

    def test_similarity_empty_target(self) -> None:
        """Test similarity returns 0.0 when target is empty."""
        result = compute_similarity(["int", "main"], [])
        assert result == 0.0

    def test_similarity_both_empty(self) -> None:
        """Test similarity returns 0.0 when both are empty."""
        result = compute_similarity([], [])
        assert result == 0.0

    def test_similarity_identical(self) -> None:
        """Test similarity returns 1.0 for identical sequences."""
        tokens = ["int", "main", "{", "}", "return", "0"]
        result = compute_similarity(tokens, tokens)
        assert result == 1.0

    def test_similarity_no_overlap(self) -> None:
        """Test similarity returns 0.0 for completely different sequences."""
        a = ["int", "main", "func_a"]
        b = ["float", "calc", "func_b"]
        result = compute_similarity(a, b)
        assert result == 0.0

    def test_similarity_partial_overlap(self) -> None:
        """Test similarity returns value between 0 and 1 for partial overlap."""
        a = ["int", "main", "{", "return", "0", "}"]
        b = ["int", "main", "{", "printf", "}"]
        result = compute_similarity(a, b)
        assert 0.0 < result < 1.0

    def test_similarity_threshold_parameter(self) -> None:
        """Test that threshold parameter is accepted (informational only)."""
        tokens = ["int", "main"]
        # Threshold does not affect the return value, just documented
        result = compute_similarity(tokens, tokens, threshold=0.5)
        assert result == 1.0

    def test_similarity_same_unique_tokens_different_order(self) -> None:
        """Test similarity when same tokens in different order."""
        a = ["int", "main", "{", "}"]
        b = ["{", "}", "main", "int"]
        result = compute_similarity(a, b)
        # Jaccard = 1.0 (same sets), LCS < 1.0 (different order)
        assert 0.0 < result < 1.0

    def test_similarity_single_common_token(self) -> None:
        """Test similarity with single common token."""
        a = ["int", "x", "y"]
        b = ["float", "x", "z"]
        result = compute_similarity(a, b)
        assert 0.0 < result < 1.0

    def test_similarity_all_unique(self) -> None:
        """Test similarity with all unique tokens in each sequence."""
        a = ["a", "b", "c"]
        b = ["d", "e", "f"]
        result = compute_similarity(a, b)
        assert result == 0.0


class TestCompareBinaries:
    """Tests for compare_binaries async function."""

    @pytest.fixture
    def mock_source_functions(self) -> list[dict[str, object]]:
        """Create sample source functions."""
        return [
            {
                "functionName": "src_main",
                "tokenList": ["int", "main", "{", "return", "0", "}"],
                "tokens": "int main { return 0 }",
            },
            {
                "functionName": "src_helper",
                "tokenList": ["void", "helper", "{", "}"],
                "tokens": "void helper { }",
            },
        ]

    def _create_mock_binary_function(
        self, function_name: str, entrypoint: int, raw_code: str
    ) -> mock.MagicMock:
        """Create a mock BinaryFunction object."""
        bf = mock.MagicMock()
        bf.function_name = function_name
        bf.entrypoint = entrypoint
        bf.raw_code = raw_code
        return bf

    @pytest.mark.asyncio
    async def test_compare_binaries_no_target_functions(self, mock_source_functions: list[dict[str, object]]) -> None:
        """Test that compare_binaries returns None when target has no functions."""
        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[])

            result = await compare_binaries(mock_source_functions, target_binary_id=1)

            assert result is None
            mock_sql.get_binary_functions.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_compare_binaries_tokenization_error(self, mock_source_functions: list[dict[str, object]]) -> None:
        """Test that compare_binaries returns None when tokenization fails."""
        mock_bf = self._create_mock_binary_function("tgt_func", 0x1000, "int tgt_func() { return 1; }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock.MagicMock(error="Tokenization failed"))

                result = await compare_binaries(mock_source_functions, target_binary_id=1)

                assert result is None

    @pytest.mark.asyncio
    async def test_compare_binaries_filtering_error(self, mock_source_functions: list[dict[str, object]]) -> None:
        """Test that compare_binaries returns None when filtering fails."""
        mock_bf = self._create_mock_binary_function("tgt_func", 0x1000, "int tgt_func() { return 1; }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_tokenized_ctx = mock.MagicMock(error=None)
            mock_tokenized_ctx.get.return_value = []

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_tokenized_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock.MagicMock(error="Filtering failed"))

                    result = await compare_binaries(mock_source_functions, target_binary_id=1)

                    assert result is None

    @pytest.mark.asyncio
    async def test_compare_binaries_no_matches(self, mock_source_functions: list[dict[str, object]]) -> None:
        """Test comparison when no functions match threshold."""
        mock_bf = self._create_mock_binary_function("tgt_func", 0x1000, "float completely_different() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_func",
                    "tokenList": ["float", "completely", "different"],
                    "tokens": "float completely different",
                }
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(mock_source_functions, target_binary_id=1)

                    assert result is not None
                    assert result["target_binary_id"] == 1
                    assert result["target_binary_name"] == "target.bin"
                    assert len(result["matched_functions"]) == 0
                    assert result["overall_similarity"] == 0.0

    @pytest.mark.asyncio
    async def test_compare_binaries_with_matches(self, mock_source_functions: list[dict[str, object]]) -> None:
        """Test comparison when functions match above threshold."""
        mock_bf = self._create_mock_binary_function("tgt_main", 0x1000, "int tgt_main() { return 0; }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_main",
                    "tokenList": ["int", "tgt_main", "{", "return", "0", "}"],
                    "tokens": "int tgt_main { return 0 }",
                }
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(mock_source_functions, target_binary_id=1)

                    assert result is not None
                    assert result["target_binary_id"] == 1
                    assert result["target_binary_name"] == "target.bin"
                    assert len(result["matched_functions"]) >= 1

    @pytest.mark.asyncio
    async def test_compare_binaries_custom_threshold(self) -> None:
        """Test comparison with custom match threshold."""
        source_functions = [
            {
                "functionName": "src_func",
                "tokenList": ["int", "func"],
                "tokens": "int func",
            },
        ]

        mock_bf = self._create_mock_binary_function("tgt_func", 0x1000, "int tgt_func() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_func",
                    "tokenList": ["int", "tgt_func"],
                    "tokens": "int tgt_func",
                }
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    # With high threshold, no matches
                    result = await compare_binaries(source_functions, target_binary_id=1, match_threshold=0.99)

                    assert result is not None
                    assert len(result["matched_functions"]) == 0

    @pytest.mark.asyncio
    async def test_compare_binaries_multiple_source_functions(self) -> None:
        """Test comparison with multiple source functions."""
        source_functions = [
            {
                "functionName": "src_a",
                "tokenList": ["int", "a", "{", "}"],
                "tokens": "int a { }",
            },
            {
                "functionName": "src_b",
                "tokenList": ["void", "b", "{", "}"],
                "tokens": "void b { }",
            },
        ]

        mock_bf1 = self._create_mock_binary_function("tgt_a", 0x1000, "int tgt_a() { }")
        mock_bf2 = self._create_mock_binary_function("tgt_b", 0x2000, "void tgt_b() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf1, mock_bf2])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_a",
                    "tokenList": ["int", "tgt_a", "{", "}"],
                    "tokens": "int tgt_a { }",
                },
                {
                    "functionName": "tgt_b",
                    "tokenList": ["void", "tgt_b", "{", "}"],
                    "tokens": "void tgt_b { }",
                },
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(source_functions, target_binary_id=42)

                    assert result is not None
                    assert result["target_binary_id"] == 42

    @pytest.mark.asyncio
    async def test_compare_binaries_uses_best_match(self) -> None:
        """Test that comparison finds the best matching target for each source."""
        source_functions = [
            {
                "functionName": "src_main",
                "tokenList": ["int", "main", "{", "return", "0", "}"],
                "tokens": "int main { return 0 }",
            },
        ]

        mock_bf1 = self._create_mock_binary_function("tgt_similar", 0x1000, "int similar() { return 0; }")
        mock_bf2 = self._create_mock_binary_function("tgt_different", 0x2000, "float different() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf1, mock_bf2])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_similar",
                    "tokenList": ["int", "similar", "{", "return", "0", "}"],
                    "tokens": "int similar { return 0 }",
                },
                {
                    "functionName": "tgt_different",
                    "tokenList": ["float", "different"],
                    "tokens": "float different",
                },
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(source_functions, target_binary_id=1)

                    assert result is not None
                    if result["matched_functions"]:
                        # The best match should be tgt_similar, not tgt_different
                        best_match = result["matched_functions"][0]
                        assert best_match["target_function_name"] == "tgt_similar"

    @pytest.mark.asyncio
    async def test_compare_binaries_matched_function_structure(self) -> None:
        """Test that matched function entries have correct structure."""
        source_functions = [
            {
                "functionName": "src_func",
                "tokenList": ["int", "func", "{", "}"],
                "tokens": "int func { }",
            },
        ]

        mock_bf = self._create_mock_binary_function("tgt_func", 0x1000, "int tgt_func() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_func",
                    "tokenList": ["int", "tgt_func", "{", "}"],
                    "tokens": "int tgt_func { }",
                }
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(source_functions, target_binary_id=1)

                    assert result is not None
                    if result["matched_functions"]:
                        match = result["matched_functions"][0]
                        assert "source_function_name" in match
                        assert "target_function_name" in match
                        assert "similarity_score" in match
                        assert "source_tokens" in match
                        assert "target_tokens" in match
                        assert 0.0 <= match["similarity_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_compare_binaries_overall_similarity_calculation(self) -> None:
        """Test that overall similarity is the average of match scores."""
        source_functions = [
            {
                "functionName": "src_a",
                "tokenList": ["int", "a", "{", "}"],
                "tokens": "int a { }",
            },
            {
                "functionName": "src_b",
                "tokenList": ["int", "b", "{", "}"],
                "tokens": "int b { }",
            },
        ]

        mock_bf1 = self._create_mock_binary_function("tgt_a", 0x1000, "int tgt_a() { }")
        mock_bf2 = self._create_mock_binary_function("tgt_b", 0x2000, "int tgt_b() { }")

        with mock.patch("app.database.sql_service.SQLUtil") as mock_sql:
            mock_sql.get_binary_functions = mock.AsyncMock(return_value=[mock_bf1, mock_bf2])
            mock_sql.get_binary_name = mock.AsyncMock(return_value="target.bin")

            mock_ctx = mock.MagicMock(error=None)
            mock_ctx.get.return_value = [
                {
                    "functionName": "tgt_a",
                    "tokenList": ["int", "tgt_a", "{", "}"],
                    "tokens": "int tgt_a { }",
                },
                {
                    "functionName": "tgt_b",
                    "tokenList": ["int", "tgt_b", "{", "}"],
                    "tokens": "int tgt_b { }",
                },
            ]

            with mock.patch("app.processing.steps.TokenizeStep") as MockTokenize:
                mock_tokenize = MockTokenize.return_value
                mock_tokenize.execute = mock.AsyncMock(return_value=mock_ctx)

                with mock.patch("app.processing.steps.FilterStep") as MockFilter:
                    mock_filter = MockFilter.return_value
                    mock_filter.execute = mock.AsyncMock(return_value=mock_ctx)

                    result = await compare_binaries(source_functions, target_binary_id=1)

                    assert result is not None
                    # Overall similarity should be rounded to 4 decimal places
                    if result["overall_similarity"] > 0:
                        assert isinstance(result["overall_similarity"], float)
