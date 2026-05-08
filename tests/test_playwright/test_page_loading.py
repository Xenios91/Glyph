# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for page loading.

Tests that all application pages load correctly with expected content.
"""

from typing import Any

from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


class TestPublicPageLoading:
    """Tests for pages accessible without authentication."""

    def test_login_page_loads(self, page: Any, server: Any) -> None:
        """Test that the login page loads with all required elements."""
        page.goto(f"{BASE_URL}/login")

        # Check page title
        expect(page).to_have_title("Glyph - Login")

        # Check login form is present
        expect(page.locator("#loginForm")).to_be_visible()

        # Check login title
        expect(page.locator("#login-title")).to_be_visible()
        expect(page.locator("#login-title")).to_have_text("LOGIN")

        # Check form inputs
        expect(page.locator("#username")).to_be_visible()
        expect(page.locator("#password")).to_be_visible()

        # Check submit button
        expect(page.locator("#login-submit-btn")).to_be_visible()

    def test_register_page_loads(self, page: Any, server: Any) -> None:
        """Test that the registration page loads with all required elements."""
        page.goto(f"{BASE_URL}/register")

        # Check page title
        expect(page).to_have_title("Glyph - Register")

        # Check registration form is present
        expect(page.locator("#registerForm")).to_be_visible()

        # Check register title
        expect(page.locator("#register-title")).to_be_visible()
        expect(page.locator("#register-title")).to_have_text("REGISTER")

        # Check form inputs
        expect(page.locator("#username")).to_be_visible()
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#full_name")).to_be_visible()
        expect(page.locator("#password")).to_be_visible()
        expect(page.locator("#confirm_password")).to_be_visible()

        # Check submit button
        expect(page.locator("#register-submit-btn")).to_be_visible()

        # Check link to login page
        expect(page.locator('.auth-links a[href="/login"]')).to_be_visible()

    def test_login_page_has_register_link(self, page: Any, server: Any) -> None:
        """Test that the login page has a link to the registration page."""
        page.goto(f"{BASE_URL}/login")

        # Check link to register page
        register_link = page.locator('.auth-links a[href="/register"]')
        expect(register_link).to_be_visible()

    def test_register_page_has_login_link(self, page: Any, server: Any) -> None:
        """Test that the register page has a link to the login page."""
        page.goto(f"{BASE_URL}/register")

        # Check link to login page
        login_link = page.locator('.auth-links a[href="/login"]')
        expect(login_link).to_be_visible()

    def test_navigation_to_login_from_register(self, page: Any, server: Any) -> None:
        """Test navigating from register page to login page."""
        page.goto(f"{BASE_URL}/register")

        # Click the login link
        page.locator('.auth-links a[href="/login"]').click()
        page.wait_for_url(f"{BASE_URL}/login")

        expect(page).to_have_title("Glyph - Login")

    def test_navigation_to_register_from_login(self, page: Any, server: Any) -> None:
        """Test navigating from login page to register page."""
        page.goto(f"{BASE_URL}/login")

        # Click the register link
        page.locator('.auth-links a[href="/register"]').click()
        page.wait_for_url(f"{BASE_URL}/register")

        expect(page).to_have_title("Glyph - Register")
