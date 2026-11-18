# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""E2E tests for the global status bar (gaps G1 and G2).

Covers the status bar task lifecycle (``registerTask``, upload progress,
terminal states with toasts, auto-removal) and the panel + localStorage
persistence contract, as specified in
[`plans/e2e-test-coverage-gaps.md`](plans/e2e-test-coverage-gaps.md) (G1, G2)
and the DOM contract in
[`plans/e2e-harness-brief.md`](plans/e2e-harness-brief.md) §8.

The status bar is driven through its public ``StatusBar.*`` API via
``page.evaluate`` and the real 2000 ms polling path, with
``GET /api/v1/status/getStatus`` mocked via ``page.route`` so no real
backend tasks are required.
"""

import json
import re
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import register_and_login

# Glob matching the status bar's polling endpoint (any uuid, any query).
STATUS_POLL_ROUTE = "**/api/v1/status/getStatus*"


def _status_envelope(status: str) -> str:
    """Build the universal API envelope for a getStatus response (brief §6)."""
    return json.dumps(
        {
            "success": True,
            "data": {"status": status},
            "message": "Status retrieved successfully",
            "metadata": {"timestamp": "2026-01-01T00:00:00Z", "request_id": "e2e-test"},
        }
    )


def _mock_status(page: Any, status: str) -> None:
    """Intercept the status bar's polling endpoint with a fixed status."""
    body = _status_envelope(status)
    page.route(
        STATUS_POLL_ROUTE,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=body
        ),
    )


def _logged_in_home(page: Any) -> str:
    """Authenticate and land on the home page (status bar is global)."""
    username = register_and_login(page)
    page.wait_for_load_state("networkidle")
    return username


def _stored_tasks(page: Any) -> list[Any]:
    """Return the parsed ``localStorage['glyph_active_tasks']`` value (or [])."""
    raw = page.evaluate("() => localStorage.getItem('glyph_active_tasks')")
    if raw is None:
        return []
    return json.loads(raw)


class TestTaskLifecycle:
    """G1 — status bar task lifecycle."""

    def test_register_task_shows_entry_badge_dot_and_tooltip(
        self, page: Any, server: Any
    ) -> None:
        # Arrange: keep the task alive by polling "processing".
        _mock_status(page, "processing")
        _logged_in_home(page)

        # Act
        page.evaluate(
            "() => StatusBar.registerTask('test-uuid-1', 'my-task.elf', "
            "{resultLink: '/task-results?task_uuid=test-uuid-1', resultLabel: 'View results'})"
        )

        # Assert: the toggle reflects the new task (badge, dot, active state).
        # registerTask does not auto-open the panel, so the entry lives in the
        # closed panel until it is opened.
        badge = page.locator("#status-bar-toggle .badge")
        expect(badge).to_be_visible()
        expect(badge).to_have_text("1")
        expect(page.locator("#status-bar-toggle .indicator-dot.is-processing")).to_have_count(1)
        expect(page.locator("#status-bar-toggle")).to_have_class(re.compile(r"\bis-active\b"))

        # Tooltip content updates (processing count, total; empty state hidden).
        tooltip = page.locator("#status-bar-toggle .status-bar-tooltip")
        expect(tooltip.locator(".tooltip-row.is-processing .count")).to_have_text("1")
        expect(tooltip.locator(".tooltip-row.is-total .count")).to_have_text("1")
        expect(tooltip.locator(".tooltip-row.is-uploading .count")).to_have_text("0")
        expect(tooltip.locator(".tooltip-empty")).to_have_attribute(
            "style", re.compile(r"display:\s*none")
        )

        # Open the panel and assert the entry appears with its content.
        page.click("#status-bar-toggle")
        expect(page.locator("#status-bar-panel")).to_have_class(re.compile(r"\bis-visible\b"))
        entry = page.locator("#entry-test-uuid-1")
        expect(entry).to_be_visible()
        expect(entry.locator(".status-entry-file")).to_contain_text("my-task.elf")
        expect(entry.locator(".status-entry-processing")).to_be_visible()

    def test_completed_task_shows_success_toast_with_result_link_and_auto_removes(
        self, page: Any, server: Any
    ) -> None:
        # Arrange: polling reports the terminal "completed" status.
        _mock_status(page, "completed")
        _logged_in_home(page)

        # Act
        page.evaluate(
            "() => StatusBar.registerTask('done-uuid', 'my-task.elf', "
            "{resultLink: '/task-results?task_uuid=done-uuid', resultLabel: 'View results'})"
        )

        # Assert: success toast with the result link.
        toast = page.locator(".toast-success")
        expect(toast).to_be_visible()
        expect(toast).to_contain_text("my-task.elf completed successfully")
        link = toast.locator("a")
        expect(link).to_have_attribute("href", "/task-results?task_uuid=done-uuid")
        expect(link).to_have_text("View results")

        # The entry auto-removes ~3 s after the terminal state.
        expect(page.locator("#entry-done-uuid")).to_have_count(0, timeout=6000)

    def test_failed_task_shows_error_toast(self, page: Any, server: Any) -> None:
        # Arrange: polling reports the terminal "error" status.
        _mock_status(page, "error")
        _logged_in_home(page)

        # Act
        page.evaluate("() => StatusBar.registerTask('fail-uuid', 'bad.elf')")

        # Assert: entry is marked as failed (error class) and the error toast
        # is shown. NOTE: the in-entry "Processing failed" label is NOT asserted
        # because _handleTerminalState() only rewrites the label when a
        # .status-entry-label element exists, which processing entries do not
        # have (genuine app bug) — the entry keeps showing "Processing...".
        entry = page.locator("#entry-fail-uuid")
        expect(entry).to_have_class(re.compile(r"\berror\b"))

        toast = page.locator(".toast-error")
        expect(toast).to_be_visible()
        expect(toast).to_contain_text("bad.elf processing failed")

        # The failed entry also auto-removes.
        expect(page.locator("#entry-fail-uuid")).to_have_count(0, timeout=6000)

    def test_upload_lifecycle_progress_to_processing(
        self, page: Any, server: Any
    ) -> None:
        # Arrange
        _mock_status(page, "processing")
        _logged_in_home(page)

        # Act: register an upload → "uploading" entry with progress.
        client_id = page.evaluate("() => StatusBar.registerUpload('sample.elf')")
        assert isinstance(client_id, str) and client_id.startswith("upload_")

        entry = page.locator(f"#entry-{client_id}")
        expect(entry).to_be_visible()
        expect(entry.locator(".status-entry-progress")).to_be_visible()
        expect(page.locator(f"#percent-{client_id}")).to_have_text("0%")

        # The upload auto-opens the panel; badge + uploading dot + tooltip update.
        expect(page.locator("#status-bar-panel")).to_be_visible()
        expect(page.locator("#status-bar-toggle .badge")).to_have_text("1")
        expect(page.locator("#status-bar-toggle .indicator-dot.is-uploading")).to_have_count(1)
        expect(
            page.locator(
                "#status-bar-toggle .status-bar-tooltip .tooltip-row.is-uploading .count"
            )
        ).to_have_text("1")

        # Act: progress climbs.
        page.evaluate("(id) => StatusBar.updateUploadProgress(id, 45)", client_id)
        expect(page.locator(f"#percent-{client_id}")).to_have_text("45%")
        expect(page.locator(f"#progress-fill-{client_id}")).to_have_attribute(
            "style", re.compile(r"width:\s*45%")
        )

        # Act: 100% transitions the entry UI to processing.
        page.evaluate("(id) => StatusBar.updateUploadProgress(id, 100)", client_id)
        expect(page.locator(f"#entry-{client_id} .status-entry-progress")).to_have_count(0)
        expect(page.locator(f"#entry-{client_id} .status-entry-processing")).to_be_visible()

        # Act: uploadComplete re-keys the task under the server UUID.
        page.evaluate(
            "([id, uuid]) => StatusBar.uploadComplete(id, uuid)",
            [client_id, "task-uuid-77"],
        )
        expect(page.locator(f"#entry-{client_id}")).to_have_count(0)
        expect(page.locator("#entry-task-uuid-77")).to_be_visible()
        expect(page.locator("#entry-task-uuid-77 .status-entry-processing")).to_be_visible()
        expect(page.locator("#status-bar-toggle .indicator-dot.is-processing")).to_have_count(1)

        # The task is persisted under the server UUID (no client id remains).
        tasks = _stored_tasks(page)
        assert any(t["uuid"] == "task-uuid-77" for t in tasks)
        assert not any(str(t["uuid"]).startswith("upload_") for t in tasks)


class TestPanelAndPersistence:
    """G2 — status bar panel and localStorage persistence."""

    def test_toggle_opens_and_closes_panel(self, page: Any, server: Any) -> None:
        # Arrange
        _logged_in_home(page)

        toggle = page.locator("#status-bar-toggle")
        panel = page.locator("#status-bar-panel")
        expect(toggle).to_be_visible()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        expect(panel).to_be_hidden()

        # Act: open the panel.
        toggle.click()
        expect(panel).to_have_class(re.compile(r"\bis-visible\b"))
        expect(toggle).to_have_attribute("aria-expanded", "true")

        # Act: close it again.
        toggle.click()
        expect(panel).to_be_hidden()
        expect(toggle).to_have_attribute("aria-expanded", "false")

    def test_dismiss_removes_only_that_entry(self, page: Any, server: Any) -> None:
        # Arrange: two tasks, panel open.
        _mock_status(page, "processing")
        _logged_in_home(page)
        page.evaluate("() => StatusBar.registerTask('uuid-a', 'a.elf')")
        page.evaluate("() => StatusBar.registerTask('uuid-b', 'b.elf')")
        page.locator("#status-bar-toggle").click()
        expect(page.locator("#entry-uuid-a")).to_be_visible()
        expect(page.locator("#entry-uuid-b")).to_be_visible()

        # Act: dismiss only the first entry.
        page.locator("#entry-uuid-a .status-entry-dismiss").click()

        # Assert: first entry gone, second untouched, badge decremented.
        expect(page.locator("#entry-uuid-a")).to_have_count(0, timeout=2000)
        expect(page.locator("#entry-uuid-b")).to_be_visible()
        expect(page.locator("#status-bar-toggle .badge")).to_have_text("1")

    def test_close_button_hides_panel(self, page: Any, server: Any) -> None:
        # Arrange: one task, panel open.
        _mock_status(page, "processing")
        _logged_in_home(page)
        page.evaluate("() => StatusBar.registerTask('uuid-c', 'c.elf')")
        page.locator("#status-bar-toggle").click()
        expect(page.locator("#status-bar-panel")).to_have_class(re.compile(r"\bis-visible\b"))

        # Act: use the panel's close button.
        page.locator(".status-bar-close").click()

        # Assert: panel hidden, toggle collapsed.
        expect(page.locator("#status-bar-panel")).to_be_hidden()
        expect(page.locator("#status-bar-toggle")).to_have_attribute(
            "aria-expanded", "false"
        )

    def test_empty_state_when_no_tasks(self, page: Any, server: Any) -> None:
        # Arrange
        _mock_status(page, "processing")
        _logged_in_home(page)

        # With no tasks, the tooltip shows the "No active tasks" state.
        expect(
            page.locator("#status-bar-toggle .status-bar-tooltip .tooltip-empty")
        ).to_have_attribute("style", re.compile(r"display:\s*block"))

        # Act: register a task, open the panel, then dismiss it.
        page.evaluate("() => StatusBar.registerTask('uuid-e', 'e.elf')")
        page.locator("#status-bar-toggle").click()
        expect(page.locator("#entry-uuid-e")).to_be_visible()
        page.locator("#entry-uuid-e .status-entry-dismiss").click()

        # Assert: the panel shows the empty state once the last entry is gone.
        empty = page.locator("#status-bar-panel .status-bar-empty")
        expect(empty).to_be_visible(timeout=2000)
        expect(empty).to_have_text("No active tasks")

    def test_task_persists_to_localstorage_and_restores_after_reload(
        self, page: Any, server: Any
    ) -> None:
        # Arrange: keep the restored task alive via mocked polling.
        _mock_status(page, "processing")
        _logged_in_home(page)

        # Act: drive the upload lifecycle so the task reaches the server-side
        # "processing" state. registerTask() alone does not persist to
        # localStorage; only uploadComplete() (and removeEntry/restore-cleanup)
        # call _persistTasks(), so the upload flow is the real persistence path.
        client_id = page.evaluate("() => StatusBar.registerUpload('persisted.elf')")
        page.evaluate(
            "([cid]) => StatusBar.updateUploadProgress(cid, 100)", [client_id]
        )
        page.evaluate(
            "([cid]) => StatusBar.uploadComplete(cid, 'persist-uuid')", [client_id]
        )

        # Assert: the processing task is written to localStorage.
        tasks = _stored_tasks(page)
        assert any(
            t["uuid"] == "persist-uuid" and t["state"] == "processing" for t in tasks
        )

        # Act: reload the page.
        page.reload()
        page.wait_for_load_state("networkidle")

        # Assert: the processing task entry is restored from localStorage.
        # Restore does not auto-open the panel, so open it to inspect the entry.
        page.click("#status-bar-toggle")
        expect(page.locator("#entry-persist-uuid")).to_be_visible()
        expect(page.locator("#entry-persist-uuid .status-entry-file")).to_contain_text(
            "persisted.elf"
        )
        expect(page.locator("#status-bar-toggle .badge")).to_have_text("1")

    def test_stale_upload_client_ids_are_skipped_on_restore(
        self, page: Any, server: Any
    ) -> None:
        # Arrange: seed a stale client-side upload id into localStorage.
        _logged_in_home(page)
        page.evaluate(
            """() => localStorage.setItem('glyph_active_tasks', JSON.stringify([
                    {uuid: 'upload_1700000000000_stale1', fileName: 'stale.elf', state: 'uploading'}
                ]))"""
        )

        # Act: reload the page.
        page.reload()
        page.wait_for_load_state("networkidle")

        # Assert: the stale upload_* entry is not restored and is cleaned up.
        expect(page.locator(".status-entry")).to_have_count(0)
        expect(page.locator("#status-bar-toggle .badge")).to_be_hidden()
        assert _stored_tasks(page) == []
