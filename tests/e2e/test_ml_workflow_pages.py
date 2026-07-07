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

    def test_similarity_dashboard_shows_progress_panel_structure(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has a progress panel structure."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # Progress panel should exist in DOM (initially hidden)
        progress_panel = page.locator("#progress-panel")
        assert progress_panel.count() == 1

        # Progress bar fill should exist
        progress_fill = page.locator("#progress-bar-fill")
        assert progress_fill.count() == 1

        # Progress text should exist
        progress_text = page.locator("#progress-text")
        assert progress_text.count() == 1

    def test_similarity_dashboard_shows_results_panel_structure(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has a results panel structure."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # Results panel should exist in DOM (initially hidden)
        results_panel = page.locator("#results-panel")
        assert results_panel.count() == 1

    def test_similarity_dashboard_has_view_toggle_buttons(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has view toggle buttons."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # View toggle container should exist
        view_toggle = page.locator(".view-toggle")
        assert view_toggle.count() == 1

    def test_similarity_dashboard_has_heatmap_button(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has the heatmap view button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        heatmap_btn = page.locator("#heatmap-btn")
        assert heatmap_btn.count() == 1
        expect(heatmap_btn).to_contain_text("Heatmap")

    def test_similarity_dashboard_has_table_button(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has the table view button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        table_btn = page.locator("#table-btn")
        assert table_btn.count() == 1
        expect(table_btn).to_contain_text("Table")

    def test_similarity_dashboard_shows_selection_count(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard shows the selection count."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        selection_count = page.locator("#selection-count")
        assert selection_count.count() == 1

    def test_similarity_dashboard_has_binaries_loading_state(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard shows binary loading state."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")

        # Binaries loading indicator should exist
        binaries_loading = page.locator("#binaries-loading")
        assert binaries_loading.count() == 1

    def test_similarity_dashboard_has_no_binaries_empty_state(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has a no-binaries empty state."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # No binaries empty state should exist in DOM
        no_binaries = page.locator("#no-binaries")
        assert no_binaries.count() == 1

    def test_similarity_dashboard_has_no_saved_empty_state(self, page: Any, server: Any) -> None:
        """Test that the similarity dashboard has a no-saved empty state."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/similarity-dashboard")
        page.wait_for_load_state("networkidle")

        # No saved computations empty state should exist in DOM
        no_saved = page.locator("#no-saved")
        assert no_saved.count() == 1
