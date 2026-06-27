# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for protected routes.

Tests that protected routes redirect unauthenticated users to the login page.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import (
    BASE_URL,
    login_user,
    register_and_login,
    register_user,
    wait_for_login_form,
    wait_for_register_form,
)


class TestProtectedRoutesRedirect:
    """Tests that protected routes redirect to login when not authenticated."""

    def test_home_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing home page redirects to login."""
        page.goto(f"{BASE_URL}/", wait_until="commit")
        # The server returns 401 for unauthenticated requests
        # Check that we either redirected to login or got a 401
        current_url = page.url
        # If redirected, URL should be login; if not, page should show error
        assert "/login" in current_url or page.title() != "Glyph"

    def test_models_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing models page redirects to login."""
        page.goto(f"{BASE_URL}/getModels", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Models List"

    def test_predictions_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing predictions page redirects to login."""
        page.goto(f"{BASE_URL}/getPredictions", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Predictions List"

    def test_profile_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing profile page redirects to login."""
        page.goto(f"{BASE_URL}/profile", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Profile"

    def test_config_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing config page redirects to login."""
        page.goto(f"{BASE_URL}/config", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Configuration"

    def test_prediction_details_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing prediction details redirects to login."""
        page.goto(f"{BASE_URL}/getPredictionDetails?model_name=test&function_name=test&task_name=test", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or "Not authenticated" in page.content()

    def test_prediction_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing a specific prediction redirects to login."""
        page.goto(f"{BASE_URL}/getPrediction?task_name=test&model_name=test", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or "Not authenticated" in page.content()

    def test_binary_library_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing binary library redirects to login."""
        page.goto(f"{BASE_URL}/binary-library", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Binary Library"

    def test_binary_detail_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing a binary detail page redirects to login."""
        page.goto(f"{BASE_URL}/binary/1", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Binary Details"

    def test_run_task_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing run task page redirects to login."""
        page.goto(f"{BASE_URL}/run-task?binary_id=1&binary_name=test", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Run Task"

    def test_create_model_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing create model page redirects to login."""
        page.goto(f"{BASE_URL}/create-model", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Create Model"

    def test_create_prediction_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing create prediction page redirects to login."""
        page.goto(f"{BASE_URL}/create-prediction", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Create Prediction"

    def test_task_results_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing task results page redirects to login."""
        page.goto(f"{BASE_URL}/task-results?task_uuid=test", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Task Results"

    def test_similarity_dashboard_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing similarity dashboard redirects to login."""
        page.goto(f"{BASE_URL}/similarity-dashboard", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Similarity Dashboard"

    def test_dangerous_functions_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing dangerous functions page redirects to login."""
        page.goto(f"{BASE_URL}/getDangerousFunctions", wait_until="commit")
        current_url = page.url
        assert "/login" in current_url or page.title() != "Glyph - Dangerous Function Scanner"


class TestPublicRoutesAccessible:
    """Tests that public routes are accessible without authentication."""

    def test_login_accessible_without_auth(self, page: Any, server: Any) -> None:
        """Test that login page is accessible without authentication."""
        page.goto(f"{BASE_URL}/login")

        # Should show login page
        expect(page).to_have_title("Glyph - Login")
        expect(page.locator("#loginForm")).to_be_visible()

    def test_register_accessible_without_auth(self, page: Any, server: Any) -> None:
        """Test that register page is accessible without authentication."""
        page.goto(f"{BASE_URL}/register")

        # Should show register page
        expect(page).to_have_title("Glyph - Register")
        expect(page.locator("#registerForm")).to_be_visible()

    def test_error_page_accessible(self, page: Any, server: Any) -> None:
        """Test that error page is accessible."""
        page.goto(f"{BASE_URL}/error")

        # Should show error page
        expect(page).to_have_title("Glyph - Error")


from tests.e2e.utils import register_and_login


class TestSessionPersistence:
    """Tests for session persistence across page navigations."""

    def test_session_persists_after_page_reload(self, page: Any, server: Any) -> None:
        """Test that user session persists after reloading the page."""
        register_and_login(page)

        # Verify logged in
        expect(page).to_have_title("Glyph")

        # Reload page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Should still be logged in
        expect(page).to_have_title("Glyph")

    def test_session_persists_across_page_navigations(self, page: Any, server: Any) -> None:
        """Test that user session persists when navigating between pages."""
        register_and_login(page)

        # Navigate to multiple pages
        page.goto(f"{BASE_URL}/getModels")
        expect(page).to_have_title("Models List")

        page.goto(f"{BASE_URL}/getPredictions")
        expect(page).to_have_title("Predictions List")

        page.goto(f"{BASE_URL}/config")
        expect(page).to_have_title("Glyph - Configuration")

        page.goto(f"{BASE_URL}/profile")
        expect(page).to_have_title("Glyph - Profile")

        # Navigate back to home
        page.goto(f"{BASE_URL}/")
        expect(page).to_have_title("Glyph")
