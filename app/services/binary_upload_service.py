"""Binary upload service for Glyph application.

Handles file validation, storage, and binary metadata operations.
"""

import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any

import magic
from loguru import logger

from app.config.settings import get_settings
from app.database.binary_repository import BinaryRepository
from app.exceptions import BinaryAccessError, BinaryNotFoundError, ValidationError
from app.processing.pipeline import PipelineContext
from app.processing.pipeline_configs import UPLOAD_PIPELINE

ALLOWED_MIME_TYPES: set[str] = {
    "application/x-executable",
    "application/x-object",
    "application/octet-stream",
    "application/x-elf",
    "application/x-dosexec",
    "application/x-sharedlib",
}


class BinaryUploadService:
    """Service for binary upload, validation, and management.

    Encapsulates business logic for uploading binaries, validating file
    content, storing files to disk, and managing binary metadata.
    """

    @staticmethod
    def validate_mime_type(file_content: bytes) -> str:
        """Validate uploaded file content is a recognized binary format.

        Args:
            file_content: Raw bytes from the uploaded file.

        Returns:
            The detected MIME type string.

        Raises:
            ValidationError: If MIME type cannot be detected or is not allowed.
        """
        try:
            mime_type = magic.from_buffer(file_content[:1024], mime=True)
        except Exception:
            logger.exception("Failed to detect MIME type")
            raise ValidationError("Failed to analyze file type")

        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"File type '{mime_type}' not allowed. Expected binary/ELF format")
        return mime_type

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize and validate the uploaded filename.

        Prevents path traversal and null byte injection attacks.

        Args:
            filename: Raw filename from the upload.

        Returns:
            Sanitized filename (basename only).

        Raises:
            ValidationError: If filename is empty or contains invalid characters.
        """
        if not filename:
            raise ValidationError("Empty filename")
        if ".." in filename:
            raise ValidationError("Invalid filename characters")
        if "\x00" in filename:
            raise ValidationError("Invalid filename characters")
        return Path(filename).name

    @staticmethod
    def validate_file_size(file_size: int) -> None:
        """Validate file size against configured maximum.

        Args:
            file_size: Size of the file in bytes.

        Raises:
            ValidationError: If file exceeds maximum allowed size.
        """
        settings = get_settings()
        max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_file_size_bytes:
            actual_size_mb = file_size / (1024 * 1024)
            raise ValidationError(
                f"File size ({actual_size_mb:.2f}MB) exceeds maximum allowed ({settings.max_file_size_mb}MB)"
            )

    @staticmethod
    def check_disk_space(file_size: int, upload_folder: str) -> None:
        """Check if there is sufficient disk space for the upload.

        Args:
            file_size: Size of the file in bytes.
            upload_folder: Path to the upload directory.

        Raises:
            ValidationError: If insufficient disk space.
        """
        disk_usage = shutil.disk_usage(upload_folder)
        if disk_usage.free < file_size * 1.1:
            raise ValidationError("Insufficient disk space to complete upload")

    @staticmethod
    def generate_filename() -> str:
        """Generate a unique filename for storage.

        Returns:
            A UUID-based filename string.
        """
        return str(uuid.uuid4())

    @staticmethod
    async def store_file(file_path: str, file_stream: Any, max_size: int) -> int:
        """Write file to disk with progressive size checking.

        Args:
            file_path: Target path on disk.
            file_stream: The upload file stream to read from.
            max_size: Maximum allowed file size in bytes.

        Returns:
            The actual file size in bytes.

        Raises:
            ValidationError: If file exceeds maximum size.
            OSError: If write fails.
        """
        chunk_size = 1024 * 1024  # 1MB chunks
        file_size = 0

        with open(file_path, "wb") as f:
            while True:
                chunk = await file_stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                file_size += len(chunk)
                if file_size > max_size:
                    raise ValidationError(f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum allowed")
        return file_size

    @staticmethod
    async def cleanup_file(file_path: str) -> None:
        """Remove a file from disk if it exists.

        Args:
            file_path: Path to the file to remove.
        """
        if os.path.exists(file_path):
            os.remove(file_path)

    async def upload_binary(
        self,
        file_stream: Any,
        name: str,
        user_id: int,
        filename: str,
    ) -> tuple[int, str]:
        """Complete binary upload workflow.

        1. Validate filename
        2. Generate unique storage path
        3. Store file to disk with size checking
        4. Validate MIME type
        5. Save metadata to database

        Args:
            file_stream: The upload file stream.
            name: Human-readable name for the binary.
            user_id: ID of the uploading user.
            filename: Original filename (for validation only).

        Returns:
            Tuple of (binary_id, file_path).

        Raises:
            ValidationError: If validation fails.
        """
        settings = get_settings()
        max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

        # Validate filename
        self.sanitize_filename(filename)

        # Prepare storage path
        unique_filename = self.generate_filename()
        upload_folder = settings.upload_folder
        os.makedirs(upload_folder, exist_ok=True)
        os.chmod(upload_folder, stat.S_IRWXU)
        file_path = os.path.join(upload_folder, unique_filename)

        # Store file
        file_size = await self.store_file(file_path, file_stream, max_file_size_bytes)

        # Validate MIME type
        with open(file_path, "rb") as f:
            header = f.read(1024)

        mime_type = magic.from_buffer(header, mime=True)

        # Override MIME type for .bin files
        if filename.lower().endswith(".bin"):
            mime_type = "application/x-sharedlib"

        if mime_type not in ALLOWED_MIME_TYPES:
            await self.cleanup_file(file_path)
            raise ValidationError(f"File type '{mime_type}' not allowed. Expected binary/ELF format")

        # Set file permissions
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

        # Check disk space (after file is written)
        self.check_disk_space(file_size, str(upload_folder))

        # Save metadata
        binary_id = await BinaryRepository.save_binary(
            name=name,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=user_id,
        )

        logger.info(
            "Binary '{}' uploaded: id={}, path={}, size={} bytes",
            name,
            binary_id,
            file_path,
            file_size,
        )
        return binary_id, file_path

    async def delete_binary(self, binary_id: int, user_id: int) -> None:
        """Delete binary with ownership validation and file cleanup.

        Args:
            binary_id: The binary to delete.
            user_id: The requesting user's ID.

        Raises:
            BinaryNotFoundError: If binary doesn't exist.
            BinaryAccessError: If user doesn't own the binary.
        """
        binary = await BinaryRepository.get(binary_id)
        if binary is None:
            raise BinaryNotFoundError(binary_id)
        if binary.uploaded_by != user_id:
            raise BinaryAccessError(binary_id, user_id)

        # Clean up file from disk
        await self.cleanup_file(binary.file_path)

        # Delete from database
        await BinaryRepository.delete(binary_id)
        logger.info("Binary {} deleted by user {}", binary_id, user_id)

    async def get_binary(self, binary_id: int, user_id: int) -> Any:
        """Retrieve binary with ownership check.

        Args:
            binary_id: The binary to retrieve.
            user_id: The requesting user's ID.

        Returns:
            The Binary ORM object.

        Raises:
            BinaryNotFoundError: If binary doesn't exist.
            BinaryAccessError: If user doesn't own the binary.
        """
        binary = await BinaryRepository.get(binary_id)
        if binary is None:
            raise BinaryNotFoundError(binary_id)
        if binary.uploaded_by != user_id:
            raise BinaryAccessError(binary_id, user_id)
        return binary

    async def list_binaries(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Any], int]:
        """List user's binaries with pagination.

        Args:
            user_id: The user whose binaries to list.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (binaries list, total count).
        """
        total = await BinaryRepository.count_by_user(user_id)
        binaries = await BinaryRepository.get_by_user(user_id, offset=offset, limit=limit)
        return binaries, total

    async def get_functions(self, binary_id: int, offset: int = 0, limit: int | None = None) -> list[Any]:
        """Get decompiled functions for a binary.

        Args:
            binary_id: The binary to retrieve functions for.
            offset: Number of rows to skip.
            limit: Maximum number of rows to return.

        Returns:
            List of BinaryFunction objects.
        """
        return await BinaryRepository.get_functions(binary_id, offset=offset, limit=limit)

    async def get_function_count(self, binary_id: int) -> int:
        """Get function count for a binary.

        Args:
            binary_id: The binary to count functions for.

        Returns:
            Total count of functions.
        """
        return await BinaryRepository.count_functions(binary_id)

    async def run_upload_pipeline(
        self,
        binary_id: int,
        file_path: str,
        task_uuid: str,
    ) -> PipelineContext:
        """Execute the upload pipeline: decompile and save raw functions.

        Args:
            binary_id: Database id of the uploaded binary.
            file_path: Path to the binary file on disk.
            task_uuid: Task UUID for progress tracking.

        Returns:
            The pipeline result context.
        """
        context = PipelineContext(
            uuid=task_uuid,
            binary_path=file_path,
            pipeline_type="binary_upload",
            metadata={"binary_id": binary_id},
        )
        context.set("binary_id", binary_id)
        result = await UPLOAD_PIPELINE.execute(context)
        return result
