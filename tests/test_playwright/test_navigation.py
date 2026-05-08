# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for application navigation.

Tests navigation elements, dropdown menus, and page transitions.
"""

import time
from typing import Any

from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


def generate_unique_username() -> str:
    """Generate a unique username for testing."""
    timestamp = int(time.time() * 1000) % 100000
    return f"testuser_{timestamp}"


def register_and_login(page: Any) -> str:
    """Helper to register a new user and login. Returns the username."""
    username = generate_unique_username()
    email = f"{username}@test.com"

    # Register
    page.goto(f"{BASE_URL}/register")
    page.locator("#username").fill(username)
    page.locator("#email").fill(email)
    page.locator("#password").fill("SecurePass123!")
    page.locator("#confirm_password").fill("SecurePass123!")
    page.locator("#register-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/login")

    # Login
    page.locator("#username").fill(username)
    page.locator("#password").fill("SecurePass123!")
    page.locator("#login-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/")

    return username


class TestUnauthenticatedNavigation:
    """Tests for navigation when user is not logged in."""

    def test_navbar_shows_login_and_register_links(self, page: Any, server: Any) -> None:
        """Test that unauthenticated users see login and register links."""
        page.goto(f"{BASE_URL}/login")

        # Check login link in navbar
        login_link = page.locator('a[aria-label="Login"]')
        expect(login_link).to_be_visible()

        # Check register link in navbar
        register_link = page.locator('a[aria-label="Register"]')
        expect(register_link).to_be_visible()

    def test_navbar_logo_links_to_home(self, page: Any, server: Any) -> None:
        """Test that the navbar logo links to the home page."""
        page.goto(f"{BASE_URL}/login")

        # Click the logo
        page.locator(".nav-logo").click()

        # Should redirect to login since not authenticated
        # (home page requires authentication)
        expect(page).to_have_title("Glyph - Login")


class TestAuthenticatedNavigation:
    """Tests for navigation when user is logged in."""

    def test_navbar_shows_user_menu_after_login(self, page: Any, server: Any) -> None:
        """Test that authenticated users see the user menu."""
        username = register_and_login(page)

        # Check that user dropdown is visible
        user_dropdown = page.locator(f"button:has-text('{username.upper()}')")
        expect(user_dropdown).to_be_visible()

    def test_home_link_navigates_to_home(self, page: Any, server: Any) -> None:
        """Test clicking HOME link navigates to home page."""
        register_and_login(page)

        # Navigate away from home
        page.goto(f"{BASE_URL}/profile")

        # Click HOME link
        page.locator('a[aria-label="Home"]').click()
        page.wait_for_url(f"{BASE_URL}/")

        expect(page).to_have_title("Glyph")

    def test_analysis_dropdown_shows_menu_items(self, page: Any, server: Any) -> None:
        """Test that the ANALYSIS dropdown shows menu items."""
        register_and_login(page)

        # Click the ANALYSIS dropdown toggle
        page.locator('button:has-text("ANALYSIS")').click()

        # Wait for dropdown to open and check menu items
        upload_link = page.locator('a[role="menuitem"][aria-label="Upload Binary"]')
        expect(upload_link).to_be_visible()

        models_link = page.locator('a[role="menuitem"][aria-label="Models"]')
        expect(models_link).to_be_visible()

        predictions_link = page.locator('a[role="menuitem"][aria-label="View Predictions"]')
        expect(predictions_link).to_be_visible()

    def test_system_dropdown_shows_config(self, page: Any, server: Any) -> None:
        """Test that the SYSTEM dropdown shows configuration link."""
        register_and_login(page)

        # Click the SYSTEM dropdown toggle
        page.locator('button:has-text("SYSTEM")').click()

        # Wait for dropdown to open and check config link
        config_link = page.locator('a[role="menuitem"][aria-label="Configuration"]')
        expect(config_link).to_be_visible()

    def test_user_dropdown_shows_profile_and_logout(self, page: Any, server: Any) -> None:
        """Test that the user dropdown shows profile and logout links."""
        username = register_and_login(page)

        # Click the user dropdown toggle
        page.locator(f"button:has-text('{username.upper()}')").click()

        # Check profile link
        profile_link = page.locator('a[role="menuitem"][aria-label="View Profile"]')
        expect(profile_link).to_be_visible()

        # Check logout link
        logout_link = page.locator('a[role="menuitem"][aria-label="Logout"]')
        expect(logout_link).to_be_visible()

    def test_navigation_to_upload_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to upload page via the ANALYSIS dropdown."""
        register_and_login(page)

        # Open ANALYSIS dropdown
        page.locator('button:has-text("ANALYSIS")').click()

        # Click UPLOAD link
        page.locator('a[role="menuitem"][aria-label="Upload Binary"]').click()
        page.wait_for_url(f"{BASE_URL}/uploadBinary")

        expect(page).to_have_title("Glyph - Upload Binary")

    def test_navigation_to_models_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to models page via the ANALYSIS dropdown."""
        register_and_login(page)

        # Open ANALYSIS dropdown
        page.locator('button:has-text("ANALYSIS")').click()

        # Click MODELS link
        page.locator('a[role="menuitem"][aria-label="Models"]').click()
        page.wait_for_url(f"{BASE_URL}/getModels")

        expect(page).to_have_title("Models List")

    def test_navigation_to_config_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to config page via the SYSTEM dropdown."""
        register_and_login(page)

        # Open SYSTEM dropdown
        page.locator('button:has-text("SYSTEM")').click()

        # Click CONFIG link
        page.locator('a[role="menuitem"][aria-label="Configuration"]').click()
        page.wait_for_url(f"{BASE_URL}/config")

        expect(page).to_have_title("Glyph - Configuration")

    def test_navigation_to_profile_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to profile page via the user dropdown."""
        username = register_and_login(page)

        # Open user dropdown
        page.locator(f"button:has-text('{username.upper()}')").click()

        # Click PROFILE link
        page.locator('a[role="menuitem"][aria-label="View Profile"]').click()
        page.wait_for_url(f"{BASE_URL}/profile")

        expect(page).to_have_title("Glyph - Profile")


class TestRedirectBehavior:
    """Tests for redirect behavior on protected routes."""

    def test_login_redirects_to_home_when_authenticated(self, page: Any, server: Any) -> None:
        """Test that accessing /login while logged in redirects to home."""
        register_and_login(page)

        # Try to access login page
        page.goto(f"{BASE_URL}/login")
        page.wait_for_url(f"{BASE_URL}/")

        expect(page).to_have_title("Glyph")

    def test_register_redirects_to_home_when_authenticated(self, page: Any, server: Any) -> None:
        """Test that accessing /register while logged in redirects to home."""
        register_and_login(page)

        # Try to access register page
        page.goto(f"{BASE_URL}/register")
        page.wait_for_url(f"{BASE_URL}/")

        expect(page).to_have_title("Glyph")
