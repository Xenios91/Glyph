"""SQLAlchemy ORM models for Glyph database abstraction layer."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, BLOB, DateTime, String, Text
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

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
