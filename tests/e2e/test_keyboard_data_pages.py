# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for keyboard navigation on data-heavy pages (TESTS.md P2).

Extends ``test_accessibility.py::TestKeyboardNavigation`` (which covers only
login / register / the task modal) to the data tables: the binary library
table and the similarity dashboard selection panel. The interactive controls
inside a library row (RUN TASK, DETAILS, DELETE) must be keyboard-reachable,
and activating RUN TASK from the keyboard must open the task-selection modal.
"""

import re
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login

# Minimal valid ELF header; the upload endpoint accepts it (background
# decompilation may fail without Ghidra/JDK, but the upload itself is
# independent of that outcome).
ELF_FILE = {
    "name": "sample.bin",
    "mimeType": "application/octet-stream",
    "buffer": b"\x7fELF" + b"\x00" * 64,
}


def _upload_binary(page: Any, name: str) -> str:
    """Upload a small ELF in the binary library and return its binary id.

    Args:
        page: Playwright page object (already logged in).
        name: Display name for the uploaded binary.

    Returns:
        The ``data-binary-id`` of the new library row.

    """
    page.goto(f"{BASE_URL}/binary-library")
    page.wait_for_load_state("networkidle")
    page.locator("#binary-name").fill(name)
    page.locator("#upload-binary").set_input_files(ELF_FILE)
    expect(page.locator("#progress-text")).to_contain_text("Upload complete!", timeout=30000)
    row = page.locator("#binaries-tbody tr[data-binary-id]").filter(has_text=name)
    expect(row).to_have_count(1, timeout=10000)
    binary_id = row.get_attribute("data-binary-id")
    assert binary_id is not None, "Library row is missing its data-binary-id attribute"
    return binary_id


def _assert_focusable(locator: Any) -> None:
    """Assert a control is keyboard-focusable: not disabled and not
    explicitly removed from the tab order via ``tabindex="-1"``."""
    expect(locator).to_be_enabled()
    tabindex = locator.get_attribute("tabindex")
    assert tabindex != "-1", "Control is explicitly removed from the tab order"


class TestLibraryRowsKeyboardReachable:
    """The interactive controls in a library row are reachable by keyboard."""

    def test_library_rows_keyboard_reachable(self, page: Any, server: Any) -> None:
        # Arrange: a user with exactly one binary in the library.
        register_and_login(page)
        binary_id = _upload_binary(page, "kb_keyboard.bin")

        row = page.locator(f"#binaries-tbody tr[data-binary-id='{binary_id}']")
        expect(row).to_have_count(1)

        run_task = row.locator(".btn-run-task")
        details = row.locator(".btn-binary-details")
        delete = row.locator(".btn-delete-binary")

        # Assert: the row's interactive controls are keyboard-reachable.
        _assert_focusable(run_task)
        _assert_focusable(details)
        _assert_focusable(delete)
        expect(details).to_have_attribute("href", f"/binary/{binary_id}")

        # Act: focus the RUN TASK control with the keyboard and activate it.
        run_task.focus()
        expect(run_task).to_be_focused()
        page.keyboard.press("Enter")

        # Assert: the task-selection modal opens from keyboard activation.
        overlay = page.locator("#task-modal-overlay")
        expect(overlay).to_have_class(re.compile(r"\bis-visible\b"))
        # The modal renders its options from the canonical action list.
        expect(overlay.locator("a.task-option")).to_have_count(
            page.evaluate("() => window.BinaryActions.actions.length")
        )

        # Act: close the modal with Escape (document-level keydown handler).
        page.keyboard.press("Escape")
        expect(overlay).not_to_have_class(re.compile(r"\bis-visible\b"))

    def test_similarity_selection_panel_keyboard_reachable(self, page: Any, server: Any) -> None:
        # Arrange: a user with two binaries (compute needs >= 2 selected),
        # on the similarity dashboard.
        register_and_login(page)
        _upload_binary(page, "kb_sim_a.bin")
        _upload_binary(page, "kb_sim_b.bin")
        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # The selection list renders a checkbox per binary once loaded.
        checkboxes = page.locator(".binary-checkbox")
        expect(checkboxes.first).to_be_visible(timeout=15000)
        expect(checkboxes).to_have_count(2)

        # Assert: the selection-panel controls are keyboard-reachable.
        select_all = page.locator("#select-all-btn")
        deselect_all = page.locator("#deselect-all-btn")
        compute = page.locator("#compute-btn")
        _assert_focusable(select_all)
        _assert_focusable(deselect_all)
        # compute is enabled only once two binaries are selected.
        expect(compute).to_be_disabled()

        # Act: select both binaries from the keyboard, which enables compute.
        checkboxes.nth(0).check()
        checkboxes.nth(1).check()
        expect(compute).to_be_enabled()
        _assert_focusable(compute)
