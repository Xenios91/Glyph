"""Reproduction script for newly identified bugs in Glyph codebase."""

import pytest


class TestBug_CorrelationBridgeHeaderLookup:
    """Bug: CorrelationIdBridgeMiddleware._get_correlation_id_from_scope
    uses dict() on scope headers which always has bytes keys, but tries
    to look up with both string and bytes keys. The string key lookup
    will always fail, making the string-key branch dead code.

    While not a functional bug (the bytes key works), it indicates a
    misunderstanding of ASGI header format and wastes a lookup.
    """

    def test_scope_headers_have_bytes_keys(self):
        """ASGI scope headers always use bytes keys."""
        # Simulate real ASGI scope headers
        headers_list = [
            (b"content-type", b"text/html"),
            (b"x-request-id", b"abc-123"),
        ]
        headers_dict = dict(headers_list)

        # String key lookup always fails
        assert headers_dict.get("x-request-id") is None  # type: ignore[arg-type]
        # Bytes key lookup works
        assert headers_dict.get(b"x-request-id") == b"abc-123"

    def test_bridge_code_works_with_bytes_key(self):
        """The bridge code's bytes key fallback works correctly."""
        from app.core.correlation_bridge import CorrelationIdBridgeMiddleware

        middleware = CorrelationIdBridgeMiddleware(app=lambda s, r, snd: None)

        # Simulate ASGI scope with headers
        scope = {
            "type": "http",
            "headers": [(b"x-request-id", b"test-req-123")],
        }

        result = middleware._get_correlation_id_from_scope(scope)  # pyright: ignore[reportPrivateUsage]
        assert result == "test-req-123"


class TestBug_RequestContextSetterOnClass:
    """Bug: RequestContext class has property setters that operate on
    per-instance level, but ContextVars are module-level globals.
    Setting request_id on one RequestContext instance affects ALL
    RequestContext instances because they share the same ContextVar.

    This is a design issue - the class gives the illusion of per-instance
    state but actually uses global state.
    """

    def test_request_context_shares_global_state(self):
        """RequestContext instances share the same ContextVar state."""
        from app.utils.request_context import RequestContext

        ctx1 = RequestContext()
        ctx2 = RequestContext()

        # Setting on ctx1 affects ctx2
        ctx1.request_id = "test-123"
        assert ctx2.request_id == "test-123", (
            "RequestContext instances share global ContextVar state"
        )

    def test_get_request_context_returns_new_instance(self):
        """get_request_context() returns a new instance each time."""
        from app.utils.request_context import get_request_context

        ctx1 = get_request_context()
        ctx2 = get_request_context()
        assert ctx1 is not ctx2, "Should return different instances"
        # But they share state
        ctx1.request_id = "shared"
        assert ctx2.request_id == "shared"


class TestBug_DeletePredictionDeletesByTaskName_Fixed:
    """Fixed: SQLUtil.delete_prediction() now accepts optional model_name
    parameter to narrow the delete scope and prevent accidental data loss.
    """

    def test_delete_prediction_accepts_model_name(self):
        """delete_prediction now accepts model_name parameter."""
        import inspect
        from app.database.sql_service import SQLUtil

        sig = inspect.signature(SQLUtil.delete_prediction)
        params = list(sig.parameters.keys())
        assert "model_name" in params, (
            "delete_prediction should accept model_name parameter"
        )

    def test_delete_prediction_filters_by_model_name(self):
        """delete_prediction filters by model_name when provided."""
        import inspect
        from app.database.sql_service import SQLUtil

        source = inspect.getsource(SQLUtil.delete_prediction)
        assert "Prediction.model_name" in source, (
            "delete_prediction should filter by model_name when provided"
        )


class TestBug_FormatCodeUnescapedClosingBrace:
    """Bug: format_code() can produce malformed output when the function
    body has unmatched braces or the closing brace logic is incorrect.
    The final check 'if not final_output[-1].strip() == "}"' can cause
    a double closing brace if the body already ends with one.
    """

    def test_format_code_double_brace(self):
        """format_code may add extra closing brace."""
        from app.utils.common import format_code

        # Code where the body naturally ends with }
        code = """
        void func() {
            if (x) {
                y++;
            }
        }
        """
        result = format_code(code)
        # Count closing braces
        close_count = result.count("}")
        # Should have exactly 2 closing braces (one for if, one for func)
        assert close_count == 2, f"Expected 2 closing braces, got {close_count}: {result!r}"


class TestBug_StaticPoolWithMultipleDatabases:
    """Bug: Using StaticPool with multiple SQLite databases can cause
    connection sharing issues. StaticPool reuses a single connection,
    but when multiple engines use StaticPool, they may interfere with
    each other's transactions.

    This is a configuration issue rather than a code bug, but it can
    cause subtle data corruption under concurrent access.
    """

    def test_static_pool_configuration(self):
        """Verify that StaticPool is used for all engines."""
        import inspect
        from app.database.session_handler import _create_engine  # pyright: ignore[reportPrivateUsage]

        source = inspect.getsource(_create_engine)
        assert "StaticPool" in source, "Engine uses StaticPool"
        # This is a design concern - StaticPool with multiple databases
        # can cause issues under concurrent access


class TestBug_Argon2DummyHashTiming:
    """The dummy hash used for timing attack prevention must use the
    same parameters as real hashes to ensure constant-time verification.
    If parameters differ, the timing will leak information.
    """

    def test_dummy_hash_matches_real_parameters(self):
        """Dummy hash parameters match PasswordHasher settings."""
        from app.database.repository import UserRepository

        # The PasswordHasher uses: time_cost=2, memory_cost=65536, parallelism=4
        # The dummy hash should have matching parameters
        dummy = UserRepository._DUMMY_HASH  # pyright: ignore[reportPrivateUsage]
        assert "m=65536" in dummy, "Memory cost should match"
        assert "t=2" in dummy, "Time cost should match"
        assert "p=4" in dummy, "Parallelism should match"


class TestBug_RateLimiterWindowFormat:
    """Verify rate limit strings are in correct slowapi format."""

    def test_rate_limit_format(self):
        """Rate limit strings are in correct slowapi format."""
        from app.core.rate_limiter import LOGIN_LIMIT, REGISTER_LIMIT

        # slowapi accepts: "10/minute", "5/5 minutes", "100/hour"
        assert "/minute" in LOGIN_LIMIT
        # REGISTER_LIMIT format depends on configuration
        assert "/" in REGISTER_LIMIT


class TestBug_JWTKeySizeWarning:
    """The JWT secret key 'change-me-in-production' may trigger
    joserfc's SecurityWarning about key size. This test documents
    the current behavior without asserting a specific outcome,
    as the warning behavior may vary by joserfc version.
    """

    def test_jwt_handler_works_with_default_key(self):
        """JWT handler works with default secret key."""
        from app.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret_key="change-me-in-production")
        token = handler.create_access_token("test")
        claims = handler.verify_access_token(token)
        assert claims["sub"] == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])