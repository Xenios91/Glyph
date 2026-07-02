"""Unit tests for auth endpoints with mocking to ensure full coverage."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest import mock

import pytest
from app.auth.endpoints import (
    change_password,
    create_api_key,
    delete_api_key,
    get_current_user_info,
    login,
    logout,
    refresh_token,
    register,
    update_profile,
)
from app.auth.jwt_handler import JWTHandler
from app.auth.schemas import (
    APIKeyCreate,
    ChangePassword,
    RefreshTokenRequest,
    UserRegister,
    UserUpdate,
)
from app.database.models import User


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
def mock_request() -> Any:
    """Create a real FastAPI Request object for SlowAPI compatibility."""
    from starlette.datastructures import Address
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/auth/test",
        "headers": [],
        "client": Address(host="127.0.0.1", port=8000),
    }
    request = Request(scope)
    return request


@pytest.fixture
def mock_db() -> mock.MagicMock:
    """Create a mock async database session."""
    db = mock.MagicMock()
    return db


@pytest.fixture
def mock_user() -> User:
    """Create a mock active user."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_pw",
        is_active=True,
        full_name="Test User",
        permissions="[]",
        created_at=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Tests for register endpoint
# ---------------------------------------------------------------------------


class TestRegisterEndpoint:
    """Unit tests for register endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_register_username_exists(self, mock_request: mock.MagicMock, mock_db: mock.MagicMock) -> None:
        """Test register raises 400 when username already exists."""
        from fastapi import HTTPException

        user_data = UserRegister(
            username="existing",
            email="new@example.com",
            password="password123",
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_username = mock.AsyncMock(return_value=mock.MagicMock())
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await register(request=mock_request, user_data=user_data, db=mock_db)

            assert exc_info.value.status_code == 400
            assert "Username already registered" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_register_email_exists(self, mock_request: mock.MagicMock, mock_db: mock.MagicMock) -> None:
        """Test register raises 400 when email already exists."""
        from fastapi import HTTPException

        user_data = UserRegister(
            username="newuser",
            email="existing@example.com",
            password="password123",
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_username = mock.AsyncMock(return_value=None)
            mock_repo.get_by_email = mock.AsyncMock(return_value=mock.MagicMock())
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await register(request=mock_request, user_data=user_data, db=mock_db)

            assert exc_info.value.status_code == 400
            assert "Email already registered" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_register_success(self, mock_request: mock.MagicMock, mock_db: mock.MagicMock) -> None:
        """Test successful registration creates user and returns response."""
        user_data = UserRegister(
            username="newuser",
            email="new@example.com",
            password="password123",
            full_name="New User",
        )

        created_user = User(
            id=2,
            username="newuser",
            email="new@example.com",
            hashed_password="hashed",
            is_active=True,
            full_name="New User",
            permissions='["read"]',
            created_at=datetime.now(),
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_username = mock.AsyncMock(return_value=None)
            mock_repo.get_by_email = mock.AsyncMock(return_value=None)
            mock_repo.create_user = mock.AsyncMock(return_value=created_user)
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_user_registration") as mock_log:
                result = await register(request=mock_request, user_data=user_data, db=mock_db)

                assert result.username == "newuser"
                assert result.email == "new@example.com"
                mock_log.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for login endpoint
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """Unit tests for login endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_login_user_blocked(self, mock_request: mock.MagicMock, mock_db: mock.MagicMock) -> None:
        """Test login returns 429 when user is blocked."""
        from fastapi import HTTPException

        form_data = mock.MagicMock()
        form_data.username = "blocked_user"
        form_data.password = "password"

        with mock.patch("app.auth.endpoints.is_blocked", return_value=True):
            with mock.patch("app.auth.endpoints.log_suspicious_activity"):
                with pytest.raises(HTTPException) as exc_info:
                    await login(
                        request=mock_request,
                        form_data=form_data,
                        db=mock_db,
                        jwt_handler=mock.MagicMock(),
                    )

                assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler
    ) -> None:
        """Test login returns 401 for invalid credentials."""
        from fastapi import HTTPException

        form_data = mock.MagicMock()
        form_data.username = "testuser"
        form_data.password = "wrong_password"

        with mock.patch("app.auth.endpoints.is_blocked", return_value=False):
            with mock.patch("app.auth.endpoints.log_login_attempt"):
                with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
                    mock_repo = mock.MagicMock()
                    mock_repo.verify_credentials = mock.AsyncMock(return_value=None)
                    mock_repo_cls.return_value = mock_repo

                    with mock.patch("app.auth.endpoints.log_login_failure"):
                        with pytest.raises(HTTPException) as exc_info:
                            await login(
                                request=mock_request,
                                form_data=form_data,
                                db=mock_db,
                                jwt_handler=jwt_handler,
                            )

                        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler
    ) -> None:
        """Test login returns 403 for inactive user."""
        from fastapi import HTTPException

        form_data = mock.MagicMock()
        form_data.username = "inactive_user"
        form_data.password = "password"

        inactive_user = User(id=1, username="inactive_user", email="i@e.com", hashed_password="h", is_active=False)

        with mock.patch("app.auth.endpoints.is_blocked", return_value=False):
            with mock.patch("app.auth.endpoints.log_login_attempt"):
                with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
                    mock_repo = mock.MagicMock()
                    mock_repo.verify_credentials = mock.AsyncMock(return_value=inactive_user)
                    mock_repo_cls.return_value = mock_repo

                    with mock.patch("app.auth.endpoints.log_login_failure"):
                        with pytest.raises(HTTPException) as exc_info:
                            await login(
                                request=mock_request,
                                form_data=form_data,
                                db=mock_db,
                                jwt_handler=jwt_handler,
                            )

                        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_login_success(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler, mock_user: User
    ) -> None:
        """Test successful login returns tokens with cookies."""
        from fastapi import Response

        form_data = mock.MagicMock()
        form_data.username = "testuser"
        form_data.password = "correct_password"

        with mock.patch("app.auth.endpoints.is_blocked", return_value=False):
            with mock.patch("app.auth.endpoints.log_login_attempt"):
                with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
                    mock_repo = mock.MagicMock()
                    mock_repo.verify_credentials = mock.AsyncMock(return_value=mock_user)
                    mock_repo_cls.return_value = mock_repo

                    with mock.patch("app.auth.endpoints.log_login_success"):
                        with mock.patch("app.auth.endpoints.get_settings") as mock_settings:
                            mock_settings.return_value.use_https = False
                            mock_settings.return_value.access_token_expire_minutes = 15
                            mock_settings.return_value.refresh_token_expire_days = 7

                            response = await login(
                                request=mock_request,
                                form_data=form_data,
                                db=mock_db,
                                jwt_handler=jwt_handler,
                            )

                            assert isinstance(response, Response)
                            data = response.body
                            assert b"access_token" in data
                            assert b"refresh_token" in data


# ---------------------------------------------------------------------------
# Tests for refresh_token endpoint
# ---------------------------------------------------------------------------


class TestRefreshTokenEndpoint:
    """Unit tests for refresh_token endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_refresh_token_user_id_none(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler
    ) -> None:
        """Test refresh returns 401 when token has no user_id."""
        from fastapi import HTTPException

        token_request = RefreshTokenRequest(refresh_token="some_token")

        mock_jwt = mock.MagicMock()
        mock_jwt.verify_refresh_token.return_value = {"sub": None}

        with pytest.raises(HTTPException) as exc_info:
            await refresh_token(
                request=mock_request,
                token_request=token_request,
                db=mock_db,
                jwt_handler=mock_jwt,
            )

        assert exc_info.value.status_code == 401
        assert "Invalid refresh token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_token(self, mock_request: mock.MagicMock, mock_db: mock.MagicMock) -> None:
        """Test refresh returns 401 for invalid token."""
        from app.auth.jwt_handler import InvalidTokenError
        from fastapi import HTTPException

        token_request = RefreshTokenRequest(refresh_token="invalid_token")

        mock_jwt = mock.MagicMock()
        mock_jwt.verify_refresh_token.side_effect = InvalidTokenError("bad token")

        with mock.patch("app.auth.endpoints.log_suspicious_activity"):
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(
                    request=mock_request,
                    token_request=token_request,
                    db=mock_db,
                    jwt_handler=mock_jwt,
                )

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler
    ) -> None:
        """Test refresh returns 401 for inactive user."""
        from fastapi import HTTPException

        inactive_user = User(id=1, username="inactive", email="i@e.com", hashed_password="h", is_active=False)

        token_request = RefreshTokenRequest(refresh_token=jwt_handler.create_refresh_token("1"))

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_id = mock.AsyncMock(return_value=inactive_user)
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_suspicious_activity"):
                with pytest.raises(HTTPException) as exc_info:
                    await refresh_token(
                        request=mock_request,
                        token_request=token_request,
                        db=mock_db,
                        jwt_handler=jwt_handler,
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, jwt_handler: JWTHandler, mock_user: User
    ) -> None:
        """Test successful token refresh."""
        from fastapi import Response

        token_request = RefreshTokenRequest(refresh_token=jwt_handler.create_refresh_token("1"))

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_id = mock.AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_token_refresh"):
                response = await refresh_token(
                    request=mock_request,
                    token_request=token_request,
                    db=mock_db,
                    jwt_handler=jwt_handler,
                )

                assert isinstance(response, Response)
                data = response.body
                assert b"access_token" in data


# ---------------------------------------------------------------------------
# Tests for logout endpoint
# ---------------------------------------------------------------------------


class TestLogoutEndpoint:
    """Unit tests for logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_html_redirect(self, mock_user: User) -> None:
        """Test logout returns redirect for HTML requests."""
        from starlette.datastructures import Address
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/auth/logout",
            "headers": [(b"accept", b"text/html")],
            "client": Address(host="127.0.0.1", port=8000),
        }
        request = Request(scope)

        with mock.patch("app.auth.endpoints.log_logout"):
            response = await logout(request=request, current_user=mock_user)

            assert response.status_code == 303

    @pytest.mark.asyncio
    async def test_logout_json_response(self, mock_user: User) -> None:
        """Test logout returns JSON for API requests."""
        from starlette.datastructures import Address
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/auth/logout",
            "headers": [(b"accept", b"application/json")],
            "client": Address(host="127.0.0.1", port=8000),
        }
        request = Request(scope)

        with mock.patch("app.auth.endpoints.log_logout"):
            response = await logout(request=request, current_user=mock_user)

            assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests for get_current_user_info endpoint
# ---------------------------------------------------------------------------


class TestGetCurrentUserInfo:
    """Unit tests for get_current_user_info endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_user_info(self, mock_user: User) -> None:
        """Test getting current user info."""
        result = await get_current_user_info(current_user=mock_user)

        assert result.username == "testuser"
        assert result.email == "test@example.com"


# ---------------------------------------------------------------------------
# Tests for change_password endpoint
# ---------------------------------------------------------------------------


class TestChangePasswordEndpoint:
    """Unit tests for change_password endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test change password returns 400 for wrong current password."""
        from fastapi import HTTPException

        password_data = ChangePassword(
            current_password="wrong_password",
            new_password="new_password_123",
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.password_hasher.verify_password.return_value = False
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_suspicious_activity"):
                with pytest.raises(HTTPException) as exc_info:
                    await change_password(
                        request=mock_request,
                        password_data=password_data,
                        db=mock_db,
                        current_user=mock_user,
                    )

                assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_success(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test successful password change."""
        password_data = ChangePassword(
            current_password="correct_password",
            new_password="new_password_123",
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.password_hasher.verify_password.return_value = True
            mock_repo.change_password = mock.AsyncMock()
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_password_change"):
                result = await change_password(
                    request=mock_request,
                    password_data=password_data,
                    db=mock_db,
                    current_user=mock_user,
                )

                assert result["message"] == "Password changed successfully"
                mock_repo.change_password.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests for update_profile endpoint
# ---------------------------------------------------------------------------


class TestUpdateProfileEndpoint:
    """Unit tests for update_profile endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_update_profile_success(self, mock_db: mock.MagicMock, mock_user: User) -> None:
        """Test successful profile update."""
        update_data = UserUpdate(full_name="Updated Name", email="updated@example.com")

        updated_user = User(
            id=1,
            username="testuser",
            email="updated@example.com",
            hashed_password="h",
            is_active=True,
            full_name="Updated Name",
            created_at=datetime.now(),
        )

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.update_user = mock.AsyncMock(return_value=updated_user)
            mock_repo_cls.return_value = mock_repo

            result = await update_profile(
                update_data=update_data,
                db=mock_db,
                current_user=mock_user,
            )

            assert result.full_name == "Updated Name"
            assert result.email == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(self, mock_db: mock.MagicMock, mock_user: User) -> None:
        """Test update profile returns 404 when user not found."""
        from fastapi import HTTPException

        update_data = UserUpdate(full_name="Updated Name", email="updated@example.com")

        with mock.patch("app.auth.endpoints.UserRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.update_user = mock.AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await update_profile(
                    update_data=update_data,
                    db=mock_db,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests for create_api_key endpoint
# ---------------------------------------------------------------------------


class TestCreateApiKeyEndpoint:
    """Unit tests for create_api_key endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_create_api_key_success(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test successful API key creation."""
        key_data = APIKeyCreate(name="Test Key", permissions=["read"], expires_days=30)

        mock_api_key_record = mock.MagicMock()
        mock_api_key_record.id = 1
        mock_api_key_record.name = "Test Key"
        mock_api_key_record.user_id = 1
        mock_api_key_record.key_prefix = "glp_test"
        mock_api_key_record.permissions = '["read"]'
        mock_api_key_record.is_active = True
        mock_api_key_record.created_at = mock.MagicMock()
        mock_api_key_record.expires_at = mock.MagicMock()

        with mock.patch("app.auth.endpoints.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.create_api_key = mock.AsyncMock(return_value=(mock_api_key_record, "glp_secret_key"))
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_api_key_created"):
                result = await create_api_key(
                    request=mock_request,
                    key_data=key_data,
                    db=mock_db,
                    current_user=mock_user,
                )

                assert result.name == "Test Key"
                assert result.secret == "glp_secret_key"


# ---------------------------------------------------------------------------
# Tests for delete_api_key endpoint
# ---------------------------------------------------------------------------


class TestDeleteApiKeyEndpoint:
    """Unit tests for delete_api_key endpoint covering all code paths."""

    @pytest.mark.asyncio
    async def test_delete_api_key_not_found(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test delete API key returns 404 when key not found."""
        from fastapi import HTTPException

        with mock.patch("app.auth.endpoints.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_id = mock.AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await delete_api_key(
                    request=mock_request,
                    key_id=999,
                    db=mock_db,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_api_key_not_authorized(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test delete API key returns 403 when not owned by user."""
        from fastapi import HTTPException

        mock_key = mock.MagicMock()
        mock_key.user_id = 999  # Different user

        with mock.patch("app.auth.endpoints.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_id = mock.AsyncMock(return_value=mock_key)
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await delete_api_key(
                    request=mock_request,
                    key_id=1,
                    db=mock_db,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_api_key_success(
        self, mock_request: mock.MagicMock, mock_db: mock.MagicMock, mock_user: User
    ) -> None:
        """Test successful API key deletion."""
        mock_key = mock.MagicMock()
        mock_key.user_id = 1  # Same user
        mock_key.name = "Test Key"

        with mock.patch("app.auth.endpoints.APIKeyRepository") as mock_repo_cls:
            mock_repo = mock.MagicMock()
            mock_repo.get_by_id = mock.AsyncMock(return_value=mock_key)
            mock_repo.delete_api_key = mock.AsyncMock()
            mock_repo_cls.return_value = mock_repo

            with mock.patch("app.auth.endpoints.log_api_key_deleted"):
                result = await delete_api_key(
                    request=mock_request,
                    key_id=1,
                    db=mock_db,
                    current_user=mock_user,
                )

                assert result["message"] == "API key deleted successfully"
                mock_repo.delete_api_key.assert_awaited_once()
