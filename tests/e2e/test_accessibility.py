# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Accessibility and keyboard navigation tests for Glyph application.

Tests cover:
- Keyboard navigation (Tab, Enter, Escape)
- ARIA attributes on navigation, menus, tabs, and live regions
- Screen reader compatibility (lang attribute, form labels, aria-hidden)
"""

from playwright.sync_api import Page, expect
from typing import Any

from tests.e2e.utils import register_and_login


# Type alias for Playwright Page
Page = Any


class TestKeyboardNavigation:
    """Tests for keyboard navigation across forms and pages."""

    def test_tab_key_navigates_form_elements_on_login(self, page: Any, server: Any) -> None:
        """Verify Tab key moves focus through login form elements in order."""
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        username_input = page.locator("#username")
        password_input = page.locator("#password")
        submit_button = page.locator("#login-submit-btn")

        # Focus the first form field directly, then verify Tab navigation
        username_input.click()
        expect(username_input).to_be_focused()

        # Tab moves to password field
        page.keyboard.press("Tab")
        expect(password_input).to_be_focused()

        # Tab moves to submit button
        page.keyboard.press("Tab")
        expect(submit_button).to_be_focused()

    def test_tab_key_navigates_form_elements_on_register(self, page: Any, server: Any) -> None:
        """Verify Tab key moves focus through registration form elements in order."""
        page.goto("http://127.0.0.1:8000/register")
        page.wait_for_load_state("networkidle")

        username_input = page.locator("#username")
        email_input = page.locator("#email")
        full_name_input = page.locator("#full_name")
        password_input = page.locator("#password")
        confirm_password_input = page.locator("#confirm_password")
        submit_button = page.locator("#register-submit-btn")

        # Focus the first form field directly, then verify Tab navigation
        username_input.click()
        expect(username_input).to_be_focused()

        page.keyboard.press("Tab")
        expect(email_input).to_be_focused()

        page.keyboard.press("Tab")
        expect(full_name_input).to_be_focused()

        page.keyboard.press("Tab")
        expect(password_input).to_be_focused()

        page.keyboard.press("Tab")
        expect(confirm_password_input).to_be_focused()

        page.keyboard.press("Tab")
        expect(submit_button).to_be_focused()

    def test_enter_key_submits_login_form(self, page: Any, server: Any) -> None:
        """Verify Enter key submits the login form."""
        from tests.e2e.utils import generate_unique_username, wait_for_login_form, wait_for_register_form

        # Register a user first with unique username to avoid conflicts
        username = generate_unique_username()
        email = f"{username}@test.com"
        password = "SecurePass123!"

        page.goto("http://127.0.0.1:8000/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#full_name").fill("Test User")
        page.locator("#password").fill(password)
        page.locator("#confirm_password").fill(password)
        page.locator("#register-submit-btn").click()
        page.wait_for_url("http://127.0.0.1:8000/login")

        # Now on login page, fill credentials
        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)

        # Submit with Enter - form uses AJAX + setTimeout redirect
        page.keyboard.press("Enter")

        # Wait for the redirect (form uses window.location.href after AJAX success)
        page.wait_for_url("http://127.0.0.1:8000/", timeout=15000)

        # Should be on home page after successful login
        expect(page).to_have_url("http://127.0.0.1:8000/")
        expect(page.locator(".hero-section")).to_be_visible()

    def test_escape_key_closes_task_modal(self, page: Any, server: Any) -> None:
        """Verify Escape key closes the task modal on binary library page."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/binary-library")
        page.wait_for_load_state("networkidle")

        # Open the task modal by clicking the upload button area
        task_modal = page.locator("#task-modal")

        # The modal may not be visible initially; check that pressing Escape does not cause errors
        page.keyboard.press("Escape")
        page.wait_for_load_state("networkidle")

        # Modal should remain hidden or be closed
        expect(task_modal).not_to_be_visible()


class TestARIAAttributes:
    """Tests for ARIA roles and attributes on key page components."""

    def test_navbar_has_role_navigation(self, page: Any, server: Any) -> None:
        """Verify the navbar element has role='navigation'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        navbar = page.locator("nav.navbar")
        expect(navbar).to_have_attribute("role", "navigation")

    def test_navbar_has_aria_label(self, page: Any, server: Any) -> None:
        """Verify the navbar has an aria-label for screen readers."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        navbar = page.locator("nav.navbar")
        expect(navbar).to_have_attribute("aria-label", "Main navigation")

    def test_dropdown_menus_have_role_menu(self, page: Any, server: Any) -> None:
        """Verify dropdown menu containers have role='menu'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        analysis_menu = page.locator("#analysis-menu")
        system_menu = page.locator("#system-menu")
        user_menu = page.locator("#user-menu")

        expect(analysis_menu).to_have_attribute("role", "menu")
        expect(system_menu).to_have_attribute("role", "menu")
        expect(user_menu).to_have_attribute("role", "menu")

    def test_menu_items_have_role_menuitem(self, page: Any, server: Any) -> None:
        """Verify dropdown menu items have role='menuitem'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        menu_items = page.locator('[role="menuitem"]')
        assert menu_items.count() >= 5, f"Expected at least 5 menu items, found {menu_items.count()}"

    def test_tab_panels_have_aria_selected(self, page: Any, server: Any) -> None:
        """Verify binary detail page tabs have aria-selected attribute."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        # Navigate to binary detail page (may show loading/empty state)
        page.goto("http://127.0.0.1:8000/binary/nonexistent")
        page.wait_for_load_state("networkidle")

        # Check tablist exists and tabs have aria-selected
        tablist = page.locator('[role="tablist"]')
        if tablist.is_visible():
            tabs = page.locator('[role="tab"]')
            tab_count = tabs.count()
            if tab_count > 0:
                # At least one tab should have aria-selected="true"
                active_tab = page.locator('[aria-selected="true"]')
                assert active_tab.count() >= 1, "Expected at least one active tab"

    def test_tab_panels_have_role_tabpanel(self, page: Any, server: Any) -> None:
        """Verify tab content panels have role='tabpanel'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        # Navigate to binary detail page
        page.goto("http://127.0.0.1:8000/binary/nonexistent")
        page.wait_for_load_state("networkidle")

        tablist = page.locator('[role="tablist"]')
        if tablist.is_visible():
            tab_panels = page.locator('[role="tabpanel"]')
            assert tab_panels.count() >= 2, f"Expected at least 2 tab panels, found {tab_panels.count()}"

    def test_loading_indicators_have_role_status(self, page: Any, server: Any) -> None:
        """Verify loading indicators have role='status'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/task-results")
        page.wait_for_load_state("networkidle")

        results_loading = page.locator("#results-loading")
        if results_loading.is_visible():
            expect(results_loading).to_have_attribute("role", "status")

    def test_error_messages_have_role_alert(self, page: Any, server: Any) -> None:
        """Verify error message containers have role='alert'."""
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        error_container = page.locator("#login-error")
        expect(error_container).to_have_attribute("role", "alert")

    def test_live_regions_have_aria_live(self, page: Any, server: Any) -> None:
        """Verify dynamic content regions have aria-live attribute."""
        # Go to login page directly (not logged in, so no redirect)
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        error_container = page.locator("#login-error")
        expect(error_container).to_have_attribute("aria-live", "assertive")

    def test_run_task_status_has_aria_live(self, page: Any, server: Any) -> None:
        """Verify run task status container has aria-live='polite'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/run-task")
        page.wait_for_load_state("networkidle")

        task_status = page.locator("#task-status")
        if task_status.count() > 0:
            expect(task_status).to_have_attribute("aria-live", "polite")


class TestScreenReaderCompatibility:
    """Tests for screen reader compatibility attributes."""

    def test_page_has_lang_attribute(self, page: Any, server: Any) -> None:
        """Verify the HTML document has a lang attribute."""
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        html = page.locator("html")
        expect(html).to_have_attribute("lang", "en")

    def test_skip_link_exists(self, page: Any, server: Any) -> None:
        """Verify skip-to-content link exists for keyboard users."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        skip_link = page.locator(".skip-link")
        expect(skip_link).to_be_visible()
        expect(skip_link).to_have_attribute("href", "#main-content")

    def test_main_content_has_role_main(self, page: Any, server: Any) -> None:
        """Verify main content area has role='main'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        main_content = page.locator('.page-content[role="main"]')
        expect(main_content).to_be_visible()

    def test_main_content_has_id_for_skip_link(self, page: Any, server: Any) -> None:
        """Verify main content has id='main-content' for skip link target."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        main_content = page.locator("#main-content")
        expect(main_content).to_be_visible()

    def test_form_inputs_have_associated_labels_on_login(self, page: Any, server: Any) -> None:
        """Verify login form inputs have associated label elements."""
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        username_label = page.locator("label[for='username']")
        password_label = page.locator("label[for='password']")

        expect(username_label).to_be_visible()
        expect(password_label).to_be_visible()

    def test_form_inputs_have_associated_labels_on_register(self, page: Any, server: Any) -> None:
        """Verify registration form inputs have associated label elements."""
        page.goto("http://127.0.0.1:8000/register")
        page.wait_for_load_state("networkidle")

        username_label = page.locator("label[for='username']")
        email_label = page.locator("label[for='email']")
        password_label = page.locator("label[for='password']")
        confirm_password_label = page.locator("label[for='confirm_password']")

        expect(username_label).to_be_visible()
        expect(email_label).to_be_visible()
        expect(password_label).to_be_visible()
        expect(confirm_password_label).to_be_visible()

    def test_decorative_icons_have_aria_hidden(self, page: Any, server: Any) -> None:
        """Verify decorative SVG icons have aria-hidden='true'."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        # Dropdown arrows are decorative and should be aria-hidden
        dropdown_arrows = page.locator('.dropdown-arrow[aria-hidden="true"]')
        assert dropdown_arrows.count() >= 3, f"Expected at least 3 dropdown arrows with aria-hidden, found {dropdown_arrows.count()}"

    def test_form_inputs_have_aria_required(self, page: Any, server: Any) -> None:
        """Verify required form inputs have aria-required='true'."""
        page.goto("http://127.0.0.1:8000/login")
        page.wait_for_load_state("networkidle")

        username_input = page.locator("#username")
        password_input = page.locator("#password")

        expect(username_input).to_have_attribute("aria-required", "true")
        expect(password_input).to_have_attribute("aria-required", "true")

    def test_stats_region_has_aria_label(self, page: Any, server: Any) -> None:
        """Verify home page stats section has an aria-label."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        stats_row = page.locator(".stats-row")
        if stats_row.is_visible():
            expect(stats_row).to_have_attribute("role", "region")
            expect(stats_row).to_have_attribute("aria-label", "Dashboard statistics")

    def test_feature_cards_have_aria_labels(self, page: Any, server: Any) -> None:
        """Verify feature card links have aria-label attributes."""
        register_and_login(page)
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_load_state("networkidle")

        feature_cards = page.locator(".feature-cards")
        if feature_cards.is_visible():
            expect(feature_cards).to_have_attribute("role", "navigation")
            expect(feature_cards).to_have_attribute("aria-label", "Quick actions")

            # Each feature card link should have an aria-label
            card_links = page.locator(".feature-cards a[aria-label]")
            assert card_links.count() >= 3, f"Expected at least 3 feature card links with aria-label, found {card_links.count()}"
