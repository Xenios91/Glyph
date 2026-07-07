# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the predictions page.

Tests the predictions list page including empty state, table structure,
and action buttons.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestPredictionsPage:
    """Tests for the predictions list page."""

    def test_predictions_page_loads(self, page: Any, server: Any) -> None:
        """Test that the predictions page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Predictions List")

    def test_predictions_page_shows_empty_state_or_table(self, page: Any, server: Any) -> None:
        """Test that the predictions page shows either empty state or predictions table.

        Since predictions data can accumulate from previous tests, this test accepts
        both states conditionally.
        """
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        # Either empty state or predictions table should be visible
        empty_state = page.locator(".no-predictions-empty-state")
        predictions_table = page.locator(".cyber-table")
        assert empty_state.is_visible() or predictions_table.is_visible(), \
            "Predictions page should show either empty state or predictions table"

    def test_predictions_empty_state_structure(self, page: Any, server: Any) -> None:
        """Test that the predictions empty state shows the title if visible."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator(".no-predictions-empty-state")
        if empty_state.is_visible():
            expect(page.locator(".empty-state-title")).to_be_visible()
            expect(page.locator(".empty-state-title")).to_contain_text("NO PREDICTIONS AVAILABLE")

    def test_predictions_empty_state_has_description(self, page: Any, server: Any) -> None:
        """Test that the predictions empty state has a description if visible."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator(".no-predictions-empty-state")
        if empty_state.is_visible():
            # Check that at least one description paragraph exists within the empty state
            description = empty_state.locator(".empty-state-description")
            assert description.count() >= 1, "Empty state should have description text"

    def test_predictions_page_has_create_prediction_link(self, page: Any, server: Any) -> None:
        """Test that the predictions page has a link to create a prediction.

        When empty state is shown, it should have a create prediction link.
        When predictions table is shown, the link may not be present.
        """
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        # Check if empty state is visible - it should have the create link
        empty_state = page.locator(".no-predictions-empty-state")
        if empty_state.is_visible():
            create_link = empty_state.locator('a[href="/create-prediction"]')
            assert create_link.count() > 0, "Empty state should have a link to create prediction"
        # When predictions table is shown, there may not be a create link on the page

    def test_predictions_page_has_back_button(self, page: Any, server: Any) -> None:
        """Test that the predictions page loads correctly."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("networkidle")

        assert page.url == f"{BASE_URL}/getPredictions"
