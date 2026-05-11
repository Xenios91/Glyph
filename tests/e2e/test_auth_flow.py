# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for authentication flow.

Tests the complete user authentication lifecycle: registration, login, and logout.
"""

import time
from typing import Any

from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


def generate_unique_username() -> str:
    """Generate a unique username for testing."""
    timestamp = int(time.time() * 1000) % 100000
    return f"testuser_{timestamp}"


def wait_for_register_form(page: Any) -> None:
    """Wait for the register form JavaScript to be initialized."""
    page.wait_for_selector("#registerForm[data-initialized='true']", timeout=10000)


def wait_for_login_form(page: Any) -> None:
    """Wait for the login form JavaScript to be initialized."""
    page.wait_for_selector("#loginForm[data-initialized='true']", timeout=10000)


class TestRegistrationFlow:
    """Tests for user registration flow."""

    def test_successful_registration(self, page: Any, server: Any) -> None:
        """Test successful user registration redirects to login page."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)

        # Fill in the registration form
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#full_name").fill("Test User")
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")

        # Submit the form
        page.locator("#register-submit-btn").click()

        # Should redirect to login page after successful registration
        page.wait_for_url(f"{BASE_URL}/login")
        expect(page).to_have_title("Glyph - Login")

    def test_registration_with_existing_username(self, page: Any, server: Any) -> None:
        """Test registration fails with duplicate username."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # First registration
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Second registration with same username should fail
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(f"different_{username}@test.com")
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should show error message
        error_locator = page.locator("#register-error")
        expect(error_locator).to_be_visible()
        expect(error_locator).to_contain_text("Username already registered")

    def test_registration_with_existing_email(self, page: Any, server: Any) -> None:
        """Test registration fails with duplicate email."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # First registration
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Second registration with same email should fail
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(f"{username}_duplicate")
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should show error message
        error_locator = page.locator("#register-error")
        expect(error_locator).to_be_visible()
        expect(error_locator).to_contain_text("Email already registered")


class TestLoginFlow:
    """Tests for user login flow."""

    def test_successful_login(self, page: Any, server: Any) -> None:
        """Test successful login redirects to home page."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register first
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Login
        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()

        # Should redirect to home page
        page.wait_for_url(f"{BASE_URL}/")
        expect(page).to_have_title("Glyph")

    def test_login_with_invalid_credentials(self, page: Any, server: Any) -> None:
        """Test login fails with invalid credentials."""
        page.goto(f"{BASE_URL}/login")
        wait_for_login_form(page)

        page.locator("#username").fill("nonexistent_user")
        page.locator("#password").fill("WrongPassword123!")
        page.locator("#login-submit-btn").click()

        # Should show error message
        error_locator = page.locator("#login-error")
        expect(error_locator).to_be_visible()
        expect(error_locator).to_contain_text("Incorrect username or password")

    def test_login_with_empty_credentials(self, page: Any, server: Any) -> None:
        """Test login fails with empty credentials."""
        page.goto(f"{BASE_URL}/login")
        wait_for_login_form(page)

        # Clear any existing values and submit
        page.locator("#username").fill("")
        page.locator("#password").fill("")
        page.locator("#login-submit-btn").click()

        # Should remain on login page
        expect(page).to_have_title("Glyph - Login")


class TestLogoutFlow:
    """Tests for user logout flow."""

    def test_successful_logout(self, page: Any, server: Any) -> None:
        """Test logout redirects to home page and clears session."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Logout via navbar - use JS to force open user dropdown (hover unreliable in headless)
        page.evaluate("""
          const menu = document.getElementById('user-menu');
          const toggle = menu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
          if (menu && toggle) {
            menu.classList.add('is-open');
            toggle.setAttribute('aria-expanded', 'true');
          }
        """)
        # Wait for dropdown to be visible
        page.wait_for_selector("#user-menu.is-open", state="visible", timeout=5000)
        # Click logout
        page.locator('a[role="menuitem"][aria-label="Logout"]').click()

        # After logout: redirect to / → 401 → redirect to /login?redirect=/
        # Wait for login page to load (use regex for URL matching with query params)
        import re
        page.wait_for_url(re.compile(r"/login"), timeout=10000)

        # Should show login/register links instead of user menu
        login_link = page.locator('a[aria-label="Login"]')
        expect(login_link).to_be_visible()


class TestAuthenticatedPageAccess:
    """Tests for accessing pages that require authentication."""

    def test_home_page_after_login(self, page: Any, server: Any) -> None:
        """Test home page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Check home page content
        expect(page).to_have_title("Glyph")
        expect(page.locator("#glyph-title")).to_be_visible()
        expect(page.locator("#glyph-title")).to_have_text("GLYPH")

    def test_upload_page_after_login(self, page: Any, server: Any) -> None:
        """Test upload page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to upload page
        page.goto(f"{BASE_URL}/uploadBinary")
        expect(page).to_have_title("Glyph - Upload Binary")
        expect(page.locator("#upload-box")).to_be_visible()

    def test_profile_page_after_login(self, page: Any, server: Any) -> None:
        """Test profile page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to profile page
        page.goto(f"{BASE_URL}/profile")
        expect(page).to_have_title("Glyph - Profile")
        expect(page.locator(".profile-username")).to_contain_text(username)

    def test_config_page_after_login(self, page: Any, server: Any) -> None:
        """Test config page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to config page
        page.goto(f"{BASE_URL}/config")
        expect(page).to_have_title("Glyph - Configuration")

    def test_models_page_after_login(self, page: Any, server: Any) -> None:
        """Test models page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to models page
        page.goto(f"{BASE_URL}/getModels")
        expect(page).to_have_title("Models List")

    def test_predictions_page_after_login(self, page: Any, server: Any) -> None:
        """Test predictions page loads correctly after login."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        wait_for_register_form(page)
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        wait_for_login_form(page)
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to predictions page
        page.goto(f"{BASE_URL}/getPredictions")
        expect(page).to_have_title("Predictions List")
