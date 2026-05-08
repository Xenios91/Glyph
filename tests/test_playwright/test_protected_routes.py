# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for protected routes.

Tests that protected routes redirect unauthenticated users to the login page.
"""

from typing import Any

from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


class TestProtectedRoutesRedirect:
    """Tests that protected routes redirect to login when not authenticated."""

    def test_home_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing home page redirects to login."""
        page.goto(f"{BASE_URL}/")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_upload_binary_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing upload page redirects to login."""
        page.goto(f"{BASE_URL}/uploadBinary")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_models_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing models page redirects to login."""
        page.goto(f"{BASE_URL}/getModels")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_predictions_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing predictions page redirects to login."""
        page.goto(f"{BASE_URL}/getPredictions")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_profile_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing profile page redirects to login."""
        page.goto(f"{BASE_URL}/profile")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_config_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing config page redirects to login."""
        page.goto(f"{BASE_URL}/config")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_prediction_details_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing prediction details redirects to login."""
        page.goto(f"{BASE_URL}/getPredictionDetails?model_name=test&function_name=test&task_name=test")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")

    def test_prediction_redirects_to_login(self, page: Any, server: Any) -> None:
        """Test that accessing a specific prediction redirects to login."""
        page.goto(f"{BASE_URL}/getPrediction?task_name=test&model_name=test")

        # Should redirect to login
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        expect(page).to_have_title("Glyph - Login")


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


class TestSessionPersistence:
    """Tests for session persistence across page navigations."""

    def test_session_persists_after_page_reload(self, page: Any, server: Any) -> None:
        """Test that user session persists after reloading the page."""
        import time
        timestamp = int(time.time() * 1000) % 100000
        username = f"testuser_{timestamp}"
        email = f"{username}@test.com"

        # Register
        page.goto(f"{BASE_URL}/register")
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Login
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Verify logged in
        expect(page).to_have_title("Glyph")

        # Reload page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Should still be logged in
        expect(page).to_have_title("Glyph")

    def test_session_persists_across_page_navigations(self, page: Any, server: Any) -> None:
        """Test that user session persists when navigating between pages."""
        import time
        timestamp = int(time.time() * 1000) % 100000
        username = f"testuser_{timestamp}"
        email = f"{username}@test.com"

        # Register
        page.goto(f"{BASE_URL}/register")
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Login
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to multiple pages
        page.goto(f"{BASE_URL}/uploadBinary")
        expect(page).to_have_title("Glyph - Upload Binary")

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
