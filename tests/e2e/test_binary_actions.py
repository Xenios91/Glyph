# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the wired binary action journeys (S4: R2, R3, R4).

Covers the newly-wired "what can I do with this binary?" surface:
- binary detail FUNCTIONS tab rows navigate to /getFunction (R3)
- binary detail action row deep-links with the binary pre-filled (R3/R4)
- run-task execute -> completed -> redirect to /task-results (R2)
- task-results renders dangerous-functions results and API error paths (R2)
- task-results code-reuse matches open an in-page code-diff modal (R12)
- library task modal options deep-link from the canonical BinaryActions list (R4)
- similarity dashboard preselects the binary from ?binary_id= (R4)

Test users have no binaries in the clean temp database, so the relevant
API endpoints are mocked via page.route with the exact SuccessResponse
envelopes the real endpoints return.
"""

import json
import re
import urllib.parse
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


def _fulfill_json(route: Any, payload: dict, status: int = 200) -> None:
    """Fulfill a Playwright route with a JSON body."""
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


def _mock_binary_detail(page: Any) -> None:
    """Mock GET /api/v1/binaries/binaries/1 (binary detail envelope)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "id": 1,
                    "name": "mock_binary_001",
                    "file_size": 1024,
                    "mime_type": "application/x-executable",
                    "function_count": 2,
                    "created_at": "2026-01-01T00:00:00",
                },
                "message": "ok",
            },
        )

    page.route("**/api/v1/binaries/binaries/1*", handler)


def _mock_binary_functions(page: Any) -> None:
    """Mock GET /api/v1/binaries/functions/1 (paginated function list)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "items": [
                        {"function_name": "main", "entrypoint": "401000"},
                        {"function_name": "helper", "entrypoint": "402000"},
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 10,
                    "total_pages": 1,
                },
                "message": "ok",
            },
        )

    page.route("**/api/v1/binaries/functions/1*", handler)


def _mock_binary_list(page: Any) -> None:
    """Mock GET /api/v1/binaries/list (paginated binary list)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "items": [
                        {
                            "id": 7,
                            "name": "modal_test.bin",
                            "file_size": 1024,
                            "mime_type": "application/x-executable",
                            "function_count": 3,
                            "created_at": "2026-01-01T00:00:00",
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "page_size": 50,
                    "total_pages": 1,
                },
                "message": "ok",
            },
        )

    page.route("**/api/v1/binaries/list*", handler)


def _mock_task_execute(page: Any) -> None:
    """Mock POST /api/v1/tasks/execute (task accepted with a fixed uuid)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "task_uuid": "test-uuid-123",
                    "task_type": "dangerous_functions",
                    "binary_id": 1,
                    "status": "starting",
                },
                "message": "Task started",
            },
        )

    page.route("**/api/v1/tasks/execute", handler)


def _mock_task_status(page: Any) -> None:
    """Mock GET /api/v1/tasks/test-uuid-123/status (immediately completed)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {"status": "completed"},
                "message": "ok",
            },
        )

    page.route("**/api/v1/tasks/test-uuid-123/status", handler)


def _mock_task_results(page: Any) -> None:
    """Mock GET /api/v1/tasks/test-uuid-123/results (dangerous-functions scan)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "result": {
                        "total_found": 2,
                        "total_functions_scanned": 50,
                        "critical_count": 1,
                        "high_count": 1,
                        "medium_count": 0,
                        "low_count": 0,
                        "binary_name": "mock_binary_001",
                        "results": [
                            {
                                "function_name": "strcpy",
                                "severity": "critical",
                                "category": "Memory Corruption",
                                "cwe": "CWE-120",
                                "containing_function": "main",
                                "entrypoint": "0x401000",
                                "description": "Unbounded string copy",
                                "safe_alternative": "strncpy",
                                "usage_context": ["strcpy(buf, input);"],
                            },
                            {
                                "function_name": "gets",
                                "severity": "high",
                                "category": "Memory Corruption",
                                "cwe": "CWE-242",
                                "containing_function": "helper",
                                "entrypoint": "0x402000",
                                "description": "Unbuffered line read",
                                "safe_alternative": "fgets",
                                "usage_context": ["gets(buf);"],
                            },
                        ],
                    },
                    "status": "completed",
                },
                "message": "ok",
            },
        )

    page.route("**/api/v1/tasks/test-uuid-123/results", handler)


def _mock_code_reuse_results(page: Any) -> None:
    """Mock GET /api/v1/tasks/test-uuid-123/results (code-reuse detection)."""

    def handler(route: Any) -> None:
        _fulfill_json(
            route,
            {
                "success": True,
                "data": {
                    "result": {
                        "source_binary_name": "mock_source.bin",
                        "comparisons": [
                            {
                                "target_binary_name": "mock_target.bin",
                                "overall_similarity": 0.83,
                                "matched_functions": [
                                    {
                                        "source_function_name": "main",
                                        "target_function_name": "main_copy",
                                        "similarity_score": 0.83,
                                        "source_tokens": "int main() {\n    int x = 1;\n    return x;\n}",
                                        "target_tokens": "int main() {\n    int x = 1;\n    int y = 2;\n    return x;\n}",
                                    },
                                ],
                            },
                        ],
                    },
                    "status": "completed",
                },
                "message": "ok",
            },
        )

    page.route("**/api/v1/tasks/test-uuid-123/results", handler)


class TestBinaryDetailActions:
    """R3: the binary detail page is actionable."""

    def test_function_row_navigates_to_get_function(self, page: Any, server: Any) -> None:
        """Clicking a FUNCTIONS tab row opens /getFunction with all params."""
        register_and_login(page)
        _mock_binary_detail(page)
        _mock_binary_functions(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#functions-tbody tr")).to_have_count(2)

        # The functions tab is hidden by default (call_graph.css); activate it
        # so the rows are clickable, then click the first row.
        page.evaluate("() => switchTab('functions')")
        expect(page.locator("#panel-functions")).to_have_class(re.compile("active"))

        page.locator("#functions-tbody tr").first.click()
        page.wait_for_url("**/getFunction*")

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(page.url).query)
        assert query["model_name"] == ["mock_binary_001"]
        assert query["function_name"] == ["main"]
        assert query["binary_id"] == ["1"]

    def test_action_row_deep_links_with_binary(self, page: Any, server: Any) -> None:
        """The action row offers all 6 canonical actions with the binary pre-filled."""
        register_and_login(page)
        _mock_binary_detail(page)
        _mock_binary_functions(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#binary-actions")).to_be_visible()
        expect(page.locator("#binary-actions-list a.task-option")).to_have_count(6)

        expect(page.locator("#binary-actions-list a[data-task-type='dangerous_functions']")).to_have_attribute(
            "href", "/getDangerousFunctions?binary_id=1"
        )
        expect(page.locator("#binary-actions-list a[data-task-type='behavioral_scan']")).to_have_attribute(
            "href", "/getBehavioralScan?binary_id=1"
        )
        expect(page.locator("#binary-actions-list a[data-task-type='ml_training']")).to_have_attribute(
            "href", "/create-model?binary_id=1"
        )
        expect(page.locator("#binary-actions-list a[data-task-type='ml_prediction']")).to_have_attribute(
            "href", "/create-prediction?binary_id=1"
        )
        expect(page.locator("#binary-actions-list a[data-task-type='similarity']")).to_have_attribute(
            "href", "/similarity-dashboard?binary_id=1"
        )
        expect(page.locator("#binary-actions-list a[data-task-type='run_task']")).to_have_attribute(
            "href", "/run-task?binary_id=1&binary_name=mock_binary_001"
        )

        # The RUN TASK action deep-links to the previously-unreachable page
        # with the binary pre-filled.
        page.locator("#binary-actions-list a[data-task-type='run_task']").click()
        page.wait_for_url("**/run-task*")
        expect(page.locator("#binary-name")).to_have_text("mock_binary_001")
        expect(page.locator("#binary-id-display")).to_have_text("1")


class TestRunTaskJourney:
    """R2: the run-task -> task-results journey is wired end to end."""

    def test_execute_redirects_to_task_results(self, page: Any, server: Any) -> None:
        """Executing a task redirects to /task-results once it completes."""
        register_and_login(page)
        _mock_binary_detail(page)
        _mock_task_execute(page)
        _mock_task_status(page)

        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=mock_binary_001")
        page.wait_for_load_state("networkidle")

        # Page loads with the binary pre-filled from the query string.
        expect(page.locator("#binary-name")).to_have_text("mock_binary_001")
        expect(page.locator("#function-count")).to_have_text("2")
        expect(page.locator("#task-type option")).to_have_count(3)
        expect(page.locator("#task-type option[value='ml_prediction']")).to_be_attached()
        expect(page.locator("#task-name")).to_have_value(re.compile(r"^task_"))

        page.locator("#execute-btn").click()
        page.wait_for_url("**/task-results*")

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(page.url).query)
        assert query["task_uuid"] == ["test-uuid-123"]

    def test_task_results_renders_dangerous_functions_results(self, page: Any, server: Any) -> None:
        """Task results render the dangerous-functions summary and scan blocks."""
        register_and_login(page)
        _mock_task_results(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-123")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#results-loading")).not_to_be_visible()
        expect(page.locator("#results-error")).not_to_be_visible()
        expect(page.locator("#results-summary")).to_be_visible()
        expect(page.locator("#result-subtitle")).to_contain_text("mock_binary_001")
        expect(page.locator("#summary-grid")).to_contain_text("Dangerous Functions")
        expect(page.locator("#comparisons-container")).to_be_visible()
        expect(page.locator("#comparisons-list .comparison-block")).to_have_count(2)

    def test_task_results_shows_error_when_api_fails(self, page: Any, server: Any) -> None:
        """A failed results API surfaces the API error message in the error state."""
        register_and_login(page)

        def handler(route: Any) -> None:
            _fulfill_json(route, {"detail": "Task not found"}, status=404)

        page.route("**/api/v1/tasks/missing-uuid-999/results", handler)

        page.goto(f"{BASE_URL}/task-results?task_uuid=missing-uuid-999")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#results-error")).to_be_visible()
        expect(page.locator("#error-message")).to_have_text("Task not found")


class TestCodeDiffModal:
    """R12: code-reuse matches open an in-page code-diff modal (no popup)."""

    def test_view_opens_in_page_diff_modal(self, page: Any, server: Any) -> None:
        """Clicking VIEW on a match row opens the in-page diff modal."""
        register_and_login(page)
        _mock_code_reuse_results(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-123")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#comparisons-list .comparison-block")).to_have_count(1)

        # The match table lives in a collapsed comparison body: expand it first.
        page.locator(".comparison-header").first.click()
        expect(page.locator(".comparison-header").first).to_have_attribute("aria-expanded", "true")

        page.locator(".code-preview-btn").first.click()

        expect(page.locator("#diff-modal-overlay")).to_have_class(re.compile("is-visible"))
        expect(page.locator("#diff-modal-title")).to_have_text("CODE COMPARISON")
        expect(page.locator("#diff-source-lines")).to_contain_text("int main() {")
        expect(page.locator("#diff-target-lines")).to_contain_text("int y = 2;")
        # The line present only in the target is highlighted as an addition.
        expect(page.locator("#diff-target-lines .diff-line.added")).to_contain_text("int y = 2;")

    def test_diff_modal_closes_via_button_and_escape(self, page: Any, server: Any) -> None:
        """The close button and Escape both dismiss the diff modal."""
        register_and_login(page)
        _mock_code_reuse_results(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=test-uuid-123")
        page.wait_for_load_state("networkidle")

        page.locator(".comparison-header").first.click()
        page.locator(".code-preview-btn").first.click()
        expect(page.locator("#diff-modal-overlay")).to_have_class(re.compile("is-visible"))

        page.locator("#diff-modal-close").click()
        expect(page.locator("#diff-modal-overlay")).not_to_have_class(re.compile("is-visible"))

        # Re-open and dismiss with the keyboard.
        page.locator(".code-preview-btn").first.click()
        expect(page.locator("#diff-modal-overlay")).to_have_class(re.compile("is-visible"))
        page.keyboard.press("Escape")
        expect(page.locator("#diff-modal-overlay")).not_to_have_class(re.compile("is-visible"))


class TestLibraryTaskModal:
    """R4: the library task modal derives its options from the canonical list."""

    def test_modal_options_deep_link_from_canonical_list(self, page: Any, server: Any) -> None:
        """The modal offers the 5 non-redundant canonical actions deep-linked to the binary."""
        register_and_login(page)
        _mock_binary_list(page)

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#binaries-tbody tr")).to_have_count(1)

        page.locator(".btn-run-task").click()
        expect(page.locator("#task-modal-overlay")).to_have_class(re.compile("is-visible"))

        # The run_task action is excluded: the modal itself is the run-task
        # flow, so offering RUN TASK again would be redundant.
        expect(page.locator("#task-modal-options a.task-option")).to_have_count(5)
        expect(page.locator("#task-modal-options a[data-task-type='run_task']")).to_have_count(0)
        expect(page.locator("#task-modal-options a[data-task-type='dangerous_functions']")).to_have_attribute(
            "href", "/getDangerousFunctions?binary_id=7"
        )


class TestSimilarityPreselect:
    """R4: the similarity dashboard preselects the binary from ?binary_id=."""

    def test_binary_preselected_from_query(self, page: Any, server: Any) -> None:
        """A SIMILARITY deep link arrives with the binary already checked."""
        register_and_login(page)
        _mock_binary_list(page)

        page.goto(f"{BASE_URL}/similarity-dashboard?binary_id=7")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#binary-7")).to_be_checked()
        expect(page.locator("#selection-count")).to_have_text("1 selected")
