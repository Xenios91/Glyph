"""Verification tests for bug fixes in Glyph codebase."""

import pytest


class TestBug1_Fixed_AcceptHeaderLogic:
    """Verify Bug 1 fix: Accept header logic now consistent across all endpoints."""

    def test_getPrediction_uses_correct_logic(self):
        """getPrediction now uses 'ACCEPT_TYPE in accept' pattern."""
        import inspect
        from app.api.v1.endpoints.predictions import get_prediction

        source = inspect.getsource(get_prediction)
        assert "ACCEPT_TYPE in accept" in source, (
            "getPrediction should use 'ACCEPT_TYPE in accept' pattern"
        )
        assert "ACCEPT_TYPE not in accept" not in source, (
            "getPrediction should NOT use inverted 'not in' pattern"
        )

    def test_getFunction_uses_correct_logic(self):
        """getFunction now uses 'ACCEPT_TYPE in accept' pattern."""
        import inspect
        from app.api.v1.endpoints.models import get_function

        source = inspect.getsource(get_function)
        assert "ACCEPT_TYPE in accept" in source, (
            "getFunction should use 'ACCEPT_TYPE in accept' pattern"
        )
        assert "ACCEPT_TYPE not in accept" not in source, (
            "getFunction should NOT use inverted 'not in' pattern"
        )

    def test_getFunctions_uses_correct_logic(self):
        """getFunctions now uses 'ACCEPT_TYPE in accept' pattern."""
        import inspect
        from app.api.v1.endpoints.models import get_functions

        source = inspect.getsource(get_functions)
        assert "ACCEPT_TYPE in accept" in source, (
            "getFunctions should use 'ACCEPT_TYPE in accept' pattern"
        )
        assert "ACCEPT_TYPE not in accept" not in source, (
            "getFunctions should NOT use inverted 'not in' pattern"
        )


class TestBug2_Fixed_GetPredictionsReturnsNone:
    """Verify Bug 2 fix: get_predictions returns None instead of raising ValueError."""

    def test_get_predictions_returns_none_type(self):
        """get_predictions now returns Prediction | None."""
        import inspect
        from app.utils.persistence_util import PredictionPersistanceUtil

        source = inspect.getsource(PredictionPersistanceUtil.get_predictions)
        assert "Prediction | None" in source or "-> Prediction | None" in source, (
            "get_predictions should return Prediction | None"
        )
        assert "raise ValueError" not in source or "non-empty" in source, (
            "get_predictions should NOT raise ValueError for missing predictions"
        )

    def test_contract_matches_sql_layer(self):
        """Both layers now return None for missing predictions."""
        import inspect
        from app.database.sql_service import SQLUtil
        from app.utils.persistence_util import PredictionPersistanceUtil

        sql_source = inspect.getsource(SQLUtil.get_predictions)
        persist_source = inspect.getsource(
            PredictionPersistanceUtil.get_predictions
        )

        sql_returns_none = "return None" in sql_source
        persist_returns_none = "return await SQLUtil.get_predictions" in persist_source

        assert sql_returns_none and persist_returns_none, (
            "Both SQL and persistence layers should return None for missing predictions"
        )


class TestBug3_Fixed_GetModelsListReturnsList:
    """Verify Bug 3 fix: get_models_list returns list[str] instead of set[str]."""

    def test_get_models_list_returns_list(self):
        """get_models_list now returns list[str]."""
        import inspect
        from app.utils.persistence_util import MLPersistanceUtil

        source = inspect.getsource(MLPersistanceUtil.get_models_list)
        assert "list[str]" in source, (
            "get_models_list should return list[str]"
        )
        assert "list(models)" in source or "list(" in source, (
            "get_models_list should convert set to list"
        )


class TestBug4_Fixed_PredictionRequestSnakeCase:
    """Verify Bug 4 fix: PredictionRequest accepts both taskName and task_name."""

    def test_prediction_request_accepts_snake_case(self):
        """PredictionRequest now accepts 'task_name' (snake_case)."""
        from app.services.request_handler import PredictionRequest

        data = {
            "task_name": "test_task",
            "functionsMap": {"functions": []},
        }

        # Should NOT raise KeyError anymore
        req = PredictionRequest(req_uuid="test-uuid", model_name="test_model", data=data)
        assert req.task_name == "test_task"

    def test_prediction_request_still_accepts_camel_case(self):
        """PredictionRequest still accepts 'taskName' (camelCase)."""
        from app.services.request_handler import PredictionRequest

        data = {
            "taskName": "test_task",
            "functionsMap": {"functions": []},
        }

        req = PredictionRequest(req_uuid="test-uuid", model_name="test_model", data=data)
        assert req.task_name == "test_task"

    def test_prediction_request_raises_when_missing(self):
        """PredictionRequest raises ValueError when neither key is present."""
        from app.services.request_handler import PredictionRequest

        data = {
            "functionsMap": {"functions": []},
        }

        with pytest.raises(ValueError, match="taskName.*task_name"):
            PredictionRequest(req_uuid="test-uuid", model_name="test_model", data=data)


class TestBug5_Fixed_JWTHandlerUsesSettings:
    """Verify Bug 5 fix: JWTHandler uses settings for token expiry."""

    def test_jwt_handler_accepts_expiry_params(self):
        """JWTHandler now accepts expiry parameters in constructor."""
        import inspect
        from app.auth.jwt_handler import JWTHandler

        sig = inspect.signature(JWTHandler.__init__)
        params = list(sig.parameters.keys())
        assert "access_token_expire_minutes" in params, (
            "JWTHandler should accept access_token_expire_minutes"
        )
        assert "refresh_token_expire_days" in params, (
            "JWTHandler should accept refresh_token_expire_days"
        )

    def test_jwt_handler_uses_expiry_params(self):
        """JWTHandler uses expiry params instead of hardcoded values."""
        import inspect
        from app.auth.jwt_handler import JWTHandler

        source = inspect.getsource(JWTHandler.create_access_token)
        assert "self.access_token_expire_minutes" in source, (
            "create_access_token should use self.access_token_expire_minutes"
        )
        assert "timedelta(minutes=15)" not in source, (
            "create_access_token should NOT hardcode 15 minutes"
        )

        refresh_source = inspect.getsource(JWTHandler.create_refresh_token)
        assert "self.refresh_token_expire_days" in refresh_source, (
            "create_refresh_token should use self.refresh_token_expire_days"
        )
        assert "timedelta(days=7)" not in refresh_source, (
            "create_refresh_token should NOT hardcode 7 days"
        )

    def test_get_jwt_handler_passes_settings(self):
        """get_jwt_handler passes settings values to JWTHandler."""
        import inspect
        from app.auth.dependencies import get_jwt_handler

        source = inspect.getsource(get_jwt_handler)
        assert "access_token_expire_minutes" in source, (
            "get_jwt_handler should pass access_token_expire_minutes"
        )
        assert "refresh_token_expire_days" in source, (
            "get_jwt_handler should pass refresh_token_expire_days"
        )

    def test_custom_expiry_values_work(self):
        """JWT tokens use custom expiry values from settings."""
        from app.auth.jwt_handler import JWTHandler

        handler = JWTHandler(
            secret_key="test-secret",
            access_token_expire_minutes=30,
            refresh_token_expire_days=14,
        )

        access_token = handler.create_access_token("user123")
        claims = handler.verify_access_token(access_token)
        iat = claims["iat"]
        exp = claims["exp"]
        # joserfc stores iat/exp as Unix timestamps (integers)
        delta_minutes = (exp - iat) / 60
        assert abs(delta_minutes - 30) < 1, (
            f"Access token should expire in ~30 minutes, got {delta_minutes}"
        )

        refresh_token = handler.create_refresh_token("user123")
        rclaims = handler.verify_refresh_token(refresh_token)
        riat = rclaims["iat"]
        rexp = rclaims["exp"]
        delta_days = (rexp - riat) / 86400
        assert abs(delta_days - 14) < 0.01, (
            f"Refresh token should expire in ~14 days, got {delta_days}"
        )


class TestArgon2VerifyCorrect:
    """Verify argon2 verify signature is correct."""

    def test_argon2_verify_signature(self):
        """argon2 verify takes (hash, password) order."""
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        h = ph.hash("test_password")
        result = ph.verify(h, "test_password")
        assert result is True


class TestInvalidHashErrorHierarchy:
    """Verify InvalidHashError exception hierarchy."""

    def test_invalid_hash_error_hierarchy(self):
        """InvalidHashError is not a subclass of VerificationError."""
        from argon2.exceptions import (
            InvalidHashError,
            VerificationError,
            VerifyMismatchError,
        )

        assert not issubclass(InvalidHashError, VerificationError)
        assert issubclass(VerifyMismatchError, VerificationError)
