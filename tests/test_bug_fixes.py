"""Tests to verify bug fixes in Glyph codebase."""


class TestBug1_Fixed_FormatCodeBalancedBraces:
    """Verify Bug 1 fix: format_code() now produces balanced braces."""

    def test_simple_nested_function_balanced(self):
        """Simple function with nested if-block should have balanced braces."""
        from app.utils.common import format_code

        code = """void func() {
    if (x) {
        y++;
    }
}"""
        result = format_code(code)
        assert result.count("{") == result.count("}"), (
            f"Braces should be balanced: {result!r}"
        )

    def test_deeply_nested_function_balanced(self):
        """Deeply nested function should have balanced braces."""
        from app.utils.common import format_code

        code = """int main() {
    for (int i = 0; i < 10; i++) {
        if (i > 5) {
            break;
        }
    }
    return 0;
}"""
        result = format_code(code)
        assert result.count("{") == result.count("}"), (
            f"Braces should be balanced: {result!r}"
        )

    def test_single_line_function_balanced(self):
        """Single-line function body should have balanced braces."""
        from app.utils.common import format_code

        code = """void simple() {
    x = 1;
}"""
        result = format_code(code)
        assert result.count("{") == result.count("}"), (
            f"Braces should be balanced: {result!r}"
        )

    def test_no_double_closing_brace(self):
        """Should not produce double closing braces."""
        from app.utils.common import format_code

        code = """void func() {
    if (x) {
        y++;
    }
}"""
        result = format_code(code)
        # Should have exactly 2 closing braces, not 3
        assert result.count("}") == 2, (
            f"Should have exactly 2 closing braces, got {result.count('}')}: {result!r}"
        )


class TestBug2_Fixed_DeletePredictionWithModelName:
    """Verify Bug 2 fix: delete_prediction now accepts model_name parameter."""

    def test_delete_prediction_accepts_model_name(self):
        """SQLUtil.delete_prediction should accept model_name parameter."""
        import inspect
        from app.database.sql_service import SQLUtil

        sig = inspect.signature(SQLUtil.delete_prediction)
        params = list(sig.parameters.keys())
        assert "model_name" in params, (
            "delete_prediction should accept model_name parameter"
        )

    def test_delete_prediction_model_name_optional(self):
        """model_name should be optional (default None) for backwards compatibility."""
        import inspect
        from app.database.sql_service import SQLUtil

        sig = inspect.signature(SQLUtil.delete_prediction)
        model_name_param = sig.parameters["model_name"]
        assert model_name_param.default is None, (
            "model_name should default to None for backwards compatibility"
        )

    def test_persistence_layer_passes_model_name(self):
        """PredictionPersistanceUtil.delete_prediction should pass model_name."""
        import inspect
        from app.utils.persistence_util import PredictionPersistanceUtil

        sig = inspect.signature(PredictionPersistanceUtil.delete_prediction)
        params = list(sig.parameters.keys())
        assert "model_name" in params, (
            "PredictionPersistanceUtil.delete_prediction should accept model_name"
        )

    def test_sql_uses_model_name_filter(self):
        """SQLUtil.delete_prediction should filter by model_name when provided."""
        import inspect
        from app.database.sql_service import SQLUtil

        source = inspect.getsource(SQLUtil.delete_prediction)
        assert "Prediction.model_name" in source, (
            "delete_prediction should filter by model_name when provided"
        )


class TestBug3_Fixed_CorrelationBridgeNoDeadCode:
    """Verify Bug 3 fix: CorrelationIdBridgeMiddleware no longer has dead code."""

    def test_no_string_key_lookup(self):
        """Should not try string key lookup (which always fails)."""
        import inspect
        from app.core.correlation_bridge import CorrelationIdBridgeMiddleware

        source = inspect.getsource(
            CorrelationIdBridgeMiddleware._get_correlation_id_from_scope  # pyright: ignore[reportPrivateUsage]
        )
        # Should not have a loop with both string and bytes keys
        assert '("x-request-id", b"x-request-id")' not in source, (
            "Should not have redundant string key lookup"
        )

    def test_uses_bytes_key_directly(self):
        """Should use bytes key directly."""
        import inspect
        from app.core.correlation_bridge import CorrelationIdBridgeMiddleware

        source = inspect.getsource(
            CorrelationIdBridgeMiddleware._get_correlation_id_from_scope  # pyright: ignore[reportPrivateUsage]
        )
        assert b"x-request-id".decode() in source or '"x-request-id"' in source, (
            "Should look up x-request-id header"
        )

    def test_bridge_still_works(self):
        """Bridge should still extract correlation ID correctly."""
        from app.core.correlation_bridge import CorrelationIdBridgeMiddleware

        middleware = CorrelationIdBridgeMiddleware(app=lambda s, r, snd: None)
        scope = {
            "type": "http",
            "headers": [(b"x-request-id", b"test-req-123")],
        }
        result = middleware._get_correlation_id_from_scope(scope)  # pyright: ignore[reportPrivateUsage]
        assert result == "test-req-123"


class TestBug4_Fixed_NoThreadingTimer:
    """Verify Bug 4 fix: No longer uses threading.Timer in async context."""

    def test_no_threading_import_in_finally(self):
        """Should not import threading in the finally block."""
        import inspect
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis  # pyright: ignore[reportPrivateUsage]

        source = inspect.getsource(_run_pipeline_analysis)
        assert "import threading" not in source, (
            "Should not import threading"
        )
        assert "threading.Timer" not in source, (
            "Should not use threading.Timer"
        )

    def test_uses_asyncio_or_call_later(self):
        """Should use asyncio-based scheduling."""
        import inspect
        from app.api.v1.endpoints.binaries import _run_pipeline_analysis  # pyright: ignore[reportPrivateUsage]

        source = inspect.getsource(_run_pipeline_analysis)
        # Should use asyncio or call_later instead of threading.Timer
        assert "asyncio" in source or "call_later" in source, (
            "Should use asyncio-based scheduling"
        )
