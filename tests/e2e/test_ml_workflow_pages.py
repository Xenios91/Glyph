# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for ML workflow pages.

Tests the create model, create prediction, and similarity dashboard pages
load correctly and display expected UI elements.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestCreateModelPage:
    """Tests for the create model page."""

    def test_create_model_page_loads(self, page: Any, server: Any) -> None:
        """Test that the create model page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-model")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Create Model")

    def test_create_model_shows_form_elements(self, page: Any, server: Any) -> None:
        """Test that the create model page shows all required form elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-model")
        page.wait_for_load_state("networkidle")

        # Check form container
        expect(page.locator("#create-model-box")).to_be_visible()
        expect(page.locator("#create-model-title")).to_contain_text("MODEL CONFIGURATION")

        # Check binary selection dropdown
        expect(page.locator("#binary-select")).to_be_visible()

        # Check model name input
        expect(page.locator("#model-name")).to_be_visible()

        # Check ML class type dropdown
        expect(page.locator("#ml-class-type")).to_be_visible()

        # Check submit button
        expect(page.locator("#create-model-btn")).to_be_visible()
        expect(page.locator("#create-model-btn")).to_contain_text("TRAIN MODEL")

    def test_create_model_shows_error_container(self, page: Any, server: Any) -> None:
        """Test that the create model page has an error message container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-model")
        page.wait_for_load_state("networkidle")

        # Error container exists in DOM (initially hidden)
        error_container = page.locator("#create-model-error")
        assert error_container.count() == 1

    def test_create_model_shows_status_container(self, page: Any, server: Any) -> None:
        """Test that the create model page has a status message container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-model")
        page.wait_for_load_state("networkidle")

        # Status container exists in DOM (initially hidden)
        status_container = page.locator("#create-model-status")
        assert status_container.count() == 1


class TestCreatePredictionPage:
    """Tests for the create prediction page."""

    def test_create_prediction_page_loads(self, page: Any, server: Any) -> None:
        """Test that the create prediction page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-prediction")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Create Prediction")

    def test_create_prediction_shows_form_elements(self, page: Any, server: Any) -> None:
        """Test that the create prediction page shows all required form elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-prediction")
        page.wait_for_load_state("networkidle")

        # Check form container
        expect(page.locator("#create-prediction-box")).to_be_visible()
        expect(page.locator("#create-prediction-title")).to_contain_text("PREDICTION CONFIGURATION")

        # Check binary selection dropdown
        expect(page.locator("#binary-select")).to_be_visible()

        # Check model selection dropdown
        expect(page.locator("#model-select")).to_be_visible()

        # Check task name input
        expect(page.locator("#task-name")).to_be_visible()

        # Check submit button
        expect(page.locator("#create-prediction-btn")).to_be_visible()
        expect(page.locator("#create-prediction-btn")).to_contain_text("RUN PREDICTION")

    def test_create_prediction_shows_error_container(self, page: Any, server: Any) -> None:
        """Test that the create prediction page has an error message container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/create-prediction")
        page.wait_for_load_state("networkidle")

        # Error container exists in DOM (initially hidden)
        error_container = page.locator("#create-prediction-error")
        assert error_container.count() == 1


class TestSimilarityDashboardPage:
    """Tests for the similarity dashboard page."""

    def test_similarity_dashboard_page_loads(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Similarity Dashboard")

    def test_similarity_dashboard_shows_selection_panel(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard shows the binary selection panel."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # Check task name input
        expect(page.locator("#task-name-input")).to_be_visible()

        # Check threshold input
        expect(page.locator("#threshold-input")).to_be_visible()

        # Check selection controls
        expect(page.locator("#select-all-btn")).to_be_visible()
        expect(page.locator("#deselect-all-btn")).to_be_visible()
        expect(page.locator("#compute-btn")).to_be_visible()

    def test_similarity_dashboard_shows_saved_computations(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard shows the saved computations section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # Saved computations container exists
        expect(page.locator("#saved-computations")).to_be_visible()
