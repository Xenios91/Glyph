# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for multi-user session isolation (TESTS.md P1).

Two users in separate browser contexts each upload a binary; user A must be
denied access to user B's binary (403 ACCESS_DENIED -> error state on the
detail page), A's library must never list B's binary, and logging out A must
not affect B's session.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, generate_unique_username, logout_user, register_and_login

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


class TestMultiUserIsolation:
    """Per-user data isolation and session independence through real browsers."""

    def test_cross_user_binary_access_denied(self, page: Any, server: Any, browser: Any) -> None:
        # Arrange: two independent browser contexts (separate cookie jars)
        context_b = browser.new_context()
        try:
            page_b = context_b.new_page()

            username_a = register_and_login(page)
            username_b = register_and_login(page_b)

            name_a = generate_unique_username()
            name_b = generate_unique_username()
            id_a = _upload_binary(page, name_a)
            id_b = _upload_binary(page_b, name_b)

            # Assert: A's library lists A's binary but never B's
            expect(page.locator("#binaries-tbody .binary-name").filter(has_text=name_a)).to_be_visible()
            expect(page.locator("#binaries-tbody .binary-name").filter(has_text=name_b)).to_have_count(0)

            # Assert: the API denies A access to B's binary (403 ACCESS_DENIED).
            # The body is a top-level ErrorResponse envelope {success, error,
            # metadata}; tolerate a {detail: {...}} wrapper as well.
            api_response = page.request.get(f"{BASE_URL}/api/v1/binaries/binaries/{id_b}")
            assert api_response.status == 403, (
                f"Expected 403 for cross-user access, got {api_response.status}"
            )
            body = api_response.json()
            detail = body.get("detail", body)
            assert detail.get("error", {}).get("code") == "ACCESS_DENIED"

            # Assert: A's detail page for B's binary shows the error state
            # (the web page itself renders for any authenticated user; the
            # API 403 drives the client-side error display).
            page.goto(f"{BASE_URL}/binary/{id_b}")
            page.wait_for_load_state("networkidle")
            expect(page.locator("#detail-error")).to_be_visible(timeout=10000)
            expect(page.locator("#detail-content")).to_be_hidden()

            # Assert: A's own detail page loads normally
            page.goto(f"{BASE_URL}/binary/{id_a}")
            page.wait_for_load_state("networkidle")
            expect(page.locator("#detail-content")).to_be_visible(timeout=10000)

            # Act: log A out
            logout_user(page, username_a)

            # Assert: B's session is unaffected - B can still load its own binary
            page_b.goto(f"{BASE_URL}/binary/{id_b}")
            page_b.wait_for_load_state("networkidle")
            expect(page_b.locator("#detail-content")).to_be_visible(timeout=10000)
        finally:
            context_b.close()
