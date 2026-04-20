"""Tests for authentication repository."""

import pytest
import pytest_asyncio

from app.auth.repository import UserRepository, APIKeyRepository, PasswordHasherService
from app.database.session_handler import get_async_session, init_async_databases


@pytest_asyncio.fixture(scope="session")
async def init_db():
    """Initialize async databases before tests."""
    await init_async_databases()


@pytest_asyncio.fixture
async def db(init_db):
    """Create a test database session."""
    session = await get_async_session("auth")
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def password_hasher():
    """Create a password hasher for testing."""
    return PasswordHasherService()


class TestPasswordHasherService:
    """Test cases for PasswordHasherService."""

    def test_hash_password(self, password_hasher):
        """Test password hashing."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password

    def test_verify_password_correct(self, password_hasher):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)
        
        assert password_hasher.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, password_hasher):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)
        
        assert password_hasher.verify_password("wrong_password", hashed) is False

    def test_verify_password_invalid_hash(self, password_hasher):
        """Test password verification with invalid hash."""
        assert password_hasher.verify_password("any_password", "invalid_hash") is False

    def test_needs_rehash(self, password_hasher):
        """Test checking if hash needs rehashing."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)
        
        # Fresh hash should not need rehashing
        assert password_hasher.needs_rehash(hashed) is False


class TestUserRepository:
    """Test cases for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(self, db):
        """Test creating a user."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123",
            full_name="Test User",
            permissions=["read", "write"]
        )
        
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.hashed_password != "test_password_123"

    @pytest.mark.asyncio
    async def test_get_by_id(self, db):
        """Test getting user by ID."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        retrieved = await repo.get_by_id(user.id)
        assert retrieved is not None
        assert retrieved.id == user.id

    @pytest.mark.asyncio
    async def test_get_by_username(self, db):
        """Test getting user by username."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser_username",
            email="test_username@example.com",
            password="test_password_123"
        )
        
        retrieved = await repo.get_by_username("testuser_username")
        assert retrieved is not None
        assert retrieved.username == "testuser_username"

    @pytest.mark.asyncio
    async def test_get_by_email(self, db):
        """Test getting user by email."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser_email",
            email="test_email@example.com",
            password="test_password_123"
        )
        
        retrieved = await repo.get_by_email("test_email@example.com")
        assert retrieved is not None
        assert retrieved.email == "test_email@example.com"

    @pytest.mark.asyncio
    async def test_verify_credentials_correct(self, db):
        """Test verifying correct credentials."""
        repo = UserRepository(db)
        
        await repo.create_user(
            username="testuser_verify_correct",
            email="test_verify_correct@example.com",
            password="test_password_123"
        )
        
        user = await repo.verify_credentials("testuser_verify_correct", "test_password_123")
        assert user is not None
        assert user.username == "testuser_verify_correct"

    @pytest.mark.asyncio
    async def test_verify_credentials_incorrect(self, db):
        """Test verifying incorrect credentials."""
        repo = UserRepository(db)
        
        await repo.create_user(
            username="testuser_verify_incorrect",
            email="test_verify_incorrect@example.com",
            password="test_password_123"
        )
        
        user = await repo.verify_credentials("testuser_verify_incorrect", "wrong_password")
        assert user is None

    @pytest.mark.asyncio
    async def test_update_user(self, db):
        """Test updating user."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        updated = await repo.update_user(user.id, full_name="Updated Name", email="updated@example.com")
        assert updated is not None
        assert updated.full_name == "Updated Name"
        assert updated.email == "updated@example.com"

    @pytest.mark.asyncio
    async def test_change_password(self, db):
        """Test changing password."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser_change_password",
            email="test_change_password@example.com",
            password="old_password"
        )
        
        success = await repo.change_password(user.id, "new_password_123")
        assert success is True
        
        # Verify old password doesn't work
        assert await repo.verify_credentials("testuser_change_password", "old_password") is None
        
        # Verify new password works
        user = await repo.verify_credentials("testuser_change_password", "new_password_123")
        assert user is not None

    @pytest.mark.asyncio
    async def test_delete_user(self, db):
        """Test deleting user."""
        repo = UserRepository(db)
        
        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        success = await repo.delete_user(user.id)
        assert success is True
        
        # Verify user is deleted
        deleted = await repo.get_by_id(user.id)
        assert deleted is None


class TestAPIKeyRepository:
    """Test cases for APIKeyRepository."""

    @pytest.mark.asyncio
    async def test_create_api_key(self, db):
        """Test creating an API key."""
        user_repo = UserRepository(db)
        api_key_repo = APIKeyRepository(db)
        
        user = await user_repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id,
            name="Test API Key",
            permissions=["read", "write"],
            expires_days=30
        )
        
        assert api_key_record is not None
        assert api_key_record.user_id == user.id
        assert api_key_record.name == "Test API Key"
        assert api_key_record.is_active is True
        assert secret.startswith("glp_")
        assert api_key_record.hashed_key != secret

    @pytest.mark.asyncio
    async def test_verify_and_get(self, db):
        """Test verifying and getting API key."""
        user_repo = UserRepository(db)
        api_key_repo = APIKeyRepository(db)
        
        user = await user_repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id,
            name="Test API Key"
        )
        
        verified = await api_key_repo.verify_and_get(secret)
        assert verified is not None
        assert verified.id == api_key_record.id
        # Check that last_used_at was updated
        assert verified.last_used_at is not None

    @pytest.mark.asyncio
    async def test_verify_and_get_invalid_key(self, db):
        """Test verifying invalid API key."""
        api_key_repo = APIKeyRepository(db)
        
        verified = await api_key_repo.verify_and_get("glp_invalid_key_here")
        assert verified is None

    @pytest.mark.asyncio
    async def test_get_user_api_keys(self, db):
        """Test getting user's API keys."""
        user_repo = UserRepository(db)
        api_key_repo = APIKeyRepository(db)
        
        user = await user_repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        await api_key_repo.create_api_key(user_id=user.id, name="Key 1")
        await api_key_repo.create_api_key(user_id=user.id, name="Key 2")
        
        keys = await api_key_repo.get_user_api_keys(user.id)
        assert len(keys) == 2

    @pytest.mark.asyncio
    async def test_delete_api_key(self, db):
        """Test deleting API key."""
        user_repo = UserRepository(db)
        api_key_repo = APIKeyRepository(db)
        
        user = await user_repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        api_key_record, _ = await api_key_repo.create_api_key(
            user_id=user.id,
            name="Test API Key"
        )
        
        success = await api_key_repo.delete_api_key(api_key_record.id)
        assert success is True
        
        # Verify key is deleted
        deleted = await api_key_repo.get_by_id(api_key_record.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_deactivate_api_key(self, db):
        """Test deactivating API key."""
        user_repo = UserRepository(db)
        api_key_repo = APIKeyRepository(db)
        
        user = await user_repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123"
        )
        
        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id,
            name="Test API Key"
        )
        
        success = await api_key_repo.deactivate_api_key(api_key_record.id)
        assert success is True
        
        # Verify key is deactivated
        api_key_record = await api_key_repo.get_by_id(api_key_record.id)
        assert api_key_record.is_active is False
        
        # Verify deactivated key cannot be used
        verified = await api_key_repo.verify_and_get(secret)
        assert verified is None
