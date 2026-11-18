# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""P2 e2e: rate-limit 429 surfaces a readable error and the UI recovers.

TESTS.md (Rate-limit 429 UI): fire the login endpoint repeatedly to trip
slowapi, then attempt login in the UI. The 429 must surface a readable error
(not a blank page), and the UI must recover after the window resets.

The shared session server runs with generous limits (100/60), so this test
uses a dedicated server with a strict window (3 requests / 30 seconds) so the
limit can be tripped quickly and the window can be allowed to reset within the
test's time budget.
"""

import time
import uuid
from typing import Any

from tests.e2e.utils import wait_for_login_form

# Strict login limit for the dedicated server: 3 requests per 30-second
# window. The window resets quickly enough to observe recovery in-test.
LOGIN_MAX = "3"
LOGIN_WINDOW = "30"
# Wait just past the window so the slowapi bucket is guaranteed to have
# refilled before the recovery attempt.
RECOVERY_WAIT_SECONDS = 31


def _register_user(page: Any, base_url: str) -> str:
    """Register a user via the API and return the username.

    Uses the API (not the UI) so the registration flow does not consume any
    of the dedicated server's login budget.
    """
    username = f"ratelimit_{uuid.uuid4().hex[:10]}"
    password = "SecurePass123!"
    response = page.request.post(
        f"{base_url}/auth/register",
        data={
            "username": username,
            "email": f"{username}@test.com",
            "password": password,
            "full_name": "Rate Limit Test",
        },
    )
    assert response.status == 201, f"register failed: {response.status} {response.text()}"
    return username


def _login_via_api(page: Any, base_url: str, username: str) -> Any:
    """POST form-encoded credentials to /auth/token and return the response."""
    return page.request.post(
        f"{base_url}/auth/token",
        form={"username": username, "password": "SecurePass123!"},
    )


def _login_via_ui(page: Any, base_url: str, username: str) -> None:
    """Fill and submit the login form in the browser."""
    if "/login" not in page.url:
        page.goto(f"{base_url}/login")
    wait_for_login_form(page)
    page.locator("#username").fill(username)
    page.locator("#password").fill("SecurePass123!")
    page.locator("#login-submit-btn").click()


def test_429_shows_error_and_recovers(browser: Any, start_dedicated_server: Any) -> None:
    """Tripping the login rate limit shows a readable 429 error; login works
    again once the window resets."""
    _, base_url = start_dedicated_server(
        {
            "GLYPH_RATE_LIMIT_LOGIN_MAX": LOGIN_MAX,
            "GLYPH_RATE_LIMIT_LOGIN_WINDOW": LOGIN_WINDOW,
        }
    )

    # A dedicated server means the shared port-8000 server is NOT running, so
    # use the browser fixture directly with our own context/page.
    context = browser.new_context()
    page = context.new_page()

    try:
        username = _register_user(page, base_url)

        # Exhaust the login budget: the first 3 attempts succeed.
        for _ in range(int(LOGIN_MAX)):
            ok = _login_via_api(page, base_url, username)
            assert ok.status == 200, f"expected 200, got {ok.status}: {ok.text()}"

        # The 4th attempt trips slowapi and must return a 429 with a readable
        # body (not a blank page / opaque error).
        limited = _login_via_api(page, base_url, username)
        assert limited.status == 429, f"expected 429, got {limited.status}: {limited.text()}"
        body = limited.text()
        assert "Rate limit exceeded" in body, f"429 body not readable: {body!r}"

        # The successful API logins above set the access-token cookie in the
        # shared browser context (page.request shares the context's cookie
        # jar), which would make /login redirect to the home page instead of
        # rendering the form. Clear the cookies so the UI login actually hits
        # the (still rate-limited) /auth/token endpoint. The rate limit is
        # keyed by client IP, so clearing cookies does not reset the budget.
        context.clear_cookies()

        # Attempt login in the UI while limited: the page must stay usable and
        # surface a readable error toast (not a blank page).
        _login_via_ui(page, base_url, username)
        toast = page.locator(".toast-error").first
        toast.wait_for(state="visible", timeout=10000)
        toast_text = toast.inner_text()
        assert toast_text.strip(), "429 toast is blank"
        # The UI must not be broken: the login form is still present and the
        # submit button is re-enabled after the failed attempt.
        assert page.locator("#loginForm").count() == 1
        assert page.locator("#login-submit-btn").is_enabled()

        # Wait for the rate-limit window to reset, then the same UI login must
        # succeed (recovery).
        time.sleep(RECOVERY_WAIT_SECONDS)
        _login_via_ui(page, base_url, username)
        page.wait_for_url(f"{base_url}/", timeout=15000)
    finally:
        context.close()
