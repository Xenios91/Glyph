"""SQLAlchemy ORM models for Glyph database abstraction layer."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, BLOB, DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


def get_utc_now() -> datetime:
    """Get the current UTC time.
    
    Returns:
        Current UTC datetime with timezone info.
    """
    return datetime.now(timezone.utc)


class Model(Base):
    """Model representing a trained ML model in the database.
    
    Attributes:
        id: Primary key
        model_name: Unique name identifier for the model
        model_data: Serialized model bytes (joblib format)
        label_encoder_data: Serialized label encoder bytes (joblib format)
        created_at: Timestamp when the model was created
        modified_at: Timestamp when the model was last modified
    """
    
    __tablename__ = "models"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_data: Mapped[bytes] = mapped_column(BLOB, nullable=False)
    label_encoder_data: Mapped[bytes] = mapped_column(BLOB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)


class Prediction(Base):
    """Model representing a prediction task in the database.
    
    Attributes:
        id: Primary key
        task_name: Name of the prediction task
        model_name: Name of the model used for prediction
        functions_data: Serialized list of function predictions (joblib format)
        created_at: Timestamp when the prediction was created
        modified_at: Timestamp when the prediction was last modified
    """
    
    __tablename__ = "predictions"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    functions_data: Mapped[bytes] = mapped_column(BLOB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)


class Function(Base):
    """Model representing a function extracted from a binary.
    
    Attributes:
        id: Primary key
        model_name: Name of the model this function belongs to
        function_name: Name of the function
        entrypoint: Memory address/entry point of the function
        tokens: Tokenized function code as text
        created_at: Timestamp when the function was created
        modified_at: Timestamp when the function was last modified
    """
    
    __tablename__ = "functions"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    function_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    entrypoint: Mapped[str] = mapped_column(String(16), nullable=False)
    tokens: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)


class User(Base):
    """Model representing a user in the database.
    
    Attributes:
        id: Primary key
        username: Unique username
        email: Unique email address
        hashed_password: Argon2id hashed password
        full_name: User's full name
        permissions: JSON array of permissions
        is_active: Whether the user account is active
        created_at: Timestamp when the user was created
        modified_at: Timestamp when the user was last modified
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=True)
    permissions: Mapped[str] = mapped_column(String(512), default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)
    
    # Relationship to API keys
    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class APIKey(Base):
    """Model representing an API key for programmatic access.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to User
        name: Human-readable name for the API key
        hashed_key: Bcrypt hashed API key
        key_prefix: First 8 characters of the key for display
        permissions: JSON array of permissions
        expires_at: Optional expiration timestamp
        is_active: Whether the API key is active
        last_used_at: Timestamp when the key was last used
        created_at: Timestamp when the key was created
    """
    
    __tablename__ = "api_keys"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(256), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    permissions: Mapped[str] = mapped_column(String(512), default="[]", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False)
    
    # Relationship to user
    user: Mapped["User"] = relationship(back_populates="api_keys")
