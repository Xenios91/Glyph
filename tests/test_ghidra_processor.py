"""Comprehensive tests for Ghidra processor module."""

import types
from collections.abc import Iterator
from unittest import mock

import pytest
from app.processing.ghidra_processor import (
    analyze_binary_and_decompile,
    decompile_all_functions,
    get_function_tokens,
    setup_decompiler,
)


class TestSetupDecompiler:
    """Tests for setup_decompiler function."""

    def test_setup_decompiler_with_existing_interface(self) -> None:
        """Test setup with provided decomp_interface."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        mock_interface = mock.MagicMock()

        result = setup_decompiler(mock_state, mock_program, decomp_interface=mock_interface)

        assert result is mock_interface
        mock_interface.setOptions.assert_called_once()
        mock_interface.toggleCCode.assert_called_once_with(True)
        mock_interface.toggleSyntaxTree.assert_called_once_with(True)
        mock_interface.setSimplificationStyle.assert_called_once_with("decompile")
        mock_interface.openProgram.assert_called_once_with(mock_program)

    def test_setup_decompiler_creates_fallback_when_none_and_import_fails(self) -> None:
        """Test setup creates fallback DecompInterface when none provided and import fails.

        conftest.py mocks Ghidra imports so the code hits the ImportError fallback,
        creating mock types. We test that it still works.
        """
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()

        # When decomp_interface is None and import fails, it creates a mock type instance
        result = setup_decompiler(mock_state, mock_program)

        # Result should be the mock type instance (not None)
        assert result is not None

    def test_setup_decompiler_returns_interface(self) -> None:
        """Test that setup returns the configured interface."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        mock_interface = mock.MagicMock()

        result = setup_decompiler(mock_state, mock_program, decomp_interface=mock_interface)

        assert result is mock_interface

    def test_setup_decompiler_num_processors_default(self) -> None:
        """Test that num_processors defaults to 2 (but is not used in current impl)."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        mock_interface = mock.MagicMock()

        # Should not raise even with default num_processors
        result = setup_decompiler(mock_state, mock_program, decomp_interface=mock_interface)
        assert result is mock_interface

    def test_setup_decompiler_custom_num_processors(self) -> None:
        """Test setup with custom num_processors value."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        mock_interface = mock.MagicMock()

        result = setup_decompiler(mock_state, mock_program, num_processors=4, decomp_interface=mock_interface)
        assert result is mock_interface

    def test_setup_decompiler_configures_options(self) -> None:
        """Test that all decompiler options are configured."""
        mock_program = mock.MagicMock()
        mock_state = mock.MagicMock()
        mock_interface = mock.MagicMock()

        setup_decompiler(mock_state, mock_program, decomp_interface=mock_interface)

        # Verify setOptions was called with DecompileOptions instance
        call_args = mock_interface.setOptions.call_args
        assert call_args is not None
        # The argument passed should be the DecompileOptions instance (mock type when import fails)
        assert call_args[0][0] is not None


class _MockArrayList:
    """Mock Java ArrayList that stores items added via add() and is iterable."""

    def __init__(self) -> None:
        self._items: list[str] = []

    def add(self, item: str) -> None:
        self._items.append(str(item))

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def _setup_java_util() -> None:
    """Set up java.util in sys.modules for get_function_tokens tests.

    PROBLEM: conftest.py sets sys.modules["java"] = MagicMock(). When Python
    evaluates `import java.util`, it does getattr(sys.modules["java"], "util")
    which creates a NEW MagicMock child, completely ignoring any
    sys.modules["java.util"] we set. So our _MockArrayList is never used.

    SOLUTION: Replace sys.modules["java"] with a real types.ModuleType so that
    `import java.util` properly loads from sys.modules["java.util"] where we
    have our _MockArrayList set up.
    """
    import sys

    java_module = types.ModuleType("java")
    java_util_module = types.ModuleType("java.util")
    java_util_module.ArrayList = _MockArrayList  # type: ignore[attr-defined]
    java_module.util = java_util_module  # type: ignore[attr-defined]
    sys.modules["java"] = java_module
    sys.modules["java.util"] = java_util_module


class TestGetFunctionTokens:
    """Tests for get_function_tokens function."""

    def _create_mock_decompiled(
        self, tokens: list[str], plain_c: str | None, raise_plain_c: bool = False,
    ) -> mock.MagicMock:
        """Create mock decompiled result with tokens and plain C code."""
        mock_decompiled = mock.MagicMock()
        mock_decompiled.decompileCompleted.return_value = True

        if raise_plain_c:
            mock_decompiled.getPlainC.side_effect = Exception("Cannot get plain C")
        else:
            mock_decompiled.getPlainC.return_value = plain_c

        # Create mock ccode_markup whose flatten() populates the passed ArrayList
        mock_ccode_markup = mock.MagicMock()

        def _populate_list(token_list: _MockArrayList) -> None:
            for token in tokens:
                token_list.add(token)

        mock_ccode_markup.flatten.side_effect = _populate_list
        mock_decompiled.getCCodeMarkup.return_value = mock_ccode_markup

        return mock_decompiled

    def test_get_function_tokens_success(self) -> None:
        """Test successful token extraction with raw C code."""
        mock_function = mock.MagicMock()
        mock_function.getName.return_value = "test_func"
        mock_interface = mock.MagicMock()

        tokens = ["int", "main", "(", ")", "{", "return", "0", "}"]
        plain_c = "int main() { return 0; }"

        mock_decompiled = self._create_mock_decompiled(tokens, plain_c)
        mock_interface.decompileFunction.return_value = mock_decompiled

        # Set up java.util.ArrayList directly (see _setup_java_util docstring)
        _setup_java_util()
        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == tokens
        assert result_raw == plain_c
        mock_interface.decompileFunction.assert_called_once()

    def test_get_function_tokens_decompile_failed(self) -> None:
        """Test returns empty when decompilation fails."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()
        mock_interface.decompileFunction.return_value = None

        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == []
        assert result_raw == ""

    def test_get_function_tokens_decompile_not_completed(self) -> None:
        """Test returns empty when decompileCompleted returns False."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()
        mock_decompiled = mock.MagicMock()
        mock_decompiled.decompileCompleted.return_value = False
        mock_interface.decompileFunction.return_value = mock_decompiled

        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == []
        assert result_raw == ""

    def test_get_function_tokens_exception(self) -> None:
        """Test returns empty on exception during decompilation."""
        mock_function = mock.MagicMock()
        mock_function.getName.return_value = "bad_func"
        mock_interface = mock.MagicMock()
        mock_interface.decompileFunction.side_effect = Exception("Decompilation error")

        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == []
        assert result_raw == ""

    def test_get_function_tokens_plain_c_exception_fallback(self) -> None:
        """Test fallback to joined tokens when getPlainC fails."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()

        tokens = ["int", "main", "(", ")", "{", "return", "0", "}"]

        mock_decompiled = self._create_mock_decompiled(tokens, None, raise_plain_c=True)
        mock_interface.decompileFunction.return_value = mock_decompiled

        _setup_java_util()
        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == tokens
        assert result_raw == " ".join(tokens)

    def test_get_function_tokens_plain_c_none(self) -> None:
        """Test empty raw_code when getPlainC returns None."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()

        tokens = ["int", "main"]

        mock_decompiled = self._create_mock_decompiled(tokens, None)
        mock_interface.decompileFunction.return_value = mock_decompiled

        _setup_java_util()
        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == tokens
        assert result_raw == ""

    def test_get_function_tokens_filters_empty_strings(self) -> None:
        """Test that empty/whitespace tokens are filtered out."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()

        raw_tokens = ["int", "", "  ", "main", "\t"]
        expected_tokens = ["int", "main"]

        mock_decompiled = self._create_mock_decompiled(raw_tokens, "int main")
        mock_interface.decompileFunction.return_value = mock_decompiled

        _setup_java_util()
        result_tokens, _result_raw = get_function_tokens(mock_function, mock_interface)

        assert result_tokens == expected_tokens

    def test_get_function_tokens_with_mock_java_import(self) -> None:
        """Test that function works when java.util import succeeds."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()

        tokens = ["int", "main"]

        mock_decompiled = self._create_mock_decompiled(tokens, "int main")
        mock_interface.decompileFunction.return_value = mock_decompiled

        _setup_java_util()
        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)
        assert result_tokens == ["int", "main"]
        assert result_raw == "int main"

    def test_get_function_tokens_empty_token_list(self) -> None:
        """Test that empty token list returns empty results with raw C code."""
        mock_function = mock.MagicMock()
        mock_interface = mock.MagicMock()

        mock_decompiled = mock.MagicMock()
        mock_decompiled.decompileCompleted.return_value = True
        mock_decompiled.getPlainC.return_value = "void empty()"
        mock_ccode_markup = mock.MagicMock()
        mock_decompiled.getCCodeMarkup.return_value = mock_ccode_markup
        mock_interface.decompileFunction.return_value = mock_decompiled

        _setup_java_util()
        result_tokens, result_raw = get_function_tokens(mock_function, mock_interface)
        assert result_tokens == []
        assert result_raw == "void empty()"


class TestDecompileAllFunctions:
    """Tests for decompile_all_functions function."""

    def test_decompile_all_functions_success(self) -> None:
        """Test successful decompilation of all functions."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func = mock.MagicMock()
        mock_func.getName.return_value = "main"
        mock_func.isExternal.return_value = False
        mock_func.getReturnType.return_value = "void"
        mock_func.getParameters.return_value = []

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = (["int", "main"], "int main() {}")

                result = decompile_all_functions(mock_state, mock_program)

                assert len(result["functions"]) == 1
                assert result["functions"][0]["functionName"] == "main"
                assert result["functions"][0]["tokenList"] == ["int", "main"]
                assert len(result["erroredFunctions"]) == 0
                mock_interface.dispose.assert_called_once()

    def test_decompile_all_functions_skips_external(self) -> None:
        """Test that external functions are skipped."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_external_func = mock.MagicMock()
        mock_external_func.isExternal.return_value = True

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_external_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                result = decompile_all_functions(mock_state, mock_program)

                assert len(result["functions"]) == 0
                assert len(result["erroredFunctions"]) == 0
                mock_get_tokens.assert_not_called()
                mock_interface.dispose.assert_called_once()

    def test_decompile_all_functions_handles_decompilation_failure(self) -> None:
        """Test that failed decompilations are recorded in erroredFunctions."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func = mock.MagicMock()
        mock_func.getName.return_value = "bad_func"
        mock_func.isExternal.return_value = False

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = ([], "")

                result = decompile_all_functions(mock_state, mock_program)

                assert len(result["functions"]) == 0
                assert len(result["erroredFunctions"]) == 1
                assert result["erroredFunctions"][0]["functionName"] == "bad_func"
                assert result["erroredFunctions"][0]["error"] == "Decompilation failed"

    def test_decompile_all_functions_undefined_return_type(self) -> None:
        """Test that undefined return type is normalized."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func = mock.MagicMock()
        mock_func.getName.return_value = "mystery"
        mock_func.isExternal.return_value = False
        mock_func.getReturnType.return_value = "undefined[]"
        mock_func.getParameters.return_value = []

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = (["undefined"], "undefined func()")

                result = decompile_all_functions(mock_state, mock_program)

                assert result["functions"][0]["returnType"] == "undefined"

    def test_decompile_all_functions_defined_return_type(self) -> None:
        """Test that defined return type is preserved."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func = mock.MagicMock()
        mock_func.getName.return_value = "calc"
        mock_func.isExternal.return_value = False
        mock_func.getReturnType.return_value = "int"
        mock_func.getParameters.return_value = ["a", "b"]

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = (["int", "calc"], "int calc(int a, int b)")

                result = decompile_all_functions(mock_state, mock_program)

                assert result["functions"][0]["returnType"] == "int"
                assert result["functions"][0]["parameterCount"] == 2

    def test_decompile_all_functions_empty_program(self) -> None:
        """Test handling of program with no functions."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.return_value = False
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            result = decompile_all_functions(mock_state, mock_program)

            assert result == {"functions": [], "erroredFunctions": []}
            mock_interface.dispose.assert_called_once()

    def test_decompile_all_functions_multiple_functions(self) -> None:
        """Test handling multiple functions in a program."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func1 = mock.MagicMock()
        mock_func1.getName.return_value = "func1"
        mock_func1.isExternal.return_value = False

        mock_func2 = mock.MagicMock()
        mock_func2.getName.return_value = "func2"
        mock_func2.isExternal.return_value = False

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, True, False]
        mock_func_iter.next.side_effect = [mock_func1, mock_func2]
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = (["tokens"], "code")

                result = decompile_all_functions(mock_state, mock_program)

                assert len(result["functions"]) == 2
                assert result["functions"][0]["functionName"] == "func1"
                assert result["functions"][1]["functionName"] == "func2"

    def test_decompile_all_functions_disposes_interface(self) -> None:
        """Test that decomp interface is disposed after processing."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.return_value = False
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            decompile_all_functions(mock_state, mock_program)

            mock_interface.dispose.assert_called_once()

    def test_decompile_all_functions_includes_raw_code(self) -> None:
        """Test that raw_code is included in function entries."""
        mock_state = mock.MagicMock()
        mock_program = mock.MagicMock()

        mock_func = mock.MagicMock()
        mock_func.getName.return_value = "main"
        mock_func.isExternal.return_value = False

        mock_func_manager = mock.MagicMock()
        mock_func_iter = mock.MagicMock()
        mock_func_iter.hasNext.side_effect = [True, False]
        mock_func_iter.next.return_value = mock_func
        mock_func_manager.getFunctions.return_value = mock_func_iter
        mock_program.getFunctionManager.return_value = mock_func_manager

        with mock.patch("app.processing.ghidra_processor.setup_decompiler") as mock_setup:
            mock_interface = mock.MagicMock()
            mock_setup.return_value = mock_interface

            with mock.patch("app.processing.ghidra_processor.get_function_tokens") as mock_get_tokens:
                mock_get_tokens.return_value = (["int", "main"], "int main() { return 0; }")

                result = decompile_all_functions(mock_state, mock_program)

                assert result["functions"][0]["raw_code"] == "int main() { return 0; }"


class TestAnalyzeBinaryAndDecompile:
    """Tests for analyze_binary_and_decompile function."""

    def test_analyze_binary_pyghidra_not_started(self) -> None:
        """Test that pyghidra.start() is called when not started."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        with mock.patch.dict("sys.modules", {"pyghidra": mock_pyghidra}):
            with mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile:
                mock_decompile.return_value = {"functions": []}

                result = analyze_binary_and_decompile("/path/to/binary")

                mock_pyghidra.start.assert_called_once()
                assert result == {"functions": []}

    def test_analyze_binary_pyghidra_already_started(self) -> None:
        """Test that pyghidra.start() is not called when already started."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = True

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        with mock.patch.dict("sys.modules", {"pyghidra": mock_pyghidra}):
            with mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile:
                mock_decompile.return_value = {"functions": []}

                analyze_binary_and_decompile("/path/to/binary")

                mock_pyghidra.start.assert_not_called()

    def test_analyze_binary_runs_analysis(self) -> None:
        """Test that analyzeAll is called when shouldAskToAnalyze returns True."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        # Set up ghidra.program.util in sys.modules so the import succeeds
        mock_ghidra_program_util = types.ModuleType("ghidra.program.util")
        mock_utils = mock.MagicMock()
        mock_utils.shouldAskToAnalyze.return_value = True
        mock_ghidra_program_util.GhidraProgramUtilities = mock_utils  # type: ignore[attr-defined]

        with (
            mock.patch.dict(
                "sys.modules",
                {
                    "pyghidra": mock_pyghidra,
                    "ghidra.program.util": mock_ghidra_program_util,
                },
            ),
            mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile,
        ):
            mock_decompile.return_value = {"functions": []}

            analyze_binary_and_decompile("/path/to/binary")

            mock_flat_api.analyzeAll.assert_called_once_with(mock_program)

    def test_analyze_binary_skips_analysis_if_not_needed(self) -> None:
        """Test that analyzeAll is skipped when shouldAskToAnalyze is False."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        # Must also provide ghidra.program.util in sys.modules so the
        # `from ghidra.program.util import GhidraProgramUtilities` succeeds.
        mock_ghidra_program_util = types.ModuleType("ghidra.program.util")
        mock_utils = mock.MagicMock()
        mock_utils.shouldAskToAnalyze.return_value = False
        mock_ghidra_program_util.GhidraProgramUtilities = mock_utils

        with (
            mock.patch.dict(
                "sys.modules",
                {
                    "pyghidra": mock_pyghidra,
                    "ghidra.program.util": mock_ghidra_program_util,
                },
            ),
            mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile,
        ):
            mock_decompile.return_value = {"functions": []}

            analyze_binary_and_decompile("/path/to/binary")

            mock_flat_api.analyzeAll.assert_not_called()

    def test_analyze_binary_import_error_gpidra_program_utilities(self) -> None:
        """Test fallback when GhidraProgramUtilities import fails."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        with mock.patch.dict("sys.modules", {"pyghidra": mock_pyghidra, "ghidra.program.util": None}):
            with mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile:
                mock_decompile.return_value = {"functions": []}

                analyze_binary_and_decompile("/path/to/binary")

                # Should fall back to analyzeAll
                mock_flat_api.analyzeAll.assert_called_once_with(mock_program)

    def test_analyze_binary_returns_decompiled_functions(self) -> None:
        """Test that decompiled functions are returned."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        expected_result = {"functions": [{"functionName": "main"}]}

        with mock.patch.dict("sys.modules", {"pyghidra": mock_pyghidra}):
            with mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile:
                mock_decompile.return_value = expected_result

                result = analyze_binary_and_decompile("/path/to/binary")

                assert result == expected_result
                mock_decompile.assert_called_once_with(None, mock_program)

    def test_analyze_binary_opens_with_correct_params(self) -> None:
        """Test that open_program is called with correct parameters."""
        mock_pyghidra = mock.MagicMock()
        mock_pyghidra.started.return_value = False

        mock_flat_api = mock.MagicMock()
        mock_program = mock.MagicMock()
        mock_flat_api.getCurrentProgram.return_value = mock_program

        mock_context = mock.MagicMock()
        mock_context.__enter__ = mock.MagicMock(return_value=mock_flat_api)
        mock_context.__exit__ = mock.MagicMock(return_value=False)
        mock_pyghidra.open_program.return_value = mock_context

        with mock.patch.dict("sys.modules", {"pyghidra": mock_pyghidra}):
            with mock.patch("app.processing.ghidra_processor.decompile_all_functions") as mock_decompile:
                mock_decompile.return_value = {"functions": []}

                analyze_binary_and_decompile("/path/to/binary")

                mock_pyghidra.open_program.assert_called_once_with(
                    "/path/to/binary", project_location="/tmp/", analyze=False,
                )

    def test_analyze_binary_import_error_fallback(self) -> None:
        """Test fallback when pyghidra import fails."""
        # When pyghidra import fails, open_program returns None which causes issues
        # This tests the ImportError fallback creates a mock pyghidra
        with mock.patch.dict("sys.modules", {"pyghidra": None}):
            # The fallback creates: type("pyghidra", (), {"started": lambda: False, "start": lambda: None, "open_program": lambda *a, **k: None})
            # open_program returns None, so with statement will fail
            with pytest.raises((AttributeError, TypeError)):
                analyze_binary_and_decompile("/path/to/binary")
