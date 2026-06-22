"""Reusable test data factories for Glyph test suite.

Centralizes mock object and model instance creation to eliminate
duplicated inline test data across test files.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

from app.database.models import (
    Binary,
    BinaryFunction,
    Function,
    Model,
    Prediction,
    User,
)


def make_user(
    user_id: int = 1,
    username: str = "testuser",
    email: str = "test@example.com",
    hashed_password: str = "hashed_password",
    full_name: str | None = "Test User",
    permissions: str = "[]",
    is_active: bool = True,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> User:
    """Create a User model instance for testing.

    Args:
        user_id: Primary key.
        username: Unique username.
        email: Unique email address.
        hashed_password: Argon2id hashed password string.
        full_name: Optional full name.
        permissions: JSON array of permissions as string.
        is_active: Whether the account is active.
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A User instance ready for test assertions or DB inserts.
    """
    now = datetime.now(timezone.utc)
    return User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        permissions=permissions,
        is_active=is_active,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


def make_model(
    model_id: int = 1,
    model_name: str = "test_model",
    model_data: bytes = b"fake_model_bytes",
    label_encoder_data: bytes = b"fake_encoder_bytes",
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Model:
    """Create a Model instance for testing.

    Args:
        model_id: Primary key.
        model_name: Unique model name.
        model_data: Serialized model bytes (placeholder).
        label_encoder_data: Serialized label encoder bytes (placeholder).
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A Model instance.
    """
    now = datetime.now(timezone.utc)
    return Model(
        id=model_id,
        model_name=model_name,
        model_data=model_data,
        label_encoder_data=label_encoder_data,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


def make_prediction(
    prediction_id: int = 1,
    task_name: str = "test_prediction",
    model_name: str = "test_model",
    functions_data: bytes = b"fake_functions_bytes",
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Prediction:
    """Create a Prediction instance for testing.

    Args:
        prediction_id: Primary key.
        task_name: Name of the prediction task.
        model_name: Name of the model used.
        functions_data: Serialized function predictions (placeholder).
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A Prediction instance.
    """
    now = datetime.now(timezone.utc)
    return Prediction(
        id=prediction_id,
        task_name=task_name,
        model_name=model_name,
        functions_data=functions_data,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


def make_function(
    func_id: int = 1,
    model_name: str = "test_model",
    function_name: str = "FUN_00401000",
    entrypoint: str = "00401000",
    tokens: str = "void func ( void ) { return ; }",
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Function:
    """Create a Function instance for testing.

    Args:
        func_id: Primary key.
        model_name: Associated model name.
        function_name: Function identifier.
        entrypoint: Memory address.
        tokens: Tokenized function code.
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A Function instance.
    """
    now = datetime.now(timezone.utc)
    return Function(
        id=func_id,
        model_name=model_name,
        function_name=function_name,
        entrypoint=entrypoint,
        tokens=tokens,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


def make_binary(
    binary_id: int = 1,
    name: str = "test.elf",
    file_path: str = "/uploads/test.elf",
    file_size: int = 4096,
    mime_type: str = "application/x-executable",
    uploaded_by: int = 1,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Binary:
    """Create a Binary instance for testing.

    Args:
        binary_id: Primary key.
        name: Human-readable binary name.
        file_path: Disk path to the binary.
        file_size: Size in bytes.
        mime_type: Detected MIME type.
        uploaded_by: Foreign key to User.id.
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A Binary instance.
    """
    now = datetime.now(timezone.utc)
    return Binary(
        id=binary_id,
        name=name,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        uploaded_by=uploaded_by,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


def make_binary_function(
    func_id: int = 1,
    binary_id: int = 1,
    function_name: str = "FUN_00401000",
    entrypoint: str = "00401000",
    raw_code: str = "void FUN_00401000(void) {}",
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> BinaryFunction:
    """Create a BinaryFunction instance for testing.

    Args:
        func_id: Primary key.
        binary_id: Foreign key to Binary.id.
        function_name: Function identifier.
        entrypoint: Memory address.
        raw_code: Raw decompiled C code.
        created_at: Explicit creation timestamp.
        modified_at: Explicit modification timestamp.

    Returns:
        A BinaryFunction instance.
    """
    now = datetime.now(timezone.utc)
    return BinaryFunction(
        id=func_id,
        binary_id=binary_id,
        function_name=function_name,
        entrypoint=entrypoint,
        raw_code=raw_code,
        created_at=created_at or now,
        modified_at=modified_at or now,
    )


# ---------------------------------------------------------------------------
# Mock object factories (for dependency overrides)
# ---------------------------------------------------------------------------


def make_mock_user(
    user_id: int = 1,
    username: str = "testuser",
    email: str = "test@example.com",
    is_active: bool = True,
) -> Mock:
    """Create a Mock user for FastAPI dependency overrides.

    This is a lightweight alternative to ``make_user`` when tests only
    need a few user attributes and don't require a full ORM instance.

    Args:
        user_id: User primary key.
        username: Username string.
        email: Email address.
        is_active: Account active flag.

    Returns:
        A Mock with user attributes pre-configured.
    """
    mock = Mock()
    mock.id = user_id
    mock.username = username
    mock.email = email
    mock.is_active = is_active
    return mock


def make_mock_binary(
    binary_id: int = 1,
    name: str = "test.elf",
    file_path: str = "/uploads/test.elf",
    file_size: int = 4096,
    mime_type: str = "application/x-executable",
    uploaded_by: int = 1,
) -> Mock:
    """Create a Mock binary for dependency overrides.

    Args:
        binary_id: Binary primary key.
        name: Binary display name.
        file_path: Disk path.
        file_size: Size in bytes.
        mime_type: MIME type string.
        uploaded_by: Owner user ID.

    Returns:
        A Mock with binary attributes pre-configured.
    """
    mock = Mock()
    mock.id = binary_id
    mock.name = name
    mock.file_path = file_path
    mock.file_size = file_size
    mock.mime_type = mime_type
    mock.uploaded_by = uploaded_by
    return mock


def make_mock_task_result(
    task_uuid: str = "test-uuid-0000",
    status: str = "completed",
    result: dict | None = None,
) -> Mock:
    """Create a Mock task result for testing task endpoints.

    Args:
        task_uuid: Task identifier.
        status: Task status string.
        result: Optional result payload.

    Returns:
        A Mock with task result attributes.
    """
    mock = Mock()
    mock.task_uuid = task_uuid
    mock.status = status
    mock.result = result or {}
    return mock
