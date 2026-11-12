# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the home page.

Tests the authenticated home page including hero section and feature card
quick-action navigation.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestHomePage:
    """Tests for the home page layout and content."""

    def test_home_page_loads_after_login(self, page: Any, server: Any) -> None:
        """Test that the home page loads with correct title after login."""
        register_and_login(page)

        expect(page).to_have_title("Glyph")

    def test_home_shows_hero_title(self, page: Any, server: Any) -> None:
        """Test that the home page shows the hero title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#glyph-title")).to_be_visible()
        expect(page.locator("#glyph-title")).to_contain_text("GLYPH")

    def test_home_shows_hero_subtitle(self, page: Any, server: Any) -> None:
        """Test that the home page shows the hero subtitle."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".hero-subtitle")).to_be_visible()
        expect(page.locator(".hero-subtitle")).to_contain_text("binary analysis tool")

    def test_home_does_not_show_stats_section(self, page: Any, server: Any) -> None:
        """The dashboard stats row (BINARIES/MODELS/PREDICTIONS) was removed
        from the home page, so no stats markup should be present."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".stats-row")).to_have_count(0)
        expect(page.locator(".stat-card")).to_have_count(0)


class TestHomeFeatureCards:
    """Tests for the feature card quick-action navigation on the home page."""

    def test_home_shows_feature_cards_section(self, page: Any, server: Any) -> None:
        """Test that the home page shows the feature cards section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".feature-cards")).to_be_visible()
        expect(page.locator(".feature-cards")).to_have_attribute("role", "navigation")

    def test_home_shows_binary_library_card(self, page: Any, server: Any) -> None:
        """Test that the home page shows the Binary Library feature card."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Go to Binary Library"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("BINARY LIBRARY")

    def test_home_shows_code_reuse_card(self, page: Any, server: Any) -> None:
        """Test that the home page shows the Code Reuse feature card."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Create a new ML model"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("CODE REUSE")

    def test_home_shows_dangerous_functions_card(self, page: Any, server: Any) -> None:
        """Test that the home page shows the Dangerous Functions feature card."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Scan for dangerous functions"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("DANGEROUS FUNCTIONS")

    def test_binary_library_card_navigates_correctly(self, page: Any, server: Any) -> None:
        """Test that clicking the Binary Library card navigates to the library."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Go to Binary Library"]')
        expect(card).to_have_attribute("href", "/binary-library")

        card.click()
        page.wait_for_url(f"{BASE_URL}/binary-library")

        expect(page).to_have_title("Glyph - Binary Library")

    def test_code_reuse_card_navigates_correctly(self, page: Any, server: Any) -> None:
        """Test that clicking the Code Reuse card navigates to create model."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Create a new ML model"]')
        expect(card).to_have_attribute("href", "/create-model")

        card.click()
        page.wait_for_url(f"{BASE_URL}/create-model")

        expect(page).to_have_title("Glyph - Create Model")

    def test_dangerous_functions_card_navigates_correctly(self, page: Any, server: Any) -> None:
        """Test that clicking the Dangerous Functions card navigates to the scanner."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Scan for dangerous functions"]')
        expect(card).to_have_attribute("href", "/getDangerousFunctions")

        card.click()
        page.wait_for_url(f"{BASE_URL}/getDangerousFunctions")

        expect(page).to_have_title("Glyph - Dangerous Function Scanner")

    def test_home_shows_behavioral_scan_card(self, page: Any, server: Any) -> None:
        """Test that the home page shows the Behavioral Scan feature card (R24)."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Run a behavioral scan"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("BEHAVIORAL SCAN")

    def test_home_shows_similarity_dashboard_card(self, page: Any, server: Any) -> None:
        """Test that the home page shows the Similarity Dashboard feature card (R24)."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Open the similarity dashboard"]')
        expect(card).to_be_visible()
        expect(card).to_contain_text("SIMILARITY")

    def test_behavioral_scan_card_navigates_correctly(self, page: Any, server: Any) -> None:
        """Test that the Behavioral Scan card links to the behavioral scan page."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Run a behavioral scan"]')
        expect(card).to_have_attribute("href", "/getBehavioralScan")

        card.click()
        page.wait_for_url(f"{BASE_URL}/getBehavioralScan")

        expect(page).to_have_title("Glyph - Behavioral Scan")

    def test_similarity_dashboard_card_navigates_correctly(self, page: Any, server: Any) -> None:
        """Test that the Similarity card links to the similarity dashboard."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        card = page.locator('a.feature-card[aria-label="Open the similarity dashboard"]')
        expect(card).to_have_attribute("href", "/similarity-dashboard")

        card.click()
        page.wait_for_url(f"{BASE_URL}/similarity-dashboard")

        expect(page).to_have_title("Glyph - Similarity Dashboard")
