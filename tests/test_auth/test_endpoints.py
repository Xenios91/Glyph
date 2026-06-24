"""Tests for authentication endpoints."""

from typing import Any, Generator

import pytest
import time
from fastapi import status
from fastapi.testclient import TestClient

from app.database.session_handler import get_async_session


@pytest.fixture
def auth_client() -> Generator[TestClient, Any, Any]:
    """Create a test client for auth endpoints."""
    from main import app
    with TestClient(app) as client:
        yield client


def get_unique_suffix() -> int:
    """Generate a unique suffix for test usernames to avoid conflicts."""
    return int(time.time() * 1000) % 100000


@pytest.fixture
async def db() -> Any:
    """Create a test database session."""
    session = await get_async_session("auth")
    try:
        yield session
    finally:
        await session.close()


class TestRegisterEndpoint:
    """Test cases for /auth/register endpoint."""

    def test_register_success(self, auth_client: TestClient) -> None:
        """Test successful user registration."""
        unique_suffix = get_unique_suffix()
        response = auth_client.post(
            "/auth/register",
            json={
                "username": f"testuser_register_success_{unique_suffix}",
                "email": f"test_register_success_{unique_suffix}@example.com",
                "password": "test_password_123",
                "full_name": "Test User"
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == f"testuser_register_success_{unique_suffix}"
        assert data["email"] == f"test_register_success_{unique_suffix}@example.com"
        assert data["is_active"] is True

    def test_register_duplicate_username(self, auth_client: TestClient) -> None:
        """Test registration with duplicate username."""
        # Register first user
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        # Try to register again
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "different@example.com",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["error"]["message"]

    def test_register_duplicate_email(self, auth_client: TestClient) -> None:
        """Test registration with duplicate email."""
        # Register first user
        auth_client.post(
            "/auth/register",
            json={
                "username": "user1",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        # Try to register with same email
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "user2",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["error"]["message"]

    def test_register_invalid_email(self, auth_client: TestClient) -> None:
        """Test registration with invalid email."""
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "invalid-email",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_register_short_password(self, auth_client: TestClient) -> None:
        """Test registration with short password."""
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestLoginEndpoint:
    """Test cases for /auth/token endpoint."""

    def test_login_success(self, auth_client: TestClient) -> None:
        """Test successful login."""
        # Register user first
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        # Login
        response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, auth_client: TestClient) -> None:
        """Test login with invalid credentials."""
        # Register user first
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        # Try to login with wrong password
        response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, auth_client: TestClient) -> None:
        """Test login with nonexistent user."""
        response = auth_client.post(
            "/auth/token",
            data={
                "username": "nonexistent",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRefreshEndpoint:
    """Test cases for /auth/refresh endpoint."""

    def test_refresh_success(self, auth_client: TestClient) -> None:
        """Test successful token refresh."""
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        login_response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, auth_client: TestClient) -> None:
        """Test refresh with invalid token."""
        response = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutEndpoint:
    """Test cases for /auth/logout endpoint."""

    def test_logout_success(self, auth_client: TestClient) -> None:
        """Test successful logout."""
        # Register and login first to get an access token
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": "testuser", "password": "test_password_123"}
        )
        access_token = login_response.json()["access_token"]
        response = auth_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK


class TestMeEndpoint:
    """Test cases for /auth/me endpoint."""

    def test_me_success(self, auth_client: TestClient) -> None:
        """Test getting current user info."""
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        login_response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Get current user
        response = auth_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_me_unauthorized(self, auth_client: TestClient) -> None:
        """Test getting current user without authentication."""
        response = auth_client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAPIKeyEndpoints:
    """Test cases for API key endpoints."""

    def test_create_api_key(self, auth_client: TestClient) -> None:
        """Test creating an API key."""
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser_create_api_key",
                "email": "test_create_api_key@example.com",
                "password": "test_password_123"
            }
        )
        
        login_response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser_create_api_key",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Create API key
        response = auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": "Test API Key Create",
                "permissions": ["read", "write"],
                "expires_days": 30
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test API Key Create"
        assert "secret" in data
        assert data["secret"].startswith("glp_")

    def test_list_api_keys(self, auth_client: TestClient) -> None:
        """Test listing API keys."""
        unique_suffix = get_unique_suffix()
        
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": f"testuser_list_api_keys_{unique_suffix}",
                "email": f"test_list_api_keys_{unique_suffix}@example.com",
                "password": "test_password_123"
            }
        )
        
        login_response = auth_client.post(
            "/auth/token",
            data={
                "username": f"testuser_list_api_keys_{unique_suffix}",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Create an API key first
        auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": f"Test API Key List {unique_suffix}",
                "permissions": ["read"]
            }
        )
        
        # List API keys
        response = auth_client.get(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Filter for keys belonging to this user (by name pattern)
        user_keys: list[dict[str, Any]] = [k for k in data if f"Test API Key List {unique_suffix}" in k["name"]]
        assert len(user_keys) >= 1
        assert user_keys[0]["name"] == f"Test API Key List {unique_suffix}"
        assert "secret" not in user_keys[0]

    def test_delete_api_key(self, auth_client: TestClient) -> None:
        """Test deleting an API key."""
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123"
            }
        )
        
        login_response = auth_client.post(
            "/auth/token",
            data={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Create an API key first
        create_response = auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": "Test API Key",
                "permissions": ["read"]
            }
        )
        
        api_key_id = create_response.json()["id"]
        
        # Delete API key
        response = auth_client.delete(
            f"/auth/api-keys/{api_key_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "API key deleted successfully"

    def test_delete_api_key_not_found(self, auth_client: TestClient) -> None:
        """Test deleting a non-existent API key."""
        # Register user and login
        auth_client.post(
            "/auth/register",
            json={
                "username": "testuser_delete_not_found",
                "email": "test_delete_not_found@example.com",
                "password": "test_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": "testuser_delete_not_found", "password": "test_password_123"}
        )
        access_token = login_response.json()["access_token"]

        # Try to delete non-existent key
        response = auth_client.delete(
            "/auth/api-keys/99999",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["error"]["message"]

    def test_delete_api_key_not_authorized(self, auth_client: TestClient) -> None:
        """Test deleting another user's API key."""
        # Create two users
        auth_client.post(
            "/auth/register",
            json={
                "username": "user_a",
                "email": "user_a@example.com",
                "password": "test_password_123"
            }
        )
        auth_client.post(
            "/auth/register",
            json={
                "username": "user_b",
                "email": "user_b@example.com",
                "password": "test_password_123"
            }
        )

        # Login as user_a and create a key
        login_a = auth_client.post(
            "/auth/token",
            data={"username": "user_a", "password": "test_password_123"}
        )
        token_a = login_a.json()["access_token"]
        create_resp = auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "UserA Key", "permissions": ["read"]}
        )
        key_id = create_resp.json()["id"]

        # Login as user_b and try to delete user_a's key
        login_b = auth_client.post(
            "/auth/token",
            data={"username": "user_b", "password": "test_password_123"}
        )
        token_b = login_b.json()["access_token"]

        response = auth_client.delete(
            f"/auth/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestChangePasswordEndpoint:
    """Test cases for /auth/change-password endpoint."""

    def test_change_password_success(self, auth_client: TestClient) -> None:
        """Test successful password change."""
        suffix = get_unique_suffix()
        username = f"testuser_change_pw_{suffix}"
        email = f"test_change_pw_{suffix}@example.com"
        # Register and login
        auth_client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "old_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": username, "password": "old_password_123"}
        )
        access_token = login_response.json()["access_token"]

        # Change password
        response = auth_client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "old_password_123",
                "new_password": "new_password_456"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Password changed successfully"

    def test_change_password_wrong_current(self, auth_client: TestClient) -> None:
        """Test password change with wrong current password."""
        suffix = get_unique_suffix()
        username = f"testuser_wrong_pw_{suffix}"
        email = f"test_wrong_pw_{suffix}@example.com"
        # Register and login
        auth_client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "correct_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": username, "password": "correct_password_123"}
        )
        access_token = login_response.json()["access_token"]

        # Try to change with wrong current password
        response = auth_client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "wrong_password",
                "new_password": "new_password_456"
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "incorrect" in response.json()["error"]["message"]


class TestUpdateProfileEndpoint:
    """Test cases for /auth/update-profile endpoint."""

    def test_update_profile_success(self, auth_client: TestClient) -> None:
        """Test successful profile update."""
        suffix = get_unique_suffix()
        username = f"testuser_update_{suffix}"
        email = f"test_update_{suffix}@example.com"
        # Register and login
        auth_client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "test_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": username, "password": "test_password_123"}
        )
        access_token = login_response.json()["access_token"]

        # Update profile
        response = auth_client.post(
            "/auth/update-profile",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "full_name": "Updated Name",
                "email": f"updated_{suffix}@example.com"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["email"] == f"updated_{suffix}@example.com"

    def test_update_profile_unauthorized(self, auth_client: TestClient) -> None:
        """Test profile update without authentication."""
        response = auth_client.post(
            "/auth/update-profile",
            json={"full_name": "Test", "email": "test@example.com"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutHTMLRedirect:
    """Test logout with HTML accept header."""

    def test_logout_html_redirect(self, auth_client: TestClient) -> None:
        """Test logout returns redirect when Accept is text/html."""
        suffix = get_unique_suffix()
        username = f"testuser_logout_html_{suffix}"
        email = f"test_logout_html_{suffix}@example.com"
        # Register and login
        auth_client.post(
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "test_password_123"
            }
        )
        login_response = auth_client.post(
            "/auth/token",
            data={"username": username, "password": "test_password_123"}
        )
        access_token = login_response.json()["access_token"]

        # Logout with Accept: text/html
        response = auth_client.get(
            "/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "text/html"
            },
            follow_redirects=False
        )

        assert response.status_code == 303


class TestLoginBlockedUser:
    """Test login with blocked user."""

    def test_login_blocked_user(self, auth_client: TestClient) -> None:
        """Test login returns 429 when user is blocked."""
        with pytest.MonkeyPatch.context() as mp:
            # Mock is_blocked to return True
            mp.setattr("app.auth.endpoints.is_blocked", lambda *a, **k: True)

            response = auth_client.post(
                "/auth/token",
                data={"username": "blocked_user", "password": "any_password"}
            )

            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestRefreshTokenEdgeCases:
    """Test edge cases for /auth/refresh endpoint."""

    def test_refresh_empty_string_token(self, auth_client: TestClient) -> None:
        """Test refresh with empty string token."""
        response = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": ""}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
