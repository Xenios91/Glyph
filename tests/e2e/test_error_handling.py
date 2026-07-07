# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for error handling and edge cases.

Tests error pages, 404 handling, and edge case scenarios in the UI.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestErrorPage:
    """Tests for the error page."""

    def test_error_page_loads(self, page: Any, server: Any) -> None:
        """Test that the error page loads with correct title."""
        page.goto(f"{BASE_URL}/error")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Error")

    def test_error_page_shows_default_message(self, page: Any, server: Any) -> None:
        """Test that the error page shows a default error message."""
        page.goto(f"{BASE_URL}/error")
        page.wait_for_load_state("networkidle")

        # Should show an error message
        error_content = page.locator(".content")
        expect(error_content).to_be_visible()

    def test_error_page_with_upload_error_type(self, page: Any, server: Any) -> None:
        """Test that the error page shows upload error message for uploadError type."""
        page.goto(f"{BASE_URL}/error?type=uploadError")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Error")
        # Should mention binary/ELF type error
        expect(page.locator("body")).to_contain_text("ELF")


class TestNonExistentResources:
    """Tests for accessing non-existent resources."""

    def test_nonexistent_binary_detail_redirects_or_errors(self, page: Any, server: Any) -> None:
        """Test that accessing a non-existent binary detail page handles gracefully."""
        register_and_login(page)

        # Try to access a binary that doesn't exist
        page.goto(f"{BASE_URL}/binary/99999")
        page.wait_for_load_state("networkidle")

        # Should either redirect or show an error, not crash
        assert page.url.startswith(BASE_URL)

    def test_nonexistent_task_results_handles_gracefully(self, page: Any, server: Any) -> None:
        """Test that accessing non-existent task results handles gracefully."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/task-results?task_uuid=non-existent-uuid")
        page.wait_for_load_state("networkidle")

        # Page should load without crashing
        expect(page).to_have_title("Glyph - Task Results")


class TestNavigationErrorHandling:
    """Tests for error handling during navigation."""

    def test_navigating_after_logout_works(self, page: Any, server: Any) -> None:
        """Test that navigation works correctly after logout."""
        register_and_login(page)

        # Logout
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

        import re

        page.wait_for_url(re.compile(r"/login"), timeout=10000)

        # Try to navigate to a protected page - should redirect to login
        page.goto(f"{BASE_URL}/binary-library", wait_until="commit")
        page.wait_for_load_state("networkidle")

        # Should be on login page or show authentication required
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Binary Library"

    def test_concurrent_page_loads(self, page: Any, server: Any) -> None:
        """Test that rapid page navigation doesn't break the UI."""
        register_and_login(page)

        # Rapidly navigate between pages
        pages = [
            f"{BASE_URL}/",
            f"{BASE_URL}/profile",
            f"{BASE_URL}/config",
            f"{BASE_URL}/getModels",
            f"{BASE_URL}/getPredictions",
        ]

        for url in pages:
            page.goto(url, wait_until="commit")
            page.wait_for_load_state("networkidle")
            # Page should have loaded without errors
            assert page.url.startswith(BASE_URL)
