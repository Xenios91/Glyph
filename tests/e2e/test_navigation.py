# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for application navigation.

Tests navigation elements, dropdown menus, and page transitions.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import (
    BASE_URL,
    generate_unique_username,
    login_user,
    open_analysis_dropdown,
    open_code_reuse_submenu,
    open_system_dropdown,
    open_user_dropdown,
    register_and_login,
    register_user,
    wait_for_login_form,
    wait_for_register_form,
)


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

        # Use JS to force open both ANALYSIS dropdown and CODE REUSE sub-menu
        # (hover unreliable in headless browser for nested sub-menus)
        page.evaluate("""
          const analysisMenu = document.getElementById('analysis-menu');
          const analysisToggle = analysisMenu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
          if (analysisMenu && analysisToggle) {
            analysisMenu.classList.add('is-open');
            analysisToggle.setAttribute('aria-expanded', 'true');
          }
          const codeReuseMenu = document.getElementById('code-reuse-menu');
          const codeReuseToggle = codeReuseMenu?.closest('.nav-dropdown-sub')?.querySelector('.nav-dropdown-sub-toggle');
          if (codeReuseMenu && codeReuseToggle) {
            codeReuseMenu.classList.add('is-open');
            codeReuseToggle.setAttribute('aria-expanded', 'true');
          }
        """)
        # Wait for sub-menu to be visible
        page.wait_for_selector("#code-reuse-menu.is-open", state="visible", timeout=5000)

        # Check menu items are visible
        library_link = page.locator('a[role="menuitem"][aria-label="Binary Library"]')
        expect(library_link).to_be_visible()

        models_link = page.locator('a[role="menuitem"][aria-label="Models"]')
        expect(models_link).to_be_visible()

        predictions_link = page.locator('a[role="menuitem"][aria-label="View Predictions"]')
        expect(predictions_link).to_be_visible()

    def test_system_dropdown_shows_config(self, page: Any, server: Any) -> None:
        """Test that the SYSTEM dropdown shows configuration link."""
        register_and_login(page)

        # Hover over the SYSTEM dropdown toggle to open via hover
        system_toggle = page.locator('button:has-text("SYSTEM")')
        system_toggle.hover()
        # Wait for the specific system menu to open
        page.wait_for_selector("#system-menu.is-open", state="visible", timeout=5000)

        # Check config link is visible
        config_link = page.locator('a[role="menuitem"][aria-label="Configuration"]')
        expect(config_link).to_be_visible()

    def test_user_dropdown_shows_profile_and_logout(self, page: Any, server: Any) -> None:
        """Test that the user dropdown shows profile and logout links."""
        username = register_and_login(page)

        # Hover over the user dropdown toggle to open via hover
        user_toggle = page.locator(f"button:has-text('{username.upper()}')")
        user_toggle.hover()
        # Wait for the specific user menu to open
        page.wait_for_selector("#user-menu.is-open", state="visible", timeout=5000)

        # Check profile link
        profile_link = page.locator('a[role="menuitem"][aria-label="View Profile"]')
        expect(profile_link).to_be_visible()

        # Check logout link
        logout_link = page.locator('a[role="menuitem"][aria-label="Logout"]')
        expect(logout_link).to_be_visible()

    def test_navigation_to_models_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to models page via the ANALYSIS dropdown."""
        register_and_login(page)

        # Use JS to force open both ANALYSIS dropdown and CODE REUSE sub-menu
        page.evaluate("""
          const analysisMenu = document.getElementById('analysis-menu');
          const analysisToggle = analysisMenu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
          if (analysisMenu && analysisToggle) {
            analysisMenu.classList.add('is-open');
            analysisToggle.setAttribute('aria-expanded', 'true');
          }
          const codeReuseMenu = document.getElementById('code-reuse-menu');
          const codeReuseToggle = codeReuseMenu?.closest('.nav-dropdown-sub')?.querySelector('.nav-dropdown-sub-toggle');
          if (codeReuseMenu && codeReuseToggle) {
            codeReuseMenu.classList.add('is-open');
            codeReuseToggle.setAttribute('aria-expanded', 'true');
          }
        """)
        page.wait_for_selector("#code-reuse-menu.is-open", state="visible", timeout=5000)
        models_link = page.locator('a[role="menuitem"][aria-label="Models"]')
        models_link.click()
        page.wait_for_url(f"{BASE_URL}/getModels")

        expect(page).to_have_title("Models List")

    def test_navigation_to_config_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to config page via the SYSTEM dropdown."""
        register_and_login(page)

        # Hover over SYSTEM dropdown to open
        system_toggle = page.locator('button:has-text("SYSTEM")')
        system_toggle.hover()
        # Wait for menu to open, then hover and click CONFIG
        page.wait_for_selector("#system-menu.is-open", state="visible", timeout=5000)
        config_link = page.locator('a[role="menuitem"][aria-label="Configuration"]')
        config_link.hover()
        config_link.click()
        page.wait_for_url(f"{BASE_URL}/config")

        expect(page).to_have_title("Glyph - Configuration")

    def test_navigation_to_profile_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to profile page via the user dropdown."""
        username = register_and_login(page)

        # Hover over user dropdown to open
        user_toggle = page.locator(f"button:has-text('{username.upper()}')")
        user_toggle.hover()
        # Wait for menu to open, then hover and click PROFILE
        page.wait_for_selector("#user-menu.is-open", state="visible", timeout=5000)
        profile_link = page.locator('a[role="menuitem"][aria-label="View Profile"]')
        profile_link.hover()
        profile_link.click()
        page.wait_for_url(f"{BASE_URL}/profile")

        expect(page).to_have_title("Glyph - Profile")

    def test_navigation_to_binary_library_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to binary library via the ANALYSIS dropdown."""
        register_and_login(page)

        # Use JS to force open ANALYSIS dropdown
        open_analysis_dropdown(page)
        page.wait_for_selector("#analysis-menu.is-open", state="visible", timeout=5000)
        library_link = page.locator('a[role="menuitem"][aria-label="Binary Library"]')
        library_link.click()
        page.wait_for_url(f"{BASE_URL}/binary-library")

        expect(page).to_have_title("Glyph - Binary Library")

    def test_navigation_to_create_model_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to create model page via ANALYSIS > CODE REUSE submenu."""
        register_and_login(page)

        # Use JS to force open both ANALYSIS dropdown and CODE REUSE sub-menu
        open_analysis_dropdown(page)
        open_code_reuse_submenu(page)
        page.wait_for_selector("#code-reuse-menu.is-open", state="visible", timeout=5000)
        create_model_link = page.locator('a[role="menuitem"][aria-label="Create Model"]')
        create_model_link.click()
        page.wait_for_url(f"{BASE_URL}/create-model")

        expect(page).to_have_title("Glyph - Create Model")

    def test_navigation_to_dangerous_functions_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to dangerous functions page via the ANALYSIS dropdown."""
        register_and_login(page)

        # Use JS to force open ANALYSIS dropdown
        open_analysis_dropdown(page)
        page.wait_for_selector("#analysis-menu.is-open", state="visible", timeout=5000)
        dangerous_link = page.locator('a[role="menuitem"][aria-label="Scan for Dangerous Functions"]')
        dangerous_link.click()
        page.wait_for_url(f"{BASE_URL}/getDangerousFunctions")

        expect(page).to_have_title("Glyph - Dangerous Function Scanner")

    def test_navigation_to_similarity_dashboard_via_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to similarity dashboard via the ANALYSIS dropdown."""
        register_and_login(page)

        # Use JS to force open ANALYSIS dropdown
        open_analysis_dropdown(page)
        page.wait_for_selector("#analysis-menu.is-open", state="visible", timeout=5000)
        similarity_link = page.locator('a[role="menuitem"][aria-label="Binary Similarity Dashboard"]')
        similarity_link.click()
        page.wait_for_url(f"{BASE_URL}/similarity-dashboard")

        expect(page).to_have_title("Glyph - Similarity Dashboard")


class TestRedirectBehavior:
    """Tests for redirect behavior on protected routes."""

    def test_login_redirects_to_home_when_authenticated(self, page: Any, server: Any) -> None:
        """Test that accessing /login while logged in redirects to home."""
        register_and_login(page)

        # Try to access login page - should redirect to home
        page.goto(f"{BASE_URL}/login")
        # Wait for page to settle
        page.wait_for_load_state("networkidle")

        # Check we ended up on home page
        expect(page).to_have_title("Glyph")

    def test_register_redirects_to_home_when_authenticated(self, page: Any, server: Any) -> None:
        """Test that accessing /register while logged in redirects to home."""
        register_and_login(page)

        # Try to access register page - should redirect to home
        page.goto(f"{BASE_URL}/register")
        # Wait for page to settle
        page.wait_for_load_state("networkidle")

        # Check we ended up on home page
        expect(page).to_have_title("Glyph")
