# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for binary upload success and cancel/oversized flows (B1, B2).

Covers the e2e coverage gaps:
- B1: Full successful upload (progress → 'Upload complete!' → success toast → new row)
- B2: Upload cancel (guard released, progress reset) and oversized file (limit message)
"""

import re
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, generate_unique_username, register_and_login


class TestFullSuccessfulUpload:
    """B1: Full successful upload flow."""

    def test_upload_success_full_flow(self, page: Any, server: Any) -> None:
        """Select a valid ELF → progress → 'Upload complete!' → success toast → new row.

        The upload endpoint succeeds (binary row created, binary_id returned) and
        queues a background decompilation task. The decompilation task fails in
        this environment (no Ghidra/JDK), but the upload itself is independent of
        the decompilation outcome: the success toast and list reload are driven by
        the HTTP 2xx response, not by the decompilation task completing.
        """
        # Arrange
        register_and_login(page)
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        binary_name = generate_unique_username()
        page.locator("#binary-name").fill(binary_name)

        # Act: select a valid ELF file (triggers upload automatically via change event)
        page.locator("#upload-binary").set_input_files(
            {"name": "sample.bin", "mimeType": "application/octet-stream",
             "buffer": b"\x7fELF" + b"\x00" * 64}
        )

        # Assert: progress bar becomes visible
        progress = page.locator("#upload-progress")
        expect(progress).to_be_visible(timeout=5000)

        # Assert: wait for the definitive success state "Upload complete!"
        # The transient "Processing..." indeterminate state occurs between
        # file-sent (xhr.upload.load) and server-confirmed (xhr.load); it is
        # too brief for a small file to assert deterministically.
        progress_text = page.locator("#progress-text")
        expect(progress_text).to_contain_text("Upload complete!", timeout=30000)

        # Assert: success toast appears (800ms after "Upload complete!")
        toast = page.locator(".toast-success")
        expect(toast).to_be_visible(timeout=10000)
        expect(toast).to_contain_text(f"Binary \"{binary_name}\" uploaded successfully")

        # Assert: list reloaded with a new row for the uploaded binary
        row = page.locator("#binaries-tbody .binary-name").filter(has_text=binary_name)
        expect(row).to_be_visible(timeout=10000)


class TestUploadCancelAndOversized:
    """B2: Upload cancel and oversized file."""

    def test_upload_cancel_releases_guard(self, page: Any, server: Any) -> None:
        """Click #upload-cancel during in-flight upload → error, guard released, progress reset."""
        # Arrange
        register_and_login(page)
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Hold the upload request open so the transfer never completes
        page.route("**/api/v1/binaries/uploadBinary", lambda route: None)

        # Act: start an upload that will be held in-flight
        page.locator("#upload-binary").set_input_files(
            {"name": "slow.bin", "mimeType": "application/octet-stream",
             "buffer": b"\x7fELF" + b"\x00" * 64}
        )
        page.wait_for_selector("#upload-progress", state="visible", timeout=5000)

        # Assert: beforeunload guard is armed during in-flight upload
        prevented = page.evaluate(
            "() => { const e = new Event('beforeunload', {cancelable: true});"
            " window.dispatchEvent(e); return e.defaultPrevented; }"
        )
        assert prevented is True, "beforeunload guard should be armed during upload"

        # Act: cancel the upload
        page.locator("#upload-cancel").click()

        # Assert: inline error shows "Upload cancelled."
        error = page.locator("#upload-error")
        expect(error).to_be_visible(timeout=5000)
        expect(error).to_contain_text("Upload cancelled.")

        # Assert: progress UI is reset (hidden)
        expect(page.locator("#upload-progress")).not_to_be_visible(timeout=5000)

        # Assert: beforeunload guard is released
        prevented_after = page.evaluate(
            "() => { const e = new Event('beforeunload', {cancelable: true});"
            " window.dispatchEvent(e); return e.defaultPrevented; }"
        )
        assert prevented_after is False, "beforeunload guard should be released after cancel"

        # Cleanup
        page.unroute("**/api/v1/binaries/uploadBinary")

    def test_oversized_file_shows_limit_error(self, page: Any, server: Any) -> None:
        """Select an oversized file → 'exceeds the Y MB upload limit' message.

        The configured max file size is read from the server-rendered
        #upload-limit-hint[data-max-mb] attribute at page load. To keep the
        test fast and deterministic, the page is intercepted via page.route to
        set a small max (1 MB) before the JS reads it, then a 2 MB buffer is
        selected to trigger the client-side limit check.
        """
        # Arrange
        register_and_login(page)

        # Intercept the binary-library page to set a small max file size (1 MB)
        # before the JS reads the data-max-mb attribute at DOMContentLoaded.
        def handle_route(route: Any) -> None:
            response = route.fetch()
            body = response.text()
            body = re.sub(r'data-max-mb="\d+"', 'data-max-mb="1"', body)
            route.fulfill(
                status=response.status,
                headers=dict(response.headers),
                body=body,
            )

        page.route("**/binary-library", handle_route)
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Act: select a file that exceeds the 1 MB limit
        oversized_buffer = b"\x00" * (2 * 1024 * 1024)  # 2 MB
        page.locator("#upload-binary").set_input_files(
            {"name": "big.bin", "mimeType": "application/octet-stream",
             "buffer": oversized_buffer}
        )

        # Assert: error message shows the limit exceeded message
        error = page.locator("#upload-error")
        expect(error).to_be_visible(timeout=5000)
        expect(error).to_contain_text("exceeds the 1 MB upload limit")

        # Assert: no upload was started (progress stays hidden)
        assert not page.locator("#upload-progress").is_visible(), \
            "Progress should remain hidden when the file exceeds the size limit"

        # Cleanup
        page.unroute("**/binary-library")
