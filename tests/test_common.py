"""Unit tests for common utility functions."""

from typing import Any

from app.utils.common import binary_function_to_dict, build_prediction_details_response, format_code


class TestFormatCode:
    """Tests for format_code function."""

    def test_format_simple_function(self):
        """Test formatting a simple C function."""
        code = "int main() { return 0; }"
        result = format_code(code)
        assert "int main()" in result
        assert "return 0" in result
        assert ";" in result
        assert "{" in result
        assert "}" in result

    def test_format_function_with_body(self):
        """Test formatting a function with multiple statements."""
        code = "void func() { int x = 1; int y = 2; return; }"
        result = format_code(code)
        assert "void func()" in result
        assert "int x = 1" in result
        assert "int y = 2" in result
        assert "return" in result

    def test_format_empty_function(self):
        """Test formatting an empty function."""
        code = "void empty() { }"
        result = format_code(code)
        assert "void empty()" in result

    def test_format_function_with_nested_braces(self):
        """Test formatting a function with nested braces."""
        code = "void func() { if (1) { return; } }"
        result = format_code(code)
        assert "void func()" in result
        assert "if (1)" in result
        assert "return" in result

    def test_format_function_with_semicolons(self):
        """Test that semicolons are properly formatted."""
        code = "void func() { int a; int b; }"
        result = format_code(code)
        # Check that semicolons are present (with possible space before them)
        assert "int a" in result and ";" in result
        assert "int b" in result and ";" in result

    def test_format_preserves_function_signature(self):
        """Test that function signature is preserved."""
        code = "int add(int a, int b) { return a + b; }"
        result = format_code(code)
        assert "int add(int a, int b)" in result
        assert "return a + b" in result

    def test_format_code_string_with_braces(self):
        """Braces inside string literals must not affect brace-depth tracking."""
        code = 'void f() { char *s = "{ not a brace }"; int x = 1; }'
        result = format_code(code)
        # The string literal is preserved verbatim.
        assert '{ not a brace }' in result
        # The function body is still well-formed and closed.
        assert "int x = 1" in result
        assert result.count("{") == result.count("}")

    def test_format_code_escaped_quote_in_string(self):
        """Escaped quotes inside string literals must not break string parsing."""
        code = 'void f() { char *s = "say \\"hi\\""; return; }'
        result = format_code(code)
        assert 'say \\"hi\\"' in result
        assert "return" in result

    def test_format_code_missing_closing_brace(self):
        """A missing closing brace must fall back and still balance the output."""
        code = "void f() { int x = 1; if (x) { return; }"
        result = format_code(code)
        # The formatter must emit a balanced result.
        assert result.count("{") == result.count("}")
        assert "int x = 1" in result


class TestBinaryFunctionToDict:
    """Tests for binary_function_to_dict."""

    def _make_bf(self, function_name: str, entrypoint: str, raw_code: str) -> Any:
        class _BF:
            def __init__(self, name: str, ep: str, code: str) -> None:
                self.function_name = name
                self.entrypoint = ep
                self.raw_code = code

        return _BF(function_name, entrypoint, raw_code)

    def test_binary_function_to_dict_keys(self):
        """The dict must expose the exact keys the pipeline expects."""
        bf = self._make_bf("main", "0x401000", "int main() { return 0; }")
        result = binary_function_to_dict(bf)
        assert set(result.keys()) == {"functionName", "lowAddress", "tokenList", "raw_code"}
        assert result["functionName"] == "main"
        assert result["lowAddress"] == "0x401000"
        assert result["raw_code"] == "int main() { return 0; }"

    def test_binary_function_to_dict_token_list_split(self):
        """tokenList must be the whitespace-split raw_code."""
        bf = self._make_bf("main", "0x401000", "int  main() { return  0; }")
        result = binary_function_to_dict(bf)
        assert result["tokenList"] == ["int", "main()", "{", "return", "0;", "}"]


class TestBuildPredictionDetailsResponse:
    """Tests for build_prediction_details_response."""

    def test_build_prediction_details_response_shape(self):
        """The response must carry all five fields verbatim."""
        result = build_prediction_details_response(
            task_name="task-1",
            model_name="model-a",
            function_name="main",
            model_tokens="tok1 tok2",
            prediction_tokens="tok3 tok4",
        )
        assert result == {
            "task_name": "task-1",
            "model_name": "model-a",
            "function_name": "main",
            "model_tokens": "tok1 tok2",
            "prediction_tokens": "tok3 tok4",
        }
        assert set(result.keys()) == {"task_name", "model_name", "function_name", "model_tokens", "prediction_tokens"}
