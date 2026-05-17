"""User and API key repository for authentication operations."""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, APIKey
from loguru import logger
class PasswordHasherService:
    """Service for password hashing using Argon2id."""
    
    def __init__(self) -> None:
        """Initialize the password hasher with recommended settings."""
        self.ph = PasswordHasher(
            time_cost=2,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16
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

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.password_hasher = PasswordHasherService()

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        permissions: list[str] | None = None
    ) -> User:
        """Create a new user."""
        hashed_password = self.password_hasher.hash_password(password)
        
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            permissions=str(permissions or [])
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    _DUMMY_HASH = (
        "$argon2id$v=19$m=65536,t=2,p=4"
        "$IaW8lT+iFVnKaCPWA+ArYg"
        "$/rEI6zn8/LYoQNpbGs9wpH/qiB4ggeLb7B9UhCS/gDc"
    )

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
        self,
        user_id: int,
        full_name: str | None = None,
        email: str | None = None,
        is_active: bool | None = None
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
        token = secrets.token_urlsafe(32)
        return f"{self.token_prefix}{token}"

    def hash_api_key(self, api_key: str) -> str:
        return bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))

    async def create_api_key(
        self,
        user_id: int,
        name: str,
        permissions: list[str] | None = None,
        expires_days: int | None = None
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user. Returns (APIKey, plain_text_key)."""
        api_key = self.generate_api_key()
        hashed_key = self.hash_api_key(api_key)
        key_prefix = api_key[:8]

        expires_at = None
        if expires_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        
        api_key_record = APIKey(
            user_id=user_id,
            name=name,
            hashed_key=hashed_key,
            key_prefix=key_prefix,
            permissions=str(permissions or ["read"]),
            expires_at=expires_at
        )
        
        self.db.add(api_key_record)
        await self.db.flush()
        await self.db.refresh(api_key_record)
        return api_key_record, api_key
    
    async def get_by_id(self, key_id: int) -> APIKey | None:
        return await self.db.get(APIKey, key_id)

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        result = await self.db.execute(select(APIKey).where(APIKey.key_prefix == prefix))
        return result.scalar_one_or_none()

    async def verify_and_get(self, api_key: str) -> APIKey | None:
        """Verify an API key and return the record if valid."""
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

        if api_key_record.expires_at and datetime.now(timezone.utc) > api_key_record.expires_at:
            logger.bind(key_id=api_key_record.id).debug("API key verification failed: key expired")
            return None

        api_key_record.last_used_at = datetime.now(timezone.utc)
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
