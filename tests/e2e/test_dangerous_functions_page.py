# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the dangerous functions scanner page.

Tests that the dangerous functions scanner page loads correctly and displays
the expected UI elements for scanning binaries for insecure functions.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestDangerousFunctionsPage:
    """Tests for the dangerous functions scanner page."""

    def test_dangerous_functions_page_loads(self, page: Any, server: Any) -> None:
        """Test that the dangerous functions page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Dangerous Function Scanner")

    def test_dangerous_functions_shows_scanner_controls(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows the control elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check target type selector
        expect(page.locator("#scan-target-type")).to_be_visible()

        # Check target selector
        expect(page.locator("#scan-target-select")).to_be_visible()

        # Check scan button
        expect(page.locator("#scan-btn")).to_be_visible()

        # Check go back button
        expect(page.locator(".back-btn")).to_be_visible()

    def test_dangerous_functions_has_target_type_options(self, page: Any, server: Any) -> None:
        """Test that the scanner page has all three target type options."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check the target type dropdown has the expected options
        target_type = page.locator("#scan-target-type")
        options = target_type.locator("option")
        option_count = options.count()
        assert option_count == 3, f"Expected 3 target type options, got {option_count}"

    def test_dangerous_functions_shows_description(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows a description text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check description paragraph exists
        expect(page.locator(".scanner-description")).to_be_visible()
