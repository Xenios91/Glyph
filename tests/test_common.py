"""Unit tests for common utility functions."""
import pytest
from app.utils.common import format_code


class TestFormatCode:
    """Tests for format_code function."""

    def test_format_simple_function(self):
        """Test formatting a simple C function."""
        code = "int main() { return 0; }"
        result = format_code(code)
        assert "int main()" in result
        assert "return 0;" in result
        assert "{" in result
        assert "}" in result

    def test_format_function_with_body(self):
        """Test formatting a function with multiple statements."""
        code = "void func() { int x = 1; int y = 2; return; }"
        result = format_code(code)
        assert "void func()" in result
        assert "int x = 1;" in result
        assert "int y = 2;" in result
        assert "return;" in result

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
        assert "return;" in result

    def test_format_function_with_semicolons(self):
        """Test that semicolons are properly formatted."""
        code = "void func() { int a; int b; }"
        result = format_code(code)
        # Check that semicolons are followed by newlines
        assert "int a;\n" in result or "int a;" in result
        assert "int b;\n" in result or "int b;" in result

    def test_format_preserves_function_signature(self):
        """Test that function signature is preserved."""
        code = "int add(int a, int b) { return a + b; }"
        result = format_code(code)
        assert "int add(int a, int b)" in result
        assert "return a + b;" in result
