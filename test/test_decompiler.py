import pytest
from unittest import mock

from app.ghidra_processor import (
    check_if_variable, 
    remove_comments, 
    filter_tokens, 
    analyze_binary_and_decompile
)

class TestTokenLogic:
    """Tests the pure-Python string manipulation logic."""

    @pytest.mark.parametrize("token, expected", [
        ("var1", True),
        ("local_10", True),
        ("stack0", True),
        ("int", False),
        ("FUN_00401000", False),
    ])
    def test_variable_regex(self, token, expected):
        assert check_if_variable(token) == expected

    def test_comment_removal_edge_cases(self):
        tokens = ["code", "/*", "comment", "*/", "more_code"]
        assert remove_comments(tokens) == ["code", "more_code"]
        
        unclosed = ["start", "/*", "unclosed"]
        assert remove_comments(unclosed) == ["start"]

    def test_filter_pipeline(self):
        raw = ["FUN_123", "0x401000", "var1", "undefined4", "keep_me"]
        result = filter_tokens(raw)
        assert result == ["FUNCTION", "HEX", "VARIABLE", "undefined", "keep_me"]


class TestOrchestration:
    """Tests the 'Path to Decompilation' workflow using Mocks."""

    @mock.patch("pyghidra.open_program")
    @mock.patch("pyghidra.is_started")
    @mock.patch("pyghidra.start")
    def test_full_pipeline_path_logic(self, mock_start, mock_is_started, mock_open):
        """Ensures the code talks to Ghidra correctly given a string path."""
        mock_is_started.return_value = False
        
        mock_program = mock.MagicMock()
        mock_open.return_value.__enter__.return_value = mock_program
        
        mock_iter = mock_program.getFunctionManager().getFunctions.return_value
        mock_iter.hasNext.side_effect = [True, False]
        
        test_path = "/workspaces/Glyph/binaries/test.bin"

        with mock.patch("app.ghidra_processor.setup_decompiler") as mock_setup:
            mock_setup.return_value = mock.MagicMock()
            
            result = analyze_binary_and_decompile(test_path)
            mock_start.assert_called_once()
            mock_open.assert_called_once_with(test_path)
            mock_program.analyze.assert_called_once()
            assert "functions" in result

class TestDecompilerConfig:
    """Tests that the decompiler is set up with the right toggles."""

    def test_setup_decompiler_settings(self):
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        
        with mock.patch("ghidra.app.decompiler.DecompInterface") as MockDI:
            instance = MockDI.return_value
            from app.ghidra_processor import setup_decompiler
            
            setup_decompiler(mock_state, mock_program, decomp_interface=instance)
            instance.toggleCCode.assert_called_with(True)
            instance.setSimplificationStyle.assert_called_with("decompile")
            instance.openProgram.assert_called_with(mock_program)
