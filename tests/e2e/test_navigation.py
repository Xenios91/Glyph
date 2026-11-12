# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for application navigation.

Tests navigation elements, category dropdown menus, and page transitions.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import (
    BASE_URL,
    open_nav_dropdown,
    register_and_login,
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

    def test_navbar_logo_navigates_to_home(self, page: Any, server: Any) -> None:
        """Test clicking the navbar logo navigates to the home page."""
        register_and_login(page)

        # Navigate away from home
        page.goto(f"{BASE_URL}/profile")

        # Click the logo (the HOME link was removed as a duplicate of the logo)
        page.locator(".nav-logo").click()
        page.wait_for_url(f"{BASE_URL}/")

        expect(page).to_have_title("Glyph")

    def test_navbar_shows_category_dropdowns(self, page: Any, server: Any) -> None:
        """Test that the authenticated navbar shows the three category dropdowns."""
        register_and_login(page)

        # Each category dropdown toggle is visible in the navbar
        for label in ("BINARIES", "MACHINE LEARNING", "SCANNING"):
            toggle = page.locator(f".nav-dropdown-toggle:has-text('{label}')")
            expect(toggle).to_be_visible()

    def test_binaries_dropdown_shows_menu_items(self, page: Any, server: Any) -> None:
        """Test that the BINARIES dropdown shows library and similarity items."""
        register_and_login(page)

        # Use JS to force open the BINARIES dropdown (hover unreliable in headless)
        open_nav_dropdown(page, "binaries-menu")
        page.wait_for_selector("#binaries-menu.is-open", state="visible", timeout=5000)

        # Check menu items are visible
        library_link = page.locator('a[role="menuitem"][aria-label="Binary Library"]')
        expect(library_link).to_be_visible()

        similarity_link = page.locator('a[role="menuitem"][aria-label="Binary Similarity Dashboard"]')
        expect(similarity_link).to_be_visible()

    def test_machine_learning_dropdown_shows_menu_items(self, page: Any, server: Any) -> None:
        """Test that the MACHINE LEARNING dropdown shows model and prediction items."""
        register_and_login(page)

        open_nav_dropdown(page, "machine-learning-menu")
        page.wait_for_selector("#machine-learning-menu.is-open", state="visible", timeout=5000)

        create_model_link = page.locator('a[role="menuitem"][aria-label="Create Model"]')
        expect(create_model_link).to_be_visible()

        models_link = page.locator('a[role="menuitem"][aria-label="Models"]')
        expect(models_link).to_be_visible()

        predictions_link = page.locator('a[role="menuitem"][aria-label="View Predictions"]')
        expect(predictions_link).to_be_visible()

    def test_scanning_dropdown_shows_menu_items(self, page: Any, server: Any) -> None:
        """Test that the SCANNING dropdown shows both scanner items."""
        register_and_login(page)

        open_nav_dropdown(page, "scanning-menu")
        page.wait_for_selector("#scanning-menu.is-open", state="visible", timeout=5000)

        dangerous_link = page.locator('a[role="menuitem"][aria-label="Scan for Dangerous Functions"]')
        expect(dangerous_link).to_be_visible()

        behavioral_link = page.locator('a[role="menuitem"][aria-label="Behavioral Scan"]')
        expect(behavioral_link).to_be_visible()

    def test_navbar_shows_top_level_config_link(self, page: Any, server: Any) -> None:
        """Test that CONFIG is a top-level navbar link (the single-item
        SYSTEM dropdown was removed to de-duplicate the nav)."""
        register_and_login(page)

        # CONFIG is a direct top-level link, not inside a dropdown
        config_link = page.locator('a[aria-label="Configuration"]')
        expect(config_link).to_be_visible()
        expect(config_link).to_have_attribute("href", "/config")

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

    def test_navigation_to_models_via_machine_learning_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to models page via the MACHINE LEARNING dropdown MODELS item."""
        register_and_login(page)

        open_nav_dropdown(page, "machine-learning-menu")
        page.wait_for_selector("#machine-learning-menu.is-open", state="visible", timeout=5000)
        models_link = page.locator('a[role="menuitem"][aria-label="Models"]')
        models_link.click()
        page.wait_for_url(f"{BASE_URL}/getModels")

        expect(page).to_have_title("Models List")

    def test_navigation_to_predictions_via_machine_learning_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to predictions page via the MACHINE LEARNING dropdown
        PREDICTIONS item."""
        register_and_login(page)

        open_nav_dropdown(page, "machine-learning-menu")
        page.wait_for_selector("#machine-learning-menu.is-open", state="visible", timeout=5000)
        predictions_link = page.locator('a[role="menuitem"][aria-label="View Predictions"]')
        predictions_link.click()
        page.wait_for_url(f"{BASE_URL}/getPredictions")

        expect(page).to_have_title("Predictions List")

    def test_navigation_to_config_via_top_level(self, page: Any, server: Any) -> None:
        """Test navigating to the config page via the top-level CONFIG link."""
        register_and_login(page)

        config_link = page.locator('a[aria-label="Configuration"]')
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

    def test_navigation_to_binary_library_via_binaries_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to binary library via the BINARIES dropdown."""
        register_and_login(page)

        # Use JS to force open BINARIES dropdown
        open_nav_dropdown(page, "binaries-menu")
        page.wait_for_selector("#binaries-menu.is-open", state="visible", timeout=5000)
        library_link = page.locator('a[role="menuitem"][aria-label="Binary Library"]')
        library_link.click()
        page.wait_for_url(f"{BASE_URL}/binary-library")

        expect(page).to_have_title("Glyph - Binary Library")

    def test_navigation_to_create_model_via_machine_learning_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to create model page via the MACHINE LEARNING dropdown."""
        register_and_login(page)

        # Use JS to force open the MACHINE LEARNING dropdown
        open_nav_dropdown(page, "machine-learning-menu")
        page.wait_for_selector("#machine-learning-menu.is-open", state="visible", timeout=5000)
        create_model_link = page.locator('a[role="menuitem"][aria-label="Create Model"]')
        create_model_link.click()
        page.wait_for_url(f"{BASE_URL}/create-model")

        expect(page).to_have_title("Glyph - Create Model")

    def test_navigation_to_dangerous_functions_via_scanning_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to dangerous functions page via the SCANNING dropdown."""
        register_and_login(page)

        # Use JS to force open SCANNING dropdown
        open_nav_dropdown(page, "scanning-menu")
        page.wait_for_selector("#scanning-menu.is-open", state="visible", timeout=5000)
        dangerous_link = page.locator('a[role="menuitem"][aria-label="Scan for Dangerous Functions"]')
        dangerous_link.click()
        page.wait_for_url(f"{BASE_URL}/getDangerousFunctions")

        expect(page).to_have_title("Glyph - Dangerous Function Scanner")

    def test_navigation_to_similarity_dashboard_via_binaries_dropdown(self, page: Any, server: Any) -> None:
        """Test navigating to similarity dashboard via the BINARIES dropdown."""
        register_and_login(page)

        # Use JS to force open BINARIES dropdown
        open_nav_dropdown(page, "binaries-menu")
        page.wait_for_selector("#binaries-menu.is-open", state="visible", timeout=5000)
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
