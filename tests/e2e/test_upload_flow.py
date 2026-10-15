# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for file upload flow.

Tests the file upload functionality on the binary library page, including
form validation, error handling, and UI feedback.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestUploadFormValidation:
    """Tests for upload form validation."""

    def test_upload_requires_binary_name(self, page: Any, server: Any) -> None:
        """Test that the upload form requires a binary name."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Binary name input should be present and required
        binary_name_input = page.locator("#binary-name")
        expect(binary_name_input).to_be_visible()
        expect(binary_name_input).to_have_attribute("aria-required", "true")

    def test_upload_drop_zone_is_visible(self, page: Any, server: Any) -> None:
        """Test that the upload drop zone is visible and interactive."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Drop zone should be visible
        drop_zone = page.locator("#drop-zone")
        expect(drop_zone).to_be_visible()
        expect(drop_zone).to_have_attribute("role", "button")
        expect(drop_zone).to_have_attribute("tabindex", "0")

    def test_upload_file_input_exists(self, page: Any, server: Any) -> None:
        """Test that the file upload input exists and is functional."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # File input should exist (hidden by CSS, but present in DOM)
        file_input = page.locator("#upload-binary")
        assert file_input.count() == 1
        expect(file_input).to_have_attribute("type", "file")

    def test_upload_progress_is_hidden_initially(self, page: Any, server: Any) -> None:
        """Test that the upload progress indicator is hidden before upload."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Progress indicator should be hidden
        progress = page.locator("#upload-progress")
        is_visible = progress.is_visible()
        assert not is_visible, "Upload progress should be hidden initially"

    def test_upload_error_is_hidden_initially(self, page: Any, server: Any) -> None:
        """Test that the upload error message is hidden before any errors."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Error message should be hidden
        error = page.locator("#upload-error")
        is_visible = error.is_visible()
        assert not is_visible, "Upload error should be hidden initially"

    def test_upload_shows_hint_text(self, page: Any, server: Any) -> None:
        """Test that the binary name field shows hint text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Hint text should be visible
        hint = page.locator("#binary-name-hint")
        expect(hint).to_be_visible()
        expect(hint).to_contain_text("unique identifier")


class TestUploadInteraction:
    """Tests for upload interaction behavior."""

    def test_select_file_label_is_clickable(self, page: Any, server: Any) -> None:
        """Test that the select file label is clickable."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # File upload label should be visible
        file_label = page.locator("#file-upload-label")
        expect(file_label).to_be_visible()
        expect(file_label).to_contain_text("SELECT FILE")

    def test_drop_zone_has_accessible_label(self, page: Any, server: Any) -> None:
        """Test that the drop zone has an accessible label."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        drop_zone = page.locator("#drop-zone")
        aria_label = drop_zone.get_attribute("aria-label")
        assert aria_label is not None
        assert "drag" in aria_label.lower() or "drop" in aria_label.lower()
