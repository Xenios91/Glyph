"""Tests for authentication repository."""

from datetime import UTC
from typing import Any

import pytest
import pytest_asyncio
from app.database.models import Base
from app.database.repository import APIKeyRepository, PasswordHasherService, UserRepository
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    get_async_session,
    init_async_databases,
)  # pyright: ignore[reportPrivateUsage]


@pytest_asyncio.fixture(scope="module", autouse=True)
async def auth_db_lifecycle():
    """Initialize and cleanup in-memory databases for this test module."""
    await init_async_databases()
    # Ensure auth tables are fresh
    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def db() -> Any:
    """Create a test database session for the auth database.

    Drops and recreates auth tables before each test for isolation,
    then yields a fresh AsyncSession. Session is closed after each test.
    """
    # Reset auth tables for test isolation
    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    session = await get_async_session("auth")
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def password_hasher() -> PasswordHasherService:
    """Create a password hasher for testing with low memory cost."""
    return PasswordHasherService(
        time_cost=1,
        memory_cost=1024,  # 1 MiB - low enough for constrained environments
        parallelism=1,
        hash_len=16,
        salt_len=8,
    )


class TestPasswordHasherService:
    """Test cases for PasswordHasherService."""

    def test_hash_password(self, password_hasher: PasswordHasherService) -> None:
        """Test password hashing."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password

    def test_verify_password_correct(self, password_hasher: PasswordHasherService) -> None:
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)

        assert password_hasher.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, password_hasher: PasswordHasherService) -> None:
        """Test password verification with incorrect password."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)

        assert password_hasher.verify_password("wrong_password", hashed) is False

    def test_verify_password_invalid_hash(self, password_hasher: PasswordHasherService) -> None:
        """Test password verification with invalid hash."""
        assert password_hasher.verify_password("any_password", "invalid_hash") is False

    def test_needs_rehash(self, password_hasher: PasswordHasherService) -> None:
        """Test checking if hash needs rehashing."""
        password = "test_password_123"
        hashed = password_hasher.hash_password(password)

        # Fresh hash should not need rehashing
        assert password_hasher.needs_rehash(hashed) is False


class TestUserRepository:
    """Test cases for UserRepository."""

    async def test_create_user(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test creating a user."""
        repo = UserRepository(db, password_hasher)

        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password="test_password_123",
            full_name="Test User",
            permissions=["read", "write"],
        )

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.hashed_password != "test_password_123"

    async def test_get_by_id(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting user by ID."""
        repo = UserRepository(db, password_hasher)

        created_user = await repo.create_user(
            username="testuser", email="test@example.com", password="test_password_123"
        )

        retrieved = await repo.get_by_id(created_user.id)
        assert retrieved is not None
        assert retrieved.id == created_user.id

    async def test_get_by_username(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting user by username."""
        repo = UserRepository(db, password_hasher)

        await repo.create_user(
            username="testuser_username", email="test_username@example.com", password="test_password_123"
        )

        retrieved = await repo.get_by_username("testuser_username")
        assert retrieved is not None
        assert retrieved.username == "testuser_username"

    async def test_get_by_email(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting user by email."""
        repo = UserRepository(db, password_hasher)

        await repo.create_user(username="testuser_email", email="test_email@example.com", password="test_password_123")

        retrieved = await repo.get_by_email("test_email@example.com")
        assert retrieved is not None
        assert retrieved.email == "test_email@example.com"

    async def test_verify_credentials_correct(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test verifying correct credentials."""
        repo = UserRepository(db, password_hasher)

        await repo.create_user(
            username="testuser_verify_correct", email="test_verify_correct@example.com", password="test_password_123"
        )

        user = await repo.verify_credentials("testuser_verify_correct", "test_password_123")
        assert user is not None
        assert user.username == "testuser_verify_correct"

    async def test_verify_credentials_incorrect(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test verifying incorrect credentials."""
        repo = UserRepository(db, password_hasher)

        await repo.create_user(
            username="testuser_verify_incorrect",
            email="test_verify_incorrect@example.com",
            password="test_password_123",
        )

        user = await repo.verify_credentials("testuser_verify_incorrect", "wrong_password")
        assert user is None

    async def test_update_user(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test updating user."""
        repo = UserRepository(db, password_hasher)

        user = await repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        updated = await repo.update_user(user.id, full_name="Updated Name", email="updated@example.com")
        assert updated is not None
        assert updated.full_name == "Updated Name"
        assert updated.email == "updated@example.com"

    async def test_change_password(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test changing password."""
        repo = UserRepository(db, password_hasher)

        user = await repo.create_user(
            username="testuser_change_password", email="test_change_password@example.com", password="old_password"
        )

        success = await repo.change_password(user.id, "new_password_123")
        assert success is True

        # Verify old password doesn't work
        assert await repo.verify_credentials("testuser_change_password", "old_password") is None

        # Verify new password works
        user = await repo.verify_credentials("testuser_change_password", "new_password_123")
        assert user is not None

    async def test_delete_user(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test deleting user."""
        repo = UserRepository(db, password_hasher)

        user = await repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        success = await repo.delete_user(user.id)
        assert success is True

        # Verify user is deleted
        deleted = await repo.get_by_id(user.id)
        assert deleted is None

    async def test_get_by_id_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting non-existent user by ID returns None."""
        repo = UserRepository(db, password_hasher)
        retrieved = await repo.get_by_id(99999)
        assert retrieved is None

    async def test_get_by_username_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting non-existent user by username returns None."""
        repo = UserRepository(db, password_hasher)
        retrieved = await repo.get_by_username("nonexistent")
        assert retrieved is None

    async def test_get_by_email_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting non-existent user by email returns None."""
        repo = UserRepository(db, password_hasher)
        retrieved = await repo.get_by_email("nonexistent@example.com")
        assert retrieved is None

    async def test_verify_credentials_nonexistent_user(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test verify_credentials returns None and performs timing attack prevention for unknown user."""
        repo = UserRepository(db, password_hasher)
        user = await repo.verify_credentials("nonexistent_user", "any_password")
        assert user is None

    async def test_verify_credentials_rehash(self, db: Any) -> None:
        """Test verify_credentials rehashes password when hash parameters are outdated."""
        # Create a hasher with very low params so the hash is "outdated" for a different hasher
        old_hasher = PasswordHasherService(time_cost=1, memory_cost=512, parallelism=1, hash_len=16, salt_len=8)
        repo = UserRepository(db, old_hasher)

        await repo.create_user(
            username="testuser_rehash",
            email="rehash@example.com",
            password="test_password_123",
        )

        # Now verify with a different hasher that has higher params — the hash should need rehashing
        new_hasher = PasswordHasherService(time_cost=2, memory_cost=32768, parallelism=2, hash_len=32, salt_len=16)
        repo_new = UserRepository(db, new_hasher)
        user = await repo_new.verify_credentials("testuser_rehash", "test_password_123")
        assert user is not None
        # The hash should have been rehashed by the new hasher
        assert new_hasher.needs_rehash(user.hashed_password) is False

    async def test_update_user_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test updating non-existent user returns None."""
        repo = UserRepository(db, password_hasher)
        updated = await repo.update_user(99999, full_name="No One")
        assert updated is None

    async def test_change_password_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test changing password for non-existent user returns False."""
        repo = UserRepository(db, password_hasher)
        success = await repo.change_password(99999, "new_password")
        assert success is False

    async def test_delete_user_not_found(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test deleting non-existent user returns False."""
        repo = UserRepository(db, password_hasher)
        success = await repo.delete_user(99999)
        assert success is False


class TestAPIKeyRepository:
    """Test cases for APIKeyRepository."""

    async def test_create_api_key(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test creating an API key."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id, name="Test API Key", permissions=["read", "write"], expires_days=30
        )

        assert api_key_record is not None
        assert api_key_record.user_id == user.id
        assert api_key_record.name == "Test API Key"
        assert api_key_record.is_active is True
        assert secret.startswith("glp_")
        assert api_key_record.hashed_key != secret

    async def test_verify_and_get(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test verifying and getting API key."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        api_key_record, secret = await api_key_repo.create_api_key(user_id=user.id, name="Test API Key")

        verified = await api_key_repo.verify_and_get(secret)
        assert verified is not None
        assert verified.id == api_key_record.id
        # Check that last_used_at was updated
        assert verified.last_used_at is not None

    async def test_verify_and_get_invalid_key(self, db: Any) -> None:
        """Test verifying invalid API key."""
        api_key_repo = APIKeyRepository(db)

        verified = await api_key_repo.verify_and_get("glp_invalid_key_here")
        assert verified is None

    async def test_get_user_api_keys(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test getting user's API keys."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        await api_key_repo.create_api_key(user_id=user.id, name="Key 1")
        await api_key_repo.create_api_key(user_id=user.id, name="Key 2")

        keys = await api_key_repo.get_user_api_keys(user.id)
        assert len(keys) == 2

    async def test_delete_api_key(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test deleting API key."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        api_key_record, _ = await api_key_repo.create_api_key(user_id=user.id, name="Test API Key")

        success = await api_key_repo.delete_api_key(api_key_record.id)
        assert success is True

        # Verify key is deleted
        deleted = await api_key_repo.get_by_id(api_key_record.id)
        assert deleted is None

    async def test_deactivate_api_key(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test deactivating API key."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(username="testuser", email="test@example.com", password="test_password_123")

        api_key_record, secret = await api_key_repo.create_api_key(user_id=user.id, name="Test API Key")

        success = await api_key_repo.deactivate_api_key(api_key_record.id)
        assert success is True

        # Verify key is deactivated
        deactivated_key = await api_key_repo.get_by_id(api_key_record.id)
        assert deactivated_key is not None
        assert deactivated_key.is_active is False

        # Verify deactivated key cannot be used
        verified = await api_key_repo.verify_and_get(secret)
        assert verified is None

    async def test_generate_api_key_format(self, db: Any) -> None:
        """Test generate_api_key produces correctly prefixed keys."""
        api_key_repo = APIKeyRepository(db)
        key = api_key_repo.generate_api_key()
        assert key.startswith("glp_")
        assert len(key) > 8

    async def test_hash_and_verify_api_key(self, db: Any) -> None:
        """Test hash_api_key and verify_api_key work together."""
        api_key_repo = APIKeyRepository(db)
        raw_key = api_key_repo.generate_api_key()
        hashed = api_key_repo.hash_api_key(raw_key)

        assert hashed != raw_key
        assert api_key_repo.verify_api_key(raw_key, hashed) is True
        assert api_key_repo.verify_api_key("glp_wrong_key", hashed) is False

    async def test_verify_and_get_invalid_prefix(self, db: Any) -> None:
        """Test verify_and_get rejects keys without glp_ prefix."""
        api_key_repo = APIKeyRepository(db)
        verified = await api_key_repo.verify_and_get("invalid_prefix_key")
        assert verified is None

    async def test_verify_and_get_expired_key(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test verify_and_get rejects expired API keys."""
        from datetime import datetime, timedelta, timezone

        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(
            username="testuser_expired",
            email="expired@example.com",
            password="test_password_123",
        )

        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id,
            name="Expired Key",
            expires_days=30,
        )

        # Manually expire the key
        api_key_record.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db.flush()

        verified = await api_key_repo.verify_and_get(secret)
        assert verified is None

    async def test_deactivate_api_key_not_found(self, db: Any) -> None:
        """Test deactivating non-existent API key returns False."""
        api_key_repo = APIKeyRepository(db)
        success = await api_key_repo.deactivate_api_key(99999)
        assert success is False

    async def test_delete_api_key_not_found(self, db: Any) -> None:
        """Test deleting non-existent API key returns False."""
        api_key_repo = APIKeyRepository(db)
        success = await api_key_repo.delete_api_key(99999)
        assert success is False

    async def test_create_api_key_no_expiration(self, db: Any, password_hasher: PasswordHasherService) -> None:
        """Test creating an API key without expiration."""
        user_repo = UserRepository(db, password_hasher)
        api_key_repo = APIKeyRepository(db)

        user = await user_repo.create_user(
            username="testuser_no_expiry",
            email="no_expiry@example.com",
            password="test_password_123",
        )

        api_key_record, secret = await api_key_repo.create_api_key(
            user_id=user.id,
            name="No Expiry Key",
        )

        assert api_key_record.expires_at is None
        # Key should still verify successfully
        verified = await api_key_repo.verify_and_get(secret)
        assert verified is not None
