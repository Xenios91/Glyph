"""User and API key repository for authentication operations."""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User, APIKey


class PasswordHasherService:
    """Service for password hashing using Argon2id."""
    
    def __init__(self):
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
    
    def __init__(self, db: AsyncSession):
        """Initialize the user repository.
        
        Args:
            db: Async database session
        """
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
        """Create a new user.
        
        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            full_name: Optional full name
            permissions: Optional list of permissions
            
        Returns:
            Created User instance
        """
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
        """Get a user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User instance or None
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> User | None:
        """Get a user by username.
        
        Args:
            username: Username
            
        Returns:
            User instance or None
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email.
        
        Args:
            email: Email address
            
        Returns:
            User instance or None
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    async def verify_credentials(self, username: str, password: str) -> User | None:
        """Verify user credentials.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User instance if credentials are valid, None otherwise
        """
        user = await self.get_by_username(username)
        if user and self.password_hasher.verify_password(password, user.hashed_password):
            return user
        return None
    
    async def update_user(
        self,
        user_id: int,
        full_name: str | None = None,
        email: str | None = None,
        is_active: bool | None = None
    ) -> User | None:
        """Update a user's information.
        
        Args:
            user_id: User ID
            full_name: Optional new full name
            email: Optional new email
            is_active: Optional new active status
            
        Returns:
            Updated User instance or None
        """
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
        """Change a user's password.
        
        Args:
            user_id: User ID
            new_password: New plain text password
            
        Returns:
            True if password was changed successfully
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        user.hashed_password = self.password_hasher.hash_password(new_password)
        await self.db.flush()
        return True
    
    async def delete_user(self, user_id: int) -> bool:
        """Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if user was deleted
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        await self.db.delete(user)
        await self.db.flush()
        return True


class APIKeyRepository:
    """Repository for API key operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize the API key repository.
        
        Args:
            db: Async database session
        """
        self.db = db
        self.token_prefix = "glp_"
    
    def generate_api_key(self) -> str:
        """Generate a new API key.
        
        Returns:
            New API key string
        """
        # Generate a random token
        token = secrets.token_urlsafe(32)
        return f"{self.token_prefix}{token}"
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key using bcrypt.
        
        Args:
            api_key: Plain text API key
            
        Returns:
            Hashed API key
        """
        return bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash.
        
        Args:
            api_key: Plain text API key
            hashed_key: Hashed API key
            
        Returns:
            True if API key matches
        """
        return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))
    
    async def create_api_key(
        self,
        user_id: int,
        name: str,
        permissions: list[str] | None = None,
        expires_days: int | None = None
    ) -> tuple[APIKey, str]:
        """Create a new API key for a user.
        
        Args:
            user_id: User ID
            name: Human-readable name for the key
            permissions: Optional list of permissions
            expires_days: Optional expiration in days
            
        Returns:
            Tuple of (APIKey instance, plain text key - only shown once)
        """
        # Generate the API key
        api_key = self.generate_api_key()
        hashed_key = self.hash_api_key(api_key)
        key_prefix = api_key[:8]
        
        # Calculate expiration
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
        """Get an API key by ID.
        
        Args:
            key_id: API key ID
            
        Returns:
            APIKey instance or None
        """
        result = await self.db.execute(select(APIKey).where(APIKey.id == key_id))
        return result.scalar_one_or_none()
    
    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        """Get an API key by its prefix.
        
        Args:
            prefix: First 8 characters of the key
            
        Returns:
            APIKey instance or None
        """
        result = await self.db.execute(select(APIKey).where(APIKey.key_prefix == prefix))
        return result.scalar_one_or_none()
    
    async def verify_and_get(self, api_key: str) -> APIKey | None:
        """Verify an API key and return the record if valid.
        
        Args:
            api_key: Plain text API key
            
        Returns:
            APIKey instance if valid, None otherwise
        """
        # Get the prefix
        if not api_key.startswith(self.token_prefix):
            return None
        
        prefix = api_key[:8]
        api_key_record = await self.get_by_prefix(prefix)
        
        if not api_key_record:
            return None
        
        # Verify the key
        if not self.verify_api_key(api_key, api_key_record.hashed_key):
            return None
        
        # Check if active
        if not api_key_record.is_active:
            return None
        
        # Check expiration
        if api_key_record.expires_at and datetime.now(timezone.utc) > api_key_record.expires_at:
            return None
        
        # Update last used timestamp
        api_key_record.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()
        
        return api_key_record
    
    async def get_user_api_keys(self, user_id: int) -> list[APIKey]:
        """Get all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of APIKey instances
        """
        result = await self.db.execute(
            select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def deactivate_api_key(self, key_id: int) -> bool:
        """Deactivate an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            True if key was deactivated
        """
        api_key_record = await self.get_by_id(key_id)
        if not api_key_record:
            return False
        
        api_key_record.is_active = False
        await self.db.flush()
        return True
    
    async def delete_api_key(self, key_id: int) -> bool:
        """Delete an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            True if key was deleted
        """
        api_key_record = await self.get_by_id(key_id)
        if not api_key_record:
            return False
        
        await self.db.delete(api_key_record)
        await self.db.flush()
        return True
