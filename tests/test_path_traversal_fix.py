"""Security tests for path traversal prevention in binary upload endpoint."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.api.v1.endpoints.binaries import (
    validate_binary_mime_type,
    sanitize_filename,
    ALLOWED_MIME_TYPES
)


class TestValidateBinaryMimeType:
    """Tests for MIME type validation function."""

    def test_valid_elf_binary(self):
        """Test that valid ELF binary is accepted."""
        # ELF magic bytes
        elf_bytes = b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 1000
        # Should not raise
        validate_binary_mime_type(elf_bytes)

    def test_valid_executable_binary(self):
        """Test that valid executable binary is accepted."""
        # PE/EXE magic bytes
        exe_bytes = b'MZ' + b'\x00' * 1000
        # Should not raise (application/octet-stream is allowed)
        validate_binary_mime_type(exe_bytes)

    def test_text_file_rejected(self):
        """Test that text files are rejected."""
        text_bytes = b'Hello, World!\n' + b'\x00' * 1000
        with pytest.raises(HTTPException) as exc_info:
            validate_binary_mime_type(text_bytes)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_html_file_rejected(self):
        """Test that HTML files are rejected."""
        html_bytes = b'<!DOCTYPE html><html>' + b'\x00' * 1000
        with pytest.raises(HTTPException) as exc_info:
            validate_binary_mime_type(html_bytes)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_python_script_rejected(self):
        """Test that Python scripts are rejected."""
        python_bytes = b'#!/usr/bin/env python\nprint("hello")' + b'\x00' * 1000
        with pytest.raises(HTTPException) as exc_info:
            validate_binary_mime_type(python_bytes)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_shell_script_rejected(self):
        """Test that shell scripts are rejected."""
        shell_bytes = b'#!/bin/bash\necho "hello"' + b'\x00' * 1000
        with pytest.raises(HTTPException) as exc_info:
            validate_binary_mime_type(shell_bytes)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail


class TestSanitizeFilename:
    """Tests for filename sanitization function."""

    def test_valid_filename(self):
        """Test that valid filename is returned unchanged (base name only)."""
        result = sanitize_filename("test_binary.elf")
        assert result == "test_binary.elf"

    def test_path_traversal_attempt_slashdotdot(self):
        """Test that path traversal with ../ is blocked."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "Invalid filename characters" in exc_info.value.detail

    def test_path_traversal_attempt_deep(self):
        """Test that deep path traversal is blocked."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("../../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_path_with_directory(self):
        """Test that directory components are stripped."""
        result = sanitize_filename("/tmp/evil_binary.elf")
        # Should only return the base name
        assert result == "evil_binary.elf"
        assert ".." not in result

    def test_null_byte_injection(self):
        """Test that null bytes in filename are blocked."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("binary.elf\x00.txt")
        assert exc_info.value.status_code == 400
        assert "Invalid filename characters" in exc_info.value.detail

    def test_empty_filename(self):
        """Test that empty filename is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("")
        assert exc_info.value.status_code == 400
        assert "Empty filename" in exc_info.value.detail

    def test_unicode_filename(self):
        """Test that unicode filenames are handled."""
        result = sanitize_filename("binary_测试.elf")
        assert result == "binary_测试.elf"

    def test_special_characters(self):
        """Test that special characters are handled."""
        result = sanitize_filename("binary-test_v1.0.elf")
        assert result == "binary-test_v1.0.elf"


class TestPathTraversalIntegration:
    """Integration tests for path traversal prevention."""

    def test_upload_with_path_traversal_filename(self):
        """Test that upload with path traversal filename is rejected."""
        # The sanitize_filename should raise HTTPException for path traversal
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename("../../../etc/passwd")
        
        assert exc_info.value.status_code == 400
        assert "Invalid filename characters" in exc_info.value.detail

    def test_upload_with_valid_binary(self):
        """Test that valid binary upload passes validation."""
        # Valid binary content
        binary_content = b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 1000
        
        # MIME validation should pass
        validate_binary_mime_type(binary_content)
        
        # Filename sanitization should work
        result = sanitize_filename("test_binary.elf")
        assert result == "test_binary.elf"


class TestAllowedMimeTypeSet:
    """Tests for the allowed MIME types configuration."""

    def test_allowed_mime_types_includes_binary_types(self):
        """Test that allowed MIME types include common binary formats."""
        assert 'application/x-executable' in ALLOWED_MIME_TYPES
        assert 'application/octet-stream' in ALLOWED_MIME_TYPES
        assert 'application/x-object' in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_excludes_text_types(self):
        """Test that text-based MIME types are not allowed."""
        assert 'text/plain' not in ALLOWED_MIME_TYPES
        assert 'text/html' not in ALLOWED_MIME_TYPES
        assert 'application/javascript' not in ALLOWED_MIME_TYPES
        assert 'application/x-python' not in ALLOWED_MIME_TYPES

    def test_allowed_mime_types_excludes_script_types(self):
        """Test that script MIME types are not allowed."""
        assert 'application/x-shellscript' not in ALLOWED_MIME_TYPES
        assert 'application/x-sh' not in ALLOWED_MIME_TYPES
