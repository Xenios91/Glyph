# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for concurrent / repeated binary uploads (TESTS.md P1).

Uploads two small ELFs back-to-back in the same browser session and verifies
the upload pipeline and library list survive repeated uploads: both uploads
complete, both rows appear in the library, no 5xx responses, and no stale
progress bar remains.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, generate_unique_username, register_and_login

# Minimal valid ELF header; the upload endpoint accepts it (background
# decompilation may fail without Ghidra/JDK, but the upload itself is
# independent of that outcome).
ELF_FILE = {
    "name": "sample.bin",
    "mimeType": "application/octet-stream",
    "buffer": b"\x7fELF" + b"\x00" * 64,
}


class TestConcurrentUploads:
    """Repeated uploads must complete independently without corrupting UI state."""

    def test_two_uploads_complete_independently(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        server_errors: list[int] = []

        def on_response(response: Any) -> None:
            if response.status >= 500:
                server_errors.append(response.status)

        page.on("response", on_response)

        name1 = generate_unique_username()
        name2 = generate_unique_username()

        # Act + Assert: first upload completes end-to-end
        page.locator("#binary-name").fill(name1)
        page.locator("#upload-binary").set_input_files(ELF_FILE)
        expect(page.locator("#progress-text")).to_contain_text("Upload complete!", timeout=30000)
        expect(page.locator(".toast-success").filter(has_text=name1)).to_be_visible(timeout=10000)
        expect(page.locator("#binaries-tbody .binary-name").filter(has_text=name1)).to_be_visible(timeout=10000)
        # Progress bar is hidden again (no stale progress bar)
        expect(page.locator("#upload-progress")).to_be_hidden(timeout=10000)

        # Act + Assert: second upload completes end-to-end (upload guard released)
        page.locator("#binary-name").fill(name2)
        page.locator("#upload-binary").set_input_files(ELF_FILE)
        expect(page.locator("#progress-text")).to_contain_text("Upload complete!", timeout=30000)
        expect(page.locator(".toast-success").filter(has_text=name2)).to_be_visible(timeout=10000)
        expect(page.locator("#binaries-tbody .binary-name").filter(has_text=name2)).to_be_visible(timeout=10000)

        # Assert: both rows coexist in the library
        expect(page.locator("#binaries-tbody tr[data-binary-id]")).to_have_count(2)
        # Progress bar remains hidden after the second upload
        expect(page.locator("#upload-progress")).to_be_hidden()
        # No server errors during either upload
        assert server_errors == [], f"Server returned 5xx responses: {server_errors}"
