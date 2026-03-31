"""Unit tests for Ghidra decompiler processing and token manipulation."""
import pytest
from unittest import mock

from app.processing.ghidra_processor import (
    check_if_variable,
    remove_comments,
    filter_tokens,
    analyze_binary_and_decompile,
)


class TestTokenLogic:
    """Tests for pure-Python string manipulation logic in token processing."""

    @pytest.mark.parametrize(
        "token, expected",
        [
            ("var1", True),
            ("local_10", True),
            ("stack0", True),
            ("int", False),
            ("FUN_00401000", False),
        ],
    )
    def test_variable_regex(self, token, expected):
        """Test variable detection regex against various token formats."""
        assert check_if_variable(token) == expected

    def test_comment_removal_edge_cases(self):
        """Test comment removal handles both closed and unclosed comments."""
        tokens = ["code", "/*", "comment", "*/", "more_code"]
        assert remove_comments(tokens) == ["code", "more_code"]

        unclosed = ["start", "/*", "unclosed"]
        assert remove_comments(unclosed) == ["start"]

    def test_filter_pipeline(self):
        """Test token filtering pipeline transforms tokens correctly."""
        raw = ["FUN_123", "0x401000", "var1", "undefined4", "keep_me"]
        result = filter_tokens(raw)
        assert result == ["FUNCTION", "HEX", "VARIABLE", "undefined", "keep_me"]


class TestDecompilerConfig:
    """Tests for decompiler configuration and setup."""

    def test_setup_decompiler_settings(self):
        """Test that decompiler is configured with correct toggles."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()

        with mock.patch("ghidra.app.decompiler.DecompInterface") as MockDI:
            instance = MockDI.return_value
            from app.processing.ghidra_processor import setup_decompiler

            setup_decompiler(mock_state, mock_program, decomp_interface=instance)
            instance.toggleCCode.assert_called_with(True)
            instance.setSimplificationStyle.assert_called_with("decompile")
            instance.openProgram.assert_called_with(mock_program)