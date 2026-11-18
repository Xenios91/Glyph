# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""P2 e2e: server-side oversized upload returns 413 and shows an inline error.

TESTS.md (Oversized upload server-side 413): upload a file exceeding
``max_file_size_mb`` (set a tiny limit via a ``GLYPH_`` env in a dedicated
server run). The ``RequestSizeMiddleware`` must reject the request with a 413
(the response body carries the ``PAYLOAD_TOO_LARGE`` error envelope), the client
must surface it as the inline upload error (not a generic toast), and the
beforeunload guard must be released.

The client-side ``validateFile`` check only rejects files *strictly greater*
than the limit, so a file of exactly ``max_file_size_mb`` MiB passes the
client check. Its multipart body (file bytes + boundary + headers + the
``name`` field) then exceeds the server's 1 MiB limit, so the
``RequestSizeMiddleware`` rejects it with a 413 before it reaches the upload
endpoint. This is what lets us exercise the *server* limit through the real
browser upload flow.

The client-side limit check itself is already covered by
``test_oversized_file_shows_limit_error``.
"""

import uuid
from typing import Any

from tests.e2e.utils import wait_for_login_form

# The dedicated server's max_file_size_mb. The file below is exactly this many
# MiB, so it passes the client's strict `>` check but its multipart body
# exceeds the server limit.
MAX_MB = 1
# Exactly MAX_MB MiB = 1,048,576 bytes, with a 4-byte ELF magic prefix.
FILE_BYTES = b"\x7fELF" + b"\x00" * (MAX_MB * 1024 * 1024 - 4)


def _register_and_login(page: Any, base_url: str) -> str:
    """Register via the API and log in through the UI; return the username."""
    username = f"oversize_{uuid.uuid4().hex[:10]}"
    response = page.request.post(
        f"{base_url}/auth/register",
        data={
            "username": username,
            "email": f"{username}@test.com",
            "password": "SecurePass123!",
            "full_name": "Oversize Test",
        },
    )
    assert response.status == 201, f"register failed: {response.status} {response.text()}"

    page.goto(f"{base_url}/login")
    wait_for_login_form(page)
    page.locator("#username").fill(username)
    page.locator("#password").fill("SecurePass123!")
    page.locator("#login-submit-btn").click()
    page.wait_for_url(f"{base_url}/", timeout=15000)
    return username


def _guard_prevented(page: Any) -> bool:
    """Return whether the beforeunload guard would block navigation."""
    return page.evaluate(
        """() => {
            const e = new Event('beforeunload', {cancelable: true});
            window.dispatchEvent(e);
            return e.defaultPrevented;
        }"""
    )


def test_server_413_shows_inline_error(browser: Any, start_dedicated_server: Any) -> None:
    """A file whose multipart body exceeds the server limit yields a 413 that
    is shown inline (not as a generic toast) and releases the unload guard."""
    _, base_url = start_dedicated_server(max_file_size_mb=MAX_MB)

    context = browser.new_context()
    page = context.new_page()

    try:
        _register_and_login(page, base_url)
        page.goto(f"{base_url}/binary-library")

        # Confirm the client-side limit hint reflects the dedicated server's
        # 1 MB setting (proves the server config reached the template).
        hint = page.locator("#upload-limit-hint")
        assert hint.get_attribute("data-max-mb") == str(MAX_MB)

        # The file is exactly 1 MiB, so it passes the client's strict `>`
        # check and the upload proceeds to the server, which must 413.
        with page.expect_response(
            lambda r: "uploadBinary" in r.url and r.status == 413, timeout=30000
        ) as response_info:
            page.locator("#upload-binary").set_input_files(
                {"name": "big.bin", "mimeType": "application/octet-stream", "buffer": FILE_BYTES}
            )

        response = response_info.value
        assert response.status == 413
        body = response.json()
        # The 413 carries the standard error envelope produced by the app's
        # exception handler (not a raw FastAPI {"detail": ...} body).
        assert body.get("success") is False, f"unexpected 413 body: {body}"
        error = body.get("error", {})
        assert error.get("code") == "PAYLOAD_TOO_LARGE", f"unexpected 413 error code: {body}"
        assert error.get("message") == "Request body too large", f"unexpected 413 error: {body}"

        # The 413 must surface as the inline upload error (the client shows the
        # HTTP status), not a generic toast.
        upload_error = page.locator("#upload-error")
        upload_error.wait_for(state="visible", timeout=10000)
        assert "413" in upload_error.inner_text(), (
            f"expected the inline error to reference the 413, got: {upload_error.inner_text()!r}"
        )

        # The progress bar is hidden after the failed upload.
        assert not page.locator("#upload-progress").is_visible()

        # No generic error toast was raised for this failure.
        assert page.locator(".toast-error").count() == 0

        # The beforeunload guard is released once the request reached a
        # terminal state.
        assert _guard_prevented(page) is False
    finally:
        context.close()
