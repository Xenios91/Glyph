"""Unit tests for Ghidra decompiler processing and token manipulation."""
import pytest
from unittest import mock

from app.processing.ghidra_processor import (
    analyze_binary_and_decompile,
)


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