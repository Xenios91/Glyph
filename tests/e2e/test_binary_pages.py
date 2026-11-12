# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for binary management pages.

Tests the binary library, binary detail, run task, and task results pages
load correctly and display expected UI elements.
"""

import json
import urllib.parse
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


def _make_list_response(page: int, page_size: int, total: int = 57) -> dict:
    """Build a /api/v1/binaries/list response envelope for a given page.

    Mirrors the SuccessResponse[PaginatedResponse[BinaryListItem]] shape the
    real endpoint returns, so the page's server-side pagination logic is
    exercised against a deterministic, >50-item dataset.
    """
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    items = [
        {
            "id": i,
            "name": f"mock_binary_{i:03d}",
            "file_size": 1024,
            "mime_type": "application/x-executable",
            "function_count": 0,
            "created_at": "2026-01-01T00:00:00",
        }
        for i in range(start + 1, end + 1)
    ]
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
        "message": "Binaries retrieved successfully",
    }


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

        # Wait for the fetch to finish and the empty state to appear
        empty_state = page.locator("#binaries-empty")
        expect(empty_state).to_be_visible(timeout=10000)
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


def test_binary_library_server_side_pagination(page: Any, server: Any) -> None:
    """R13: The binary library must paginate server-side.

    The list request must carry page/page_size query params, the controls
    (total count, page buttons, page-size selector) must be driven by the
    server-reported total, and page 2 must be reachable when the server has
    more items than the default page size (50).

    The list endpoint is intercepted with a deterministic >50-item dataset so
    the test does not depend on seeding the database.
    """
    register_and_login(page)

    # Start from a clean slate so the client's default page size (50) applies
    # rather than a page size persisted by an earlier test in the session.
    page.evaluate("() => sessionStorage.clear()")

    # Intercept the list endpoint and serve a 57-item dataset, slicing it by
    # the requested page/page_size exactly like the real server does.
    def _serve_list(route: Any) -> None:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
        pg = int(qs.get("page", ["1"])[0])
        ps = int(qs.get("page_size", ["50"])[0])
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_make_list_response(pg, ps)),
        )

    page.route("**/api/v1/binaries/list*", _serve_list)

    page.goto(f"{BASE_URL}/binary-library")
    page.wait_for_load_state("domcontentloaded")

    # Wait for the table + pagination to render from server data.
    expect(page.locator("#binaries-table-wrapper")).to_be_visible()
    expect(page.locator("#binaries-pagination")).to_be_visible()

    # Page 1 shows exactly page_size rows (server slice, not a 50-row client array).
    expect(page.locator("#binaries-tbody tr")).to_have_count(50)

    # Total-count display reflects the server total (57), not the 50 rows fetched.
    page_info = page.locator("#binaries-pagination .pagination-info")
    expect(page_info).to_contain_text("57")

    # 57 items / 50 per page -> 2 pages; the "2" page button must exist and be enabled.
    page2_btn = page.locator("#binaries-pagination .pagination-page-numbers button", has_text="2")
    expect(page2_btn).to_have_count(1)
    expect(page2_btn).to_be_enabled()

    # Navigate to page 2: the request must now carry page=2 and page_size=50.
    with page.expect_response(lambda r: "/api/v1/binaries/list" in r.url) as page2_info:
        page2_btn.click()
    page2_url = page2_info.value.url
    q = urllib.parse.parse_qs(urllib.parse.urlparse(page2_url).query)
    assert q.get("page") == ["2"], f"Expected page=2 in request, got {page2_url}"
    assert q.get("page_size") == ["50"], f"Expected page_size=50 in request, got {page2_url}"

    # Page 2 renders the remaining 7 rows (57 - 50) from the server slice.
    expect(page.locator("#binaries-tbody tr")).to_have_count(7)
    expect(page.locator("#binaries-tbody tr").first).to_contain_text("mock_binary_051")
    expect(page_info).to_contain_text("51–57 of 57")

    # Page-size selector offers options capped at the API max (200), none above it.
    # The Pagination class derives element IDs from the container selector
    # (#binaries-pagination -> _binaries_pagination_<suffix>).
    size_select = page.locator("#binaries-pagination select#_binaries_pagination_page-size")
    expect(size_select).to_be_visible()
    options = [int(o) for o in size_select.locator("option").all_inner_texts()]
    assert max(options) == 200, f"Page-size options must cap at 200, got {options}"
    assert all(o <= 200 for o in options), f"No page-size option may exceed 200, got {options}"

    # Changing the page size re-queries the server with the new page_size, page 1.
    with page.expect_response(lambda r: "/api/v1/binaries/list" in r.url) as size_info:
        size_select.select_option("200")
    size_url = size_info.value.url
    sq = urllib.parse.parse_qs(urllib.parse.urlparse(size_url).query)
    assert sq.get("page_size") == ["200"], f"Expected page_size=200 in request, got {size_url}"
    assert sq.get("page") == ["1"], f"Expected page=1 after page-size change, got {size_url}"


def test_binary_library_shows_skeleton_while_loading(page: Any, server: Any) -> None:
    """R23: while the list fetch is in flight, the binaries table must show
    skeleton placeholder rows (matching the real columns), then swap in the
    real data rows once the fetch resolves."""
    register_and_login(page)

    # Clean slate so the client's default page size (50) applies.
    page.evaluate("() => sessionStorage.clear()")

    # Intercept the list endpoint and serve it instantly. The delay is applied
    # *inside the browser* (see init script below) so the page's event loop
    # stays free to render the skeleton while the fetch is pending. Delaying
    # in the route handler instead would block Playwright's loop and freeze
    # the page, hiding the skeleton state.
    def _serve_list(route: Any) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_make_list_response(1, 50, total=50)),
        )

    page.route("**/api/v1/binaries/list*", _serve_list)

    # Wrap window.fetch so the binaries list request resolves after 1.5s,
    # leaving a window in which the skeleton rows are the only content.
    page.add_init_script(
        """
        (() => {
            const originalFetch = window.fetch;
            window.fetch = function (input, init) {
                const url = typeof input === 'string' ? input : (input && input.url) || '';
                if (url.indexOf('/api/v1/binaries/list') !== -1) {
                    return new Promise((resolve, reject) => {
                        setTimeout(() => originalFetch.call(window, input, init).then(resolve, reject), 1500);
                    });
                }
                return originalFetch.call(window, input, init);
            };
        })();
        """
    )

    page.goto(f"{BASE_URL}/binary-library")
    page.wait_for_load_state("domcontentloaded")

    # Skeleton rows are visible while the fetch is pending.
    expect(page.locator("#binaries-tbody tr.skeleton-row")).to_have_count(5)
    expect(page.locator("#binaries-tbody .skeleton")).to_have_count(25)

    # Once the fetch resolves, the skeleton is replaced by real data rows.
    expect(page.locator("#binaries-tbody tr.skeleton-row")).to_have_count(0)
    expect(page.locator("#binaries-tbody tr")).to_have_count(50)
    expect(page.locator("#binaries-tbody tr").first).to_contain_text("mock_binary_001")


def test_binary_delete_uses_styled_confirm_modal(page: Any, server: Any) -> None:
    """R9/R10: deleting a binary must open the styled confirm modal.

    The list endpoint is mocked with a single binary. Cancelling the modal
    keeps the row and fires no DELETE request; confirming issues the DELETE
    and re-renders the (now empty) list.
    """
    register_and_login(page)

    binary = {
        "id": 42,
        "name": "e2e_delete_target",
        "file_size": 2048,
        "mime_type": "application/x-executable",
        "function_count": 0,
        "created_at": "2026-01-01T00:00:00",
    }
    state = {"deleted": False}
    delete_methods: list[str] = []

    def _serve_list(route: Any) -> None:
        items = [] if state["deleted"] else [binary]
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "success": True,
                    "data": {
                        "items": items,
                        "total": len(items),
                        "page": 1,
                        "page_size": 50,
                        "total_pages": 1 if items else 0,
                    },
                    "message": "Binaries retrieved successfully",
                }
            ),
        )

    def _capture_delete(route: Any) -> None:
        state["deleted"] = True
        delete_methods.append(route.request.method)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {"success": True, "data": None, "message": "Binary deleted successfully"}
            ),
        )

    page.route("**/api/v1/binaries/list*", _serve_list)
    page.route("**/api/v1/binaries/binaries/42", _capture_delete)

    page.goto(f"{BASE_URL}/binary-library")
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator("#binaries-tbody tr")).to_have_count(1)

    native_dialogs: list[str] = []

    def _on_dialog(dialog: Any) -> None:
        native_dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", _on_dialog)

    # Clicking DELETE opens the styled modal naming the binary.
    page.locator(".btn-delete-binary").click()
    overlay = page.locator(".confirm-modal-overlay")
    expect(overlay).to_be_visible()
    expect(page.locator(".confirm-modal-title")).to_contain_text("Delete Binary")
    expect(page.locator(".confirm-modal-message")).to_contain_text("e2e_delete_target")

    # Cancelling keeps the row and fires no DELETE request.
    page.locator(".confirm-modal .cyber-btn", has_text="Cancel").click()
    expect(overlay).to_have_count(0)
    expect(page.locator("#binaries-tbody tr")).to_have_count(1)
    assert delete_methods == []

    # Confirming issues the DELETE and re-renders the empty list.
    page.locator(".btn-delete-binary").click()
    expect(overlay).to_be_visible()
    page.locator(".confirm-modal .cyber-btn", has_text="Delete").click()
    expect(page.locator("#binaries-tbody tr")).to_have_count(0)
    expect(page.locator("#binaries-empty")).to_be_visible()
    assert delete_methods == ["DELETE"]
    assert not native_dialogs, f"Native dialog opened: {native_dialogs}"
