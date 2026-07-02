"""Comprehensive tests for authentication dependencies."""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from app.auth.dependencies import (
    get_current_active_user,
    get_current_user,
    get_db,
    get_jwt_handler,
    get_optional_user,
)
from app.auth.jwt_handler import JWTHandler
from app.database.models import User
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def jwt_handler() -> JWTHandler:
    """Create a JWT handler for testing."""
    return JWTHandler(
        secret_key="test_secret_key",
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def valid_access_token(jwt_handler: JWTHandler) -> str:
    """Create a valid access token for user 1."""
    return jwt_handler.create_access_token("1")


@pytest.fixture
def mock_async_session() -> mock.MagicMock:
    """Create a mock async database session."""
    session = mock.MagicMock(spec=AsyncSession)
    session.commit = mock.AsyncMock()
    session.rollback = mock.AsyncMock()
    return session


@pytest.fixture
def mock_request() -> mock.MagicMock:
    """Create a mock FastAPI Request object."""
    request = mock.MagicMock(spec=Request)
    request.headers = {}
    request.cookies = {}
    request.client = mock.MagicMock()
    request.client.host = "127.0.0.1"
    request.url.path = "/api/test"
    return request


# ---------------------------------------------------------------------------
# Tests for get_jwt_handler
# ---------------------------------------------------------------------------


class TestGetJWTHandler:
    """Tests for get_jwt_handler dependency."""

    def test_get_jwt_handler_returns_instance(self) -> None:
        """Test that get_jwt_handler returns a JWTHandler instance."""
        with mock.patch("app.auth.dependencies.get_settings") as mock_get_settings:
            mock_settings = mock.MagicMock()
            mock_settings.jwt_secret_key = "test_secret"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.access_token_expire_minutes = 30
            mock_settings.refresh_token_expire_days = 14
            mock_get_settings.return_value = mock_settings

            handler = get_jwt_handler()

            assert isinstance(handler, JWTHandler)
            assert handler.algorithm == "HS256"
            assert handler.access_token_expire_minutes == 30
            assert handler.refresh_token_expire_days == 14

    def test_get_jwt_handler_uses_settings(self) -> None:
        """Test that get_jwt_handler uses settings values correctly."""
        with mock.patch("app.auth.dependencies.get_settings") as mock_get_settings:
            mock_settings = mock.MagicMock()
            mock_settings.jwt_secret_key = "my_secret_key"
            mock_settings.jwt_algorithm = "HS384"
            mock_settings.access_token_expire_minutes = 60
            mock_settings.refresh_token_expire_days = 30
            mock_get_settings.return_value = mock_settings

            handler = get_jwt_handler()

            assert handler.algorithm == "HS384"
            assert handler.access_token_expire_minutes == 60
            assert handler.refresh_token_expire_days == 30


# ---------------------------------------------------------------------------
# Tests for get_db
# ---------------------------------------------------------------------------


class TestGetDb:
    """Tests for get_db async generator dependency."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session_and_commits(self) -> None:
        """Test that get_db yields a session and commits on success."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            session = await gen.asend(None)

            assert session is mock_session
            mock_async_session.assert_called_once_with("auth")

            # Trigger rollback path via HTTPException
            try:
                await gen.athrow(HTTPException(status_code=404))
            except HTTPException:
                pass

            # Should rollback on HTTPException
            mock_session.rollback.assert_awaited_once()
            mock_context.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_commits_on_success(self) -> None:
        """Test that get_db commits when no exception occurs."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            session = await gen.asend(None)

            assert session is mock_session

            # Normal completion - send None to trigger commit
            try:
                await gen.asend(None)
            except StopAsyncIteration:
                pass

            mock_session.commit.assert_awaited_once()
            mock_context.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_http_exception(self) -> None:
        """Test that get_db rolls back on HTTPException."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            await gen.asend(None)

            try:
                await gen.athrow(HTTPException(status_code=401))
            except HTTPException:
                pass

            mock_session.rollback.assert_awaited_once()
            mock_session.commit.assert_not_awaited()
            mock_context.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_request_validation_error(self) -> None:
        """Test that get_db rolls back on RequestValidationError."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            await gen.asend(None)

            try:
                await gen.athrow(RequestValidationError(errors=[]))
            except RequestValidationError:
                pass

            mock_session.rollback.assert_awaited_once()
            mock_session.commit.assert_not_awaited()
            mock_context.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_generic_exception(self) -> None:
        """Test that get_db rolls back on generic exceptions."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            await gen.asend(None)

            try:
                await gen.athrow(sa_exc.SQLAlchemyError("db error"))
            except sa_exc.SQLAlchemyError:
                pass

            mock_session.rollback.assert_awaited_once()
            mock_session.commit.assert_not_awaited()
            mock_context.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_always_closes_session(self) -> None:
        """Test that session context manager exit is always called."""
        mock_session = mock.AsyncMock()
        mock_context = mock.AsyncMock()
        mock_context.__aenter__ = mock.AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = mock.AsyncMock(return_value=None)

        with mock.patch("app.auth.dependencies.async_session") as mock_async_session:
            mock_async_session.return_value = mock_context

            gen = get_db()
            await gen.asend(None)

            # Throw exception to trigger finally
            try:
                await gen.athrow(Exception("unexpected"))
            except Exception:
                pass

            mock_context.__aexit__.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests for get_current_user
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_auth_disabled_returns_anonymous(self, mock_request: mock.MagicMock) -> None:
        """Test that auth disabled returns anonymous user."""
        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = False

            user = await get_current_user(
                request=mock_request,
                db=mock.MagicMock(),
                jwt_handler=mock.MagicMock(),
            )

            assert user.username == "anonymous"
            assert user.id == 0
            assert user.is_active is True

    @pytest.mark.asyncio
    async def test_get_current_user_valid_jwt_token(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test authentication with valid JWT token."""
        mock_user = User(id=1, username="testuser", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            user = await get_current_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            assert user.id == 1
            assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_token_from_cookie(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test authentication with token from cookie."""
        mock_user = User(id=1, username="cookieuser", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {}
        mock_request.cookies = {"access_token_cookie": valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            user = await get_current_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            assert user.id == 1
            assert user.username == "cookieuser"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_token_raises_401(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that missing token raises 401."""
        mock_request.headers = {}
        mock_request.cookies = {}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    db=mock.MagicMock(),
                    jwt_handler=jwt_handler,
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Not authenticated" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_jwt_falls_back_to_api_key(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that invalid JWT falls back to API key lookup."""
        mock_user = User(id=2, username="apikeyuser", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        mock_api_key_record = mock.MagicMock()
        mock_api_key_record.user_id = 2
        mock_api_key_record.key_prefix = "test_key_prefix"

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            with mock.patch("app.auth.dependencies.APIKeyRepository") as mock_repo_cls:
                mock_repo = mock.MagicMock()
                mock_repo.verify_and_get = mock.AsyncMock(return_value=mock_api_key_record)
                mock_repo_cls.return_value = mock_repo

                with mock.patch("app.auth.dependencies.log_api_key_usage") as mock_log_usage:
                    user = await get_current_user(
                        request=mock_request,
                        db=mock_async_session,
                        jwt_handler=jwt_handler,
                    )

                    assert user.id == 2
                    assert user.username == "apikeyuser"
                    mock_log_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_user_api_key_user_inactive_raises_401(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that inactive user via API key raises 401."""
        mock_inactive_user = User(id=3, username="inactive_user", is_active=False)
        mock_async_session.get = mock.AsyncMock(return_value=mock_inactive_user)
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        mock_api_key_record = mock.MagicMock()
        mock_api_key_record.user_id = 3
        mock_api_key_record.key_prefix = "test_key_prefix"

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            with mock.patch("app.auth.dependencies.APIKeyRepository") as mock_repo_cls:
                mock_repo = mock.MagicMock()
                mock_repo.verify_and_get = mock.AsyncMock(return_value=mock_api_key_record)
                mock_repo_cls.return_value = mock_repo

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(
                        request=mock_request,
                        db=mock_async_session,
                        jwt_handler=jwt_handler,
                    )

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "User not found or inactive" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_api_key_not_found_raises_401(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that invalid API key raises 401."""
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            with mock.patch("app.auth.dependencies.APIKeyRepository") as mock_repo_cls:
                mock_repo = mock.MagicMock()
                mock_repo.verify_and_get = mock.AsyncMock(return_value=None)
                mock_repo_cls.return_value = mock_repo

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(
                        request=mock_request,
                        db=mock.MagicMock(),
                        jwt_handler=jwt_handler,
                    )

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Invalid authentication credentials" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_empty_token_subject_raises_401(
        self,
        mock_request: mock.MagicMock,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that JWT with empty subject raises 401."""
        mock_request.headers = {"Authorization": "Bearer some_token"}

        mock_jwt_handler = mock.MagicMock()
        mock_jwt_handler.verify_access_token.return_value = {"sub": None}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    db=mock_async_session,
                    jwt_handler=mock_jwt_handler,
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid token payload" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_not_found_raises_401(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that user not found raises 401."""
        mock_async_session.get = mock.AsyncMock(return_value=None)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    db=mock_async_session,
                    jwt_handler=jwt_handler,
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found or inactive" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_inactive_user_raises_401(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that inactive user raises 401."""
        mock_inactive_user = User(id=1, username="inactive", is_active=False)
        mock_async_session.get = mock.AsyncMock(return_value=mock_inactive_user)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    db=mock_async_session,
                    jwt_handler=jwt_handler,
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found or inactive" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_sets_request_context(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that request context is set on successful auth."""
        mock_user = User(id=1, username="testuser", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            with mock.patch("app.auth.dependencies.set_request_context") as mock_set_context:
                user = await get_current_user(
                    request=mock_request,
                    db=mock_async_session,
                    jwt_handler=jwt_handler,
                )

                mock_set_context.assert_called_once_with(user_id=1, username="testuser", clear_unset=False)
                assert user.id == 1

    @pytest.mark.asyncio
    async def test_get_current_user_bearer_prefix_case_insensitive(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that 'bearer' prefix is case-insensitive."""
        mock_user = User(id=1, username="testuser", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            user = await get_current_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            assert user.id == 1

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_authorization_format(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that invalid Authorization header format raises 401."""
        mock_request.headers = {"Authorization": "InvalidFormat"}
        mock_request.cookies = {}

        with mock.patch("app.auth.dependencies.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=mock_request,
                    db=mock.MagicMock(),
                    jwt_handler=jwt_handler,
                )

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Tests for get_current_active_user
# ---------------------------------------------------------------------------


class TestGetCurrentActiveUser:
    """Tests for get_current_active_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_active_user(self) -> None:
        """Test that active user passes through."""
        active_user = User(id=1, username="active_user", is_active=True)

        user = await get_current_active_user(current_user=active_user)

        assert user.id == 1
        assert user.username == "active_user"

    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive_user_raises_403(self) -> None:
        """Test that inactive user raises 403."""
        inactive_user = User(id=2, username="inactive_user", is_active=False)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user=inactive_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "User account is disabled" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# Tests for get_optional_user
# ---------------------------------------------------------------------------


class TestGetOptionalUser:
    """Tests for get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_get_optional_user_no_token_returns_none(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that missing token returns None."""
        mock_request.headers = {}
        mock_request.cookies = {}

        user = await get_optional_user(
            request=mock_request,
            db=mock.MagicMock(),
            jwt_handler=jwt_handler,
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_valid_jwt_returns_user(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that valid JWT returns user."""
        mock_user = User(id=1, username="optional_user", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        user = await get_optional_user(
            request=mock_request,
            db=mock_async_session,
            jwt_handler=jwt_handler,
        )

        assert user is not None
        assert user.id == 1
        assert user.username == "optional_user"

    @pytest.mark.asyncio
    async def test_get_optional_user_token_from_cookie(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that token from cookie returns user."""
        mock_user = User(id=1, username="cookie_user", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {}
        mock_request.cookies = {"access_token_cookie": valid_access_token}

        user = await get_optional_user(
            request=mock_request,
            db=mock_async_session,
            jwt_handler=jwt_handler,
        )

        assert user is not None
        assert user.username == "cookie_user"

    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_jwt_returns_none(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that invalid JWT returns None."""
        mock_request.headers = {"Authorization": "Bearer invalid_token"}
        mock_request.cookies = {}

        user = await get_optional_user(
            request=mock_request,
            db=mock.MagicMock(),
            jwt_handler=jwt_handler,
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_valid_api_key_returns_user(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that valid API key returns user."""
        mock_user = User(id=5, username="api_optional", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer invalid_jwt"}
        mock_request.cookies = {}

        mock_api_key_record = mock.MagicMock()
        mock_api_key_record.user_id = 5

        with mock.patch("app.auth.dependencies.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.verify_and_get = mock.AsyncMock(return_value=mock_api_key_record)
            mock_repo_cls.return_value = mock_repo

            user = await get_optional_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            assert user is not None
            assert user.id == 5

    @pytest.mark.asyncio
    async def test_get_optional_user_api_key_inactive_returns_none(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that API key for inactive user returns None."""
        mock_inactive_user = User(id=6, username="inactive", is_active=False)
        mock_async_session.get = mock.AsyncMock(return_value=mock_inactive_user)
        mock_request.headers = {"Authorization": "Bearer invalid_jwt"}
        mock_request.cookies = {}

        mock_api_key_record = mock.MagicMock()
        mock_api_key_record.user_id = 6

        with mock.patch("app.auth.dependencies.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.verify_and_get = mock.AsyncMock(return_value=mock_api_key_record)
            mock_repo_cls.return_value = mock_repo

            user = await get_optional_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_user_not_found_returns_none(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that user not found returns None."""
        mock_async_session.get = mock.AsyncMock(return_value=None)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        user = await get_optional_user(
            request=mock_request,
            db=mock_async_session,
            jwt_handler=jwt_handler,
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_empty_subject_returns_none(
        self,
        mock_request: mock.MagicMock,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that JWT with empty subject returns None."""
        mock_request.headers = {"Authorization": "Bearer some_token"}

        mock_jwt_handler = mock.MagicMock()
        mock_jwt_handler.verify_access_token.return_value = {"sub": None}

        user = await get_optional_user(
            request=mock_request,
            db=mock_async_session,
            jwt_handler=mock_jwt_handler,
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_sets_request_context(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
        valid_access_token: str,
        mock_async_session: mock.MagicMock,
    ) -> None:
        """Test that request context is set on successful optional auth."""
        mock_user = User(id=1, username="optional_user", is_active=True)
        mock_async_session.get = mock.AsyncMock(return_value=mock_user)
        mock_request.headers = {"Authorization": "Bearer " + valid_access_token}

        with mock.patch("app.auth.dependencies.set_request_context") as mock_set_context:
            user = await get_optional_user(
                request=mock_request,
                db=mock_async_session,
                jwt_handler=jwt_handler,
            )

            mock_set_context.assert_called_once_with(user_id=1, username="optional_user", clear_unset=False)
            assert user is not None

    @pytest.mark.asyncio
    async def test_get_optional_user_invalid_auth_format_returns_none(
        self,
        mock_request: mock.MagicMock,
        jwt_handler: JWTHandler,
    ) -> None:
        """Test that invalid Authorization format returns None."""
        mock_request.headers = {"Authorization": "InvalidFormat"}
        mock_request.cookies = {}

        user = await get_optional_user(
            request=mock_request,
            db=mock.MagicMock(),
            jwt_handler=jwt_handler,
        )

        assert user is None
