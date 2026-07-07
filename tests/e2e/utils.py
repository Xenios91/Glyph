# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Shared test utilities for Playwright E2E tests.

Provides common helper functions used across multiple test files to avoid
duplication and maintain consistency in test setup and interactions.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

import time
import uuid
from typing import Any

BASE_URL = "http://127.0.0.1:8000"


def generate_unique_username() -> str:
    """Generate a unique username for testing.

    Uses a short UUID prefix combined with a timestamp to guarantee uniqueness
    across all tests in a session, even when multiple tests run within the same
    millisecond.

    Returns:
        A unique username string like 'testuser_a1b2c3d_12345'.

    """
    short_uuid = uuid.uuid4().hex[:8]
    timestamp = int(time.time() * 1000) % 100000
    return f"testuser_{short_uuid}_{timestamp}"


# ---------------------------------------------------------------------------
# Form waiters
# ---------------------------------------------------------------------------


def wait_for_register_form(page: Any, timeout: int = 10000) -> None:
    """Wait for the registration form JavaScript to be initialized.

    The registration form sets a `data-initialized='true'` attribute once
    its JavaScript has run and the form is ready for interaction.

    Args:
        page: Playwright page object.
        timeout: Maximum time to wait in milliseconds.

    """
    page.wait_for_selector("#registerForm[data-initialized='true']", timeout=timeout)


def wait_for_login_form(page: Any, timeout: int = 10000) -> None:
    """Wait for the login form JavaScript to be initialized.

    The login form sets a `data-initialized='true'` attribute once its
    JavaScript has run and the form is ready for interaction.

    Args:
        page: Playwright page object.
        timeout: Maximum time to wait in milliseconds.

    """
    page.wait_for_selector("#loginForm[data-initialized='true']", timeout=timeout)


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


def register_user(page: Any, username: str | None = None) -> tuple[str, str]:
    """Register a new user on the application.

    Navigates to the registration page, fills in the form, and submits it.
    The caller should verify the redirect to the login page afterward.

    Args:
        page: Playwright page object.
        username: Optional username. If not provided, a unique one is generated.

    Returns:
        A tuple of (username, email) that was used for registration.

    """
    if username is None:
        username = generate_unique_username()
    email = f"{username}@test.com"
    password = "SecurePass123!"
    full_name = "Test User"

    page.goto(f"{BASE_URL}/register")
    wait_for_register_form(page)

    page.locator("#username").fill(username)
    page.locator("#email").fill(email)
    page.locator("#full_name").fill(full_name)
    page.locator("#password").fill(password)
    page.locator("#confirm_password").fill(password)
    page.locator("#register-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/login")

    return username, email


def login_user(page: Any, username: str, password: str = "SecurePass123!") -> None:
    """Log in an existing user.

    Assumes the page is already on the login page (or navigates to it).
    Fills in the credentials and submits the form. The caller should
    verify the redirect to the home page afterward.

    Args:
        page: Playwright page object.
        username: The username to log in with.
        password: The password to log in with.

    """
    if "/login" not in page.url:
        page.goto(f"{BASE_URL}/login")
    wait_for_login_form(page)

    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#login-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/")


def register_and_login(page: Any) -> str:
    """Register a new user and immediately log in.

    Convenience helper that combines registration and login in one call.

    Args:
        page: Playwright page object.

    Returns:
        The username that was registered and logged in.

    """
    username, _ = register_user(page)
    login_user(page, username)
    return username


def logout_user(page: Any, username: str) -> None:
    """Log out the current user via the navbar dropdown.

    Uses JavaScript to force-open the user dropdown (hover is unreliable
    in headless browsers), then clicks the logout link.

    Args:
        page: Playwright page object.
        username: The username of the logged-in user (used to locate the dropdown).

    """
    page.evaluate("""
      const menu = document.getElementById('user-menu');
      const toggle = menu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
      if (menu && toggle) {
        menu.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
      }
    """)
    page.wait_for_selector("#user-menu.is-open", state="visible", timeout=5000)
    page.locator('a[role="menuitem"][aria-label="Logout"]').click()
    # After logout, the app redirects: / → 401 → /login?redirect=/
    import re

    page.wait_for_url(re.compile(r"/login"), timeout=10000)


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------


def open_analysis_dropdown(page: Any) -> None:
    """Force-open the ANALYSIS navigation dropdown via JavaScript.

    Args:
        page: Playwright page object.

    """
    page.evaluate("""
      const analysisMenu = document.getElementById('analysis-menu');
      const analysisToggle = analysisMenu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
      if (analysisMenu && analysisToggle) {
        analysisMenu.classList.add('is-open');
        analysisToggle.setAttribute('aria-expanded', 'true');
      }
    """)


def open_code_reuse_submenu(page: Any) -> None:
    """Force-open the CODE REUSE sub-menu within the ANALYSIS dropdown.

    Args:
        page: Playwright page object.

    """
    page.evaluate("""
      const codeReuseMenu = document.getElementById('code-reuse-menu');
      const codeReuseToggle = codeReuseMenu?.closest('.nav-dropdown-sub')?.querySelector('.nav-dropdown-sub-toggle');
      if (codeReuseMenu && codeReuseToggle) {
        codeReuseMenu.classList.add('is-open');
        codeReuseToggle.setAttribute('aria-expanded', 'true');
      }
    """)


def open_system_dropdown(page: Any) -> None:
    """Open the SYSTEM navigation dropdown via hover.

    Args:
        page: Playwright page object.

    """
    system_toggle = page.locator('button:has-text("SYSTEM")')
    system_toggle.hover()
    page.wait_for_selector("#system-menu.is-open", state="visible", timeout=5000)


def open_user_dropdown(page: Any, username: str) -> None:
    """Open the user profile dropdown via hover.

    Args:
        page: Playwright page object.
        username: The username of the logged-in user.

    """
    user_toggle = page.locator(f"button:has-text('{username.upper()}')")
    user_toggle.hover()
    page.wait_for_selector("#user-menu.is-open", state="visible", timeout=5000)
