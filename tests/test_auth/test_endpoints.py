"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient

from app.database.session_handler import get_async_session
from app.auth.repository import UserRepository


@pytest.fixture
def auth_client():
    """Create a test client for auth endpoints."""
    from main import app
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def db():
    """Create a test database session."""
    session = await get_async_session("auth")
    try:
        yield session
    finally:
        await session.close()


class TestRegisterEndpoint:
    """Test cases for /auth/register endpoint."""

    def test_register_success(self, auth_client):
        """Test successful user registration."""
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "test_password_123",
                "full_name": "Test User"
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True

    def test_register_duplicate_username(self, auth_client):
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
        assert "already registered" in response.json()["detail"]

    def test_register_duplicate_email(self, auth_client):
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
        assert "already registered" in response.json()["detail"]

    def test_register_invalid_email(self, auth_client):
        """Test registration with invalid email."""
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "invalid-email",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_short_password(self, auth_client):
        """Test registration with short password."""
        response = auth_client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    """Test cases for /auth/token endpoint."""

    def test_login_success(self, auth_client):
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
            json={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, auth_client):
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
            json={
                "username": "testuser",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, auth_client):
        """Test login with nonexistent user."""
        response = auth_client.post(
            "/auth/token",
            json={
                "username": "nonexistent",
                "password": "test_password_123"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRefreshEndpoint:
    """Test cases for /auth/refresh endpoint."""

    def test_refresh_success(self, auth_client):
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
            json={
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

    def test_refresh_invalid_token(self, auth_client):
        """Test refresh with invalid token."""
        response = auth_client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutEndpoint:
    """Test cases for /auth/logout endpoint."""

    def test_logout_success(self, auth_client):
        """Test successful logout."""
        response = auth_client.post("/auth/logout")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Logged out successfully"


class TestMeEndpoint:
    """Test cases for /auth/me endpoint."""

    def test_me_success(self, auth_client):
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
            json={
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

    def test_me_unauthorized(self, auth_client):
        """Test getting current user without authentication."""
        response = auth_client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAPIKeyEndpoints:
    """Test cases for API key endpoints."""

    def test_create_api_key(self, auth_client):
        """Test creating an API key."""
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
            json={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Create API key
        response = auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": "Test API Key",
                "permissions": ["read", "write"],
                "expires_days": 30
            }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test API Key"
        assert "secret" in data
        assert data["secret"].startswith("glp_")

    def test_list_api_keys(self, auth_client):
        """Test listing API keys."""
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
            json={
                "username": "testuser",
                "password": "test_password_123"
            }
        )
        
        access_token = login_response.json()["access_token"]
        
        # Create an API key first
        auth_client.post(
            "/auth/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": "Test API Key",
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
        assert len(data) == 1
        assert data[0]["name"] == "Test API Key"
        assert "secret" not in data[0]

    def test_delete_api_key(self, auth_client):
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
            json={
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
