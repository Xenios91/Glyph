"""User and API key repository for authentication operations."""

import json
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import APIKey, User


class PasswordHasherService:
    """Service for password hashing using Argon2id."""

    def __init__(
        self,
        time_cost: int | None = None,
        memory_cost: int | None = None,
        parallelism: int | None = None,
        hash_len: int | None = None,
        salt_len: int | None = None,
    ) -> None:
        """Initialize the password hasher with recommended settings.

        Args:
            time_cost: Number of iterations. Defaults to 3 (OWASP recommended minimum).
            memory_cost: Memory to use in KiB. Defaults to 65536 (64 MiB).
            parallelism: Degree of parallelism. Defaults to 4.
            hash_len: Length of the hash. Defaults to 32.
            salt_len: Length of the salt. Defaults to 16.
        """
        self.ph = PasswordHasher(
            time_cost=time_cost if time_cost is not None else 3,
            memory_cost=memory_cost if memory_cost is not None else 65536,
            parallelism=parallelism if parallelism is not None else 4,
            hash_len=hash_len if hash_len is not None else 32,
            salt_len=salt_len if salt_len is not None else 16,
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id.

        Args:
            password: Plain text password to hash

        Returns:
            Hashed password string
        """
        return self.ph.hash(password)

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to verify against

        Returns:
            True if password matches, False otherwise
        """
        try:
            self.ph.verify(hashed_password, password)
            return True
        except argon2_exceptions.VerifyMismatchError:
            return False
        except argon2_exceptions.InvalidHashError:
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if a password hash needs to be rehashed.

        Args:
            hashed_password: Hashed password to check

        Returns:
            True if the hash needs to be rehashed
        """
        return self.ph.check_needs_rehash(hashed_password)


class UserRepository:
    """Repository for user operations."""

    def __init__(self, db: AsyncSession, password_hasher: PasswordHasherService | None = None) -> None:
        """Initialize UserRepository.

        Args:
            db: Async database session.
            password_hasher: Optional password hasher service. Uses default settings if not provided.
        """
        self.db = db
        self.password_hasher = password_hasher if password_hasher is not None else PasswordHasherService()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        permissions: list[str] | None = None,
    ) -> User:
        """Create a new user."""
        hashed_password = self.password_hasher.hash_password(password)

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            permissions=json.dumps(permissions or []),
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        """Retrieve a user by their ID.

        Args:
            user_id: The user's primary key.

        Returns:
            The User object if found, None otherwise.
        """
        return await self.db.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        """Retrieve a user by their username.

        Args:
            username: The unique username to search for.

        Returns:
            The User object if found, None otherwise.
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address.

        Args:
            email: The unique email address to search for.

        Returns:
            The User object if found, None otherwise.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    _DUMMY_HASH = "$argon2id$v=19$m=32768,t=2,p=2$0/ozftprJUeARua45+SumQ$MnHFU4/Gpierd7U0Trn3JGlYYqbepxa8jibBk8ISAE8"

    async def verify_credentials(self, username: str, password: str) -> User | None:
        """Verify user credentials and rehash if needed."""
        user = await self.get_by_username(username)
        if user is None:
            self.password_hasher.verify_password(password, self._DUMMY_HASH)
            return None
        if self.password_hasher.verify_password(password, user.hashed_password):
            logger.bind(user_id=user.id).debug("Credentials verified")
            if self.password_hasher.needs_rehash(user.hashed_password):
                user.hashed_password = self.password_hasher.hash_password(password)
                await self.db.flush()
                logger.bind(user_id=user.id).info("Password hash rehashed")
            return user
        return None

    async def update_user(
        self, user_id: int, full_name: str | None = None, email: str | None = None, is_active: bool | None = None
    ) -> User | None:
        """Update a user's information."""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        if is_active is not None:
            user.is_active = is_active

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def change_password(self, user_id: int, new_password: str) -> bool:
        """Change a user's password."""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.hashed_password = self.password_hasher.hash_password(new_password)
        await self.db.flush()
        return True

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user."""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        await self.db.delete(user)
        await self.db.flush()
        return True


class APIKeyRepository:
    """Repository for API key operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.token_prefix = "glp_"

    def generate_api_key(self) -> str:
        """Generate a cryptographically secure API key.

        Returns:
            A random API key prefixed with the token prefix (e.g., "glp_").
        """
        token = secrets.token_urlsafe(32)
        return f"{self.token_prefix}{token}"

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key using bcrypt.

        Args:
            api_key: The plain-text API key to hash.

        Returns:
            The bcrypt hash of the API key.
        """
        return bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        """Verify a plain-text API key against its bcrypt hash.

        Args:
            api_key: The plain-text API key to verify.
            hashed_key: The bcrypt hash to compare against.

        Returns:
            True if the key matches, False otherwise.
        """
        return bcrypt.checkpw(api_key.encode("utf-8"), hashed_key.encode("utf-8"))

    async def create_api_key(
        self, user_id: int, name: str, permissions: list[str] | None = None, expires_days: int | None = None
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user. Returns (APIKey, plain_text_key)."""
        api_key = self.generate_api_key()
        hashed_key = self.hash_api_key(api_key)
        key_prefix = api_key[:8]

        expires_at = None
        if expires_days:
            expires_at = datetime.now(UTC) + timedelta(days=expires_days)

        api_key_record = APIKey(
            user_id=user_id,
            name=name,
            hashed_key=hashed_key,
            key_prefix=key_prefix,
            permissions=json.dumps(permissions or ["read"]),
            expires_at=expires_at,
        )

        self.db.add(api_key_record)
        await self.db.flush()
        await self.db.refresh(api_key_record)
        return api_key_record, api_key

    async def get_by_id(self, key_id: int) -> APIKey | None:
        """Retrieve an API key by its ID.

        Args:
            key_id: The API key's primary key.

        Returns:
            The APIKey object if found, None otherwise.
        """
        return await self.db.get(APIKey, key_id)

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        """Retrieve an API key by its prefix.

        Args:
            prefix: The first 8 characters of the API key.

        Returns:
            The APIKey object if found, None otherwise.
        """
        result = await self.db.execute(select(APIKey).where(APIKey.key_prefix == prefix))
        return result.scalar_one_or_none()

    async def verify_and_get(self, api_key: str) -> APIKey | None:
        """Verify an API key and return the record if valid.

        Checks the key prefix, hash match, active status, and expiration.
        Updates the last_used_at timestamp on successful verification.

        Args:
            api_key: The plain-text API key to verify.

        Returns:
            The APIKey object if valid, None otherwise.
        """
        if not api_key.startswith(self.token_prefix):
            logger.debug("API key verification failed: invalid prefix")
            return None

        prefix = api_key[:8]
        api_key_record = await self.get_by_prefix(prefix)

        if not api_key_record:
            logger.debug("API key verification failed: key not found")
            return None

        if not self.verify_api_key(api_key, api_key_record.hashed_key):
            logger.debug("API key verification failed: invalid key")
            return None

        if not api_key_record.is_active:
            logger.bind(key_id=api_key_record.id).debug("API key verification failed: key inactive")
            return None

        if api_key_record.expires_at and datetime.now(UTC) > api_key_record.expires_at:
            logger.bind(key_id=api_key_record.id).debug("API key verification failed: key expired")
            return None

        api_key_record.last_used_at = datetime.now(UTC)
        await self.db.flush()
        logger.bind(key_id=api_key_record.id, user_id=api_key_record.user_id).debug("API key verified")
        return api_key_record

    async def get_user_api_keys(self, user_id: int) -> list[APIKey]:
        result = await self.db.execute(
            select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def deactivate_api_key(self, key_id: int) -> bool:
        """Deactivate an API key."""
        api_key_record = await self.get_by_id(key_id)
        if not api_key_record:
            return False

        api_key_record.is_active = False
        await self.db.flush()
        return True

    async def delete_api_key(self, key_id: int) -> bool:
        """Delete an API key."""
        api_key_record = await self.get_by_id(key_id)
        if not api_key_record:
            return False

        await self.db.delete(api_key_record)
        await self.db.flush()
        return True
