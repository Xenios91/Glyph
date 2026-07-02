# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for binary management pages.

Tests the binary library, binary detail, run task, and task results pages
load correctly and display expected UI elements.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestBinaryLibraryPage:
    """Tests for the binary library page."""

    def test_binary_library_page_loads(self, page: Any, server: Any) -> None:
        """Test that the binary library page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Binary Library")

    def test_binary_library_shows_upload_section(self, page: Any, server: Any) -> None:
        """Test that the binary library page shows the upload section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Check upload section is visible
        expect(page.locator("#upload-box")).to_be_visible()
        expect(page.locator("#upload-title")).to_contain_text("UPLOAD BINARY")

        # Check binary name input exists
        expect(page.locator("#binary-name")).to_be_visible()

        # Check drop zone exists
        expect(page.locator("#drop-zone")).to_be_visible()

        # Check file upload input exists (hidden by design, but present in DOM)
        file_input = page.locator("#upload-binary")
        assert file_input.count() == 1
        expect(file_input).to_have_attribute("type", "file")

    def test_binary_library_shows_binaries_container(self, page: Any, server: Any) -> None:
        """Test that the binary library page shows the binaries container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Check binaries container is visible
        expect(page.locator("#binaries-container")).to_be_visible()
        expect(page.locator("#binaries-title")).to_contain_text("YOUR BINARIES")

    def test_binary_library_shows_empty_state(self, page: Any, server: Any) -> None:
        """Test that the binary library shows empty state when no binaries exist."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Wait for loading to complete
        page.wait_for_selector("#binaries-loading", state="hidden", timeout=10000)

        # Empty state should be visible
        empty_state = page.locator("#binaries-empty")
        expect(empty_state).to_be_visible()
        expect(empty_state).to_contain_text("No binaries uploaded yet")

    def test_binary_library_has_task_modal(self, page: Any, server: Any) -> None:
        """Test that the binary library page has the task selection modal."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Check task modal overlay exists in DOM (initially hidden with display:none)
        modal_overlay = page.locator("#task-modal-overlay")
        assert modal_overlay.count() == 1

        # Check task modal has task options (also hidden until modal is opened)
        assert page.locator('.task-option[data-task-type="dangerous_functions"]').count() == 1
        assert page.locator('.task-option[data-task-type="ml_training"]').count() == 1
        assert page.locator('.task-option[data-task-type="ml_prediction"]').count() == 1

        # Check cancel button exists
        assert page.locator("#task-modal-cancel").count() == 1


class TestRunTaskPage:
    """Tests for the run task page."""

    def test_run_task_page_loads(self, page: Any, server: Any) -> None:
        """Test that the run task page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Run Task")

    def test_run_task_page_shows_task_selection(self, page: Any, server: Any) -> None:
        """Test that the run task page shows task selection UI."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        # Page should load without errors
        expect(page.locator(".page-header")).to_be_visible()


class TestTaskResultsPage:
    """Tests for the task results page."""

    def test_task_results_page_loads(self, page: Any, server: Any) -> None:
        """Test that the task results page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Task Results")
