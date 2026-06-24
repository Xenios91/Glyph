"""SQLAlchemy ORM models for Glyph database abstraction layer."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base(cls=AsyncAttrs)


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
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    model_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    label_encoder_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )


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
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    functions_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("task_name", "model_name", name="uq_predictions_task_model"),
    )


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
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    function_name: Mapped[str] = mapped_column(String(256), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(16), nullable=False)
    tokens: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("model_name", "function_name", name="uq_functions_model_function"),
    )


class Binary(Base):
    """Model representing an uploaded binary in the database.

    Stores metadata about the binary file and links to its raw
    decompiled functions via BinaryFunction.

    Attributes:
        id: Primary key (auto-increment integer)
        name: Human-readable name given by the user at upload time
        file_path: Path to the binary file on disk
        file_size: Size in bytes
        mime_type: Detected MIME type of the binary
        uploaded_by: Foreign key to User.id
        created_at: Timestamp when the binary was uploaded
        modified_at: Timestamp when the binary was last modified
    """

    __tablename__ = "binaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )

    functions: Mapped[list["BinaryFunction"]] = relationship(
        back_populates="binary",
        cascade="save-update, merge, delete, delete-orphan",
    )


class BinaryFunction(Base):
    """Model representing a raw decompiled function from a binary.

    Stores the unmodified C code output from Ghidra. No tokenization,
    filtering, or normalization is applied at storage time — those
    transformations happen only in memory when a task is executed.

    Attributes:
        id: Primary key (auto-increment integer)
        binary_id: Foreign key to Binary.id
        function_name: Name of the function (e.g., "FUN_00401000")
        entrypoint: Memory address/entry point of the function
        raw_code: Raw decompiled C code as text
        created_at: Timestamp when the function was extracted
        modified_at: Timestamp when the function was last modified
    """

    __tablename__ = "binary_functions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    binary_id: Mapped[int] = mapped_column(
        ForeignKey("binaries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    function_name: Mapped[str] = mapped_column(String(256), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )

    binary: Mapped["Binary"] = relationship(back_populates="functions")

    __table_args__ = (
        UniqueConstraint("binary_id", "function_name", name="uq_binary_functions_binary_name"),
    )


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
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=True)
    permissions: Mapped[str] = mapped_column(String(512), default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )
    
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="user",
        cascade="save-update, merge, delete, delete-orphan",
    )


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
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(256), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    permissions: Mapped[str] = mapped_column(String(512), default="[]", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )
    
    user: Mapped["User"] = relationship(back_populates="api_keys")


class SimilarityComputation(Base):
    """Model representing a saved similarity computation task.

    Stores the metadata and results of a pairwise similarity
    computation across a set of binaries.

    Attributes:
        id: Primary key
        task_name: Human-readable name for this computation
        computed_by: User ID who initiated the computation
        binary_count: Number of binaries compared
        total_comparisons: Number of pairwise comparisons made
        status: Computation status (pending, processing, completed, error)
        created_at: Timestamp when the computation was created
        modified_at: Timestamp when the computation was last modified
    """

    __tablename__ = "similarity_computations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    computed_by: Mapped[int] = mapped_column(Integer, nullable=False)
    binary_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_comparisons: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )
    modified_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        onupdate=get_utc_now,
        nullable=False,
    )

    pairs: Mapped[list["SimilarityPair"]] = relationship(
        back_populates="computation",
        cascade="save-update, merge, delete, delete-orphan",
    )


class SimilarityPair(Base):
    """Model representing a single pairwise similarity result.

    Attributes:
        id: Primary key
        computation_id: Foreign key to SimilarityComputation.id
        binary_a_id: First binary in the pair
        binary_b_id: Second binary in the pair
        overall_similarity: Average similarity score across matched functions
        matched_function_count: Number of function pairs above threshold
        total_function_comparisons: Total function pairs compared
        created_at: Timestamp when the comparison was computed
    """

    __tablename__ = "similarity_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computation_id: Mapped[int] = mapped_column(
        ForeignKey("similarity_computations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    binary_a_id: Mapped[int] = mapped_column(Integer, nullable=False)
    binary_b_id: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_function_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_function_comparisons: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        server_default=func.now(),
        nullable=False,
    )

    computation: Mapped["SimilarityComputation"] = relationship(back_populates="pairs")

    __table_args__ = (
        UniqueConstraint("computation_id", "binary_a_id", "binary_b_id",
                        name="uq_similarity_pair_computation_binaries"),
    )
