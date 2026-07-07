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

    def test_run_task_shows_binary_info_section(self, page: Any, server: Any) -> None:
        """Test that the run task page shows the binary info section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#binary-info")).to_be_visible()
        expect(page.locator("#binary-name")).to_contain_text("test_binary")
        expect(page.locator("#binary-id-display")).to_contain_text("1")

    def test_run_task_shows_task_name_input(self, page: Any, server: Any) -> None:
        """Test that the run task page shows the task name input."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#task-name")).to_be_visible()
        expect(page.locator("#task-name")).to_have_attribute("type", "text")

    def test_run_task_shows_task_type_selector(self, page: Any, server: Any) -> None:
        """Test that the run task page shows the task type selector."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#task-type")).to_be_visible()

    def test_run_task_task_type_has_options(self, page: Any, server: Any) -> None:
        """Test that the task type selector has the expected options."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        task_type = page.locator("#task-type")
        options = task_type.locator("option")
        option_count = options.count()
        assert option_count >= 2, f"Expected at least 2 task type options, got {option_count}"

    def test_run_task_shows_execute_button(self, page: Any, server: Any) -> None:
        """Test that the run task page shows the execute button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#execute-btn")).to_be_visible()
        expect(page.locator("#execute-btn")).to_contain_text("EXECUTE TASK")

    def test_run_task_shows_dangerous_functions_options(self, page: Any, server: Any) -> None:
        """Test that the run task page has dangerous functions options section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        # Select dangerous_functions task type and call the onchange handler directly
        page.locator("#task-type").select_option("dangerous_functions")
        page.evaluate("() => window.handleTaskTypeChange()")

        # Dangerous functions options should be visible
        expect(page.locator("#dangerous-functions-options")).to_be_visible()

    def test_run_task_shows_ml_training_options(self, page: Any, server: Any) -> None:
        """Test that the run task page has ML training options section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        # Select ml_training task type and call the onchange handler directly
        page.locator("#task-type").select_option("ml_training")
        page.evaluate("() => window.handleTaskTypeChange()")

        # ML training options should be visible
        expect(page.locator("#ml-training-options")).to_be_visible()
        expect(page.locator("#model-name")).to_be_visible()
        expect(page.locator("#ml-class-type")).to_be_visible()

    def test_run_task_has_error_container(self, page: Any, server: Any) -> None:
        """Test that the run task page has an error message container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        error_container = page.locator("#task-error")
        assert error_container.count() == 1

    def test_run_task_has_task_status_container(self, page: Any, server: Any) -> None:
        """Test that the run task page has a task status container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test_binary")
        page.wait_for_load_state("networkidle")

        status_container = page.locator("#task-status")
        assert status_container.count() == 1


class TestTaskResultsPage:
    """Tests for the task results page."""

    def test_task_results_page_loads(self, page: Any, server: Any) -> None:
        """Test that the task results page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Task Results")

    def test_task_results_shows_page_header(self, page: Any, server: Any) -> None:
        """Test that the task results page shows the page header."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".page-header")).to_be_visible()
        expect(page.locator(".page-header .title")).to_contain_text("TASK RESULTS")

    def test_task_results_shows_loading_state(self, page: Any, server: Any) -> None:
        """Test that the task results page shows a loading state initially."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")

        loading = page.locator("#results-loading")
        assert loading.count() == 1

    def test_task_results_has_summary_section(self, page: Any, server: Any) -> None:
        """Test that the task results page has a summary section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        summary = page.locator("#results-summary")
        assert summary.count() == 1

    def test_task_results_has_comparisons_section(self, page: Any, server: Any) -> None:
        """Test that the task results page has a comparisons section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        comparisons = page.locator("#comparisons-container")
        assert comparisons.count() == 1

    def test_task_results_has_empty_state_container(self, page: Any, server: Any) -> None:
        """Test that the task results page has an empty state container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator("#results-empty")
        assert empty_state.count() == 1

    def test_task_results_has_error_state_container(self, page: Any, server: Any) -> None:
        """Test that the task results page has an error state container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        error_state = page.locator("#results-error")
        assert error_state.count() == 1

    def test_task_results_has_back_to_library_link(self, page: Any, server: Any) -> None:
        """Test that the task results page has a back to library link."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-12345")
        page.wait_for_load_state("networkidle")

        # Scope to main content area to avoid matching the navbar link
        back_link = page.locator('[role="main"] a[href="/binary-library"]')
        assert back_link.count() > 0
        expect(back_link.first).to_contain_text("BACK TO LIBRARY")
