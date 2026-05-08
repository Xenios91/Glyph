# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for form validation.

Tests client-side and server-side form validation for login and registration forms.
"""

import time
from typing import Any

from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


def generate_unique_username() -> str:
    """Generate a unique username for testing."""
    timestamp = int(time.time() * 1000) % 100000
    return f"testuser_{timestamp}"


class TestLoginFormValidation:
    """Tests for login form validation."""

    def test_login_form_requires_username(self, page: Any, server: Any) -> None:
        """Test that login form requires a username."""
        page.goto(f"{BASE_URL}/login")

        # Leave username empty, fill password only
        page.locator("#password").fill("SomePassword123!")
        page.locator("#login-submit-btn").click()

        # Should remain on login page
        expect(page).to_have_title("Glyph - Login")

    def test_login_form_requires_password(self, page: Any, server: Any) -> None:
        """Test that login form requires a password."""
        page.goto(f"{BASE_URL}/login")

        # Fill username only, leave password empty
        page.locator("#username").fill("testuser")
        page.locator("#login-submit-btn").click()

        # Should remain on login page
        expect(page).to_have_title("Glyph - Login")

    def test_login_form_shows_error_on_invalid_credentials(self, page: Any, server: Any) -> None:
        """Test that login form shows error message on invalid credentials."""
        page.goto(f"{BASE_URL}/login")

        page.locator("#username").fill("invalid_user")
        page.locator("#password").fill("WrongPassword123!")
        page.locator("#login-submit-btn").click()

        # Error message should be visible
        error_locator = page.locator("#login-error")
        expect(error_locator).to_be_visible()
        expect(error_locator).to_contain_text("Incorrect username or password")

    def test_login_form_inputs_have_correct_types(self, page: Any, server: Any) -> None:
        """Test that login form inputs have correct types."""
        page.goto(f"{BASE_URL}/login")

        # Username should be text input
        username_input = page.locator("#username")
        expect(username_input).to_have_attribute("type", "text")

        # Password should be password input
        password_input = page.locator("#password")
        expect(password_input).to_have_attribute("type", "password")


class TestRegisterFormValidation:
    """Tests for registration form validation."""

    def test_register_form_requires_username(self, page: Any, server: Any) -> None:
        """Test that registration form requires a username."""
        page.goto(f"{BASE_URL}/register")

        # Fill all fields except username
        page.locator("#email").fill("test@example.com")
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should remain on register page (validation error)
        expect(page).to_have_title("Glyph - Register")

    def test_register_form_requires_email(self, page: Any, server: Any) -> None:
        """Test that registration form requires an email."""
        page.goto(f"{BASE_URL}/register")

        # Fill all fields except email
        username = generate_unique_username()
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should remain on register page (validation error)
        expect(page).to_have_title("Glyph - Register")

    def test_register_form_requires_password(self, page: Any, server: Any) -> None:
        """Test that registration form requires a password."""
        page.goto(f"{BASE_URL}/register")

        # Fill all fields except password
        username = generate_unique_username()
        page.locator("#username").fill(username)
        page.locator("#email").fill(f"{username}@test.com")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should remain on register page (validation error)
        expect(page).to_have_title("Glyph - Register")

    def test_register_form_passwords_must_match(self, page: Any, server: Any) -> None:
        """Test that registration form requires matching passwords."""
        page.goto(f"{BASE_URL}/register")

        username = generate_unique_username()
        page.locator("#username").fill(username)
        page.locator("#email").fill(f"{username}@test.com")
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("DifferentPass123!")
        page.locator("#register-submit-btn").click()

        # Should show error or remain on page
        expect(page).to_have_title("Glyph - Register")

    def test_register_form_inputs_have_correct_types(self, page: Any, server: Any) -> None:
        """Test that registration form inputs have correct types."""
        page.goto(f"{BASE_URL}/register")

        # Username should be text input
        expect(page.locator("#username")).to_have_attribute("type", "text")

        # Email should be email input
        expect(page.locator("#email")).to_have_attribute("type", "email")

        # Full name should be text input
        expect(page.locator("#full_name")).to_have_attribute("type", "text")

        # Password should be password input
        expect(page.locator("#password")).to_have_attribute("type", "password")

        # Confirm password should be password input
        expect(page.locator("#confirm_password")).to_have_attribute("type", "password")

    def test_register_form_username_min_length(self, page: Any, server: Any) -> None:
        """Test that registration form enforces minimum username length."""
        page.goto(f"{BASE_URL}/register")

        # Try username with less than 3 characters
        page.locator("#username").fill("ab")
        page.locator("#email").fill("short@test.com")
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()

        # Should remain on register page (validation error)
        expect(page).to_have_title("Glyph - Register")

    def test_register_form_password_min_length(self, page: Any, server: Any) -> None:
        """Test that registration form enforces minimum password length."""
        page.goto(f"{BASE_URL}/register")

        username = generate_unique_username()
        page.locator("#username").fill(username)
        page.locator("#email").fill(f"{username}@test.com")
        page.locator("#password").fill("Short1!")  # Less than 8 characters
        page.locator("#confirm_password").fill("Short1!")
        page.locator("#register-submit-btn").click()

        # Should remain on register page or show error
        expect(page).to_have_title("Glyph - Register")


class TestProfileFormValidation:
    """Tests for profile form validation."""

    def test_profile_form_shows_user_data(self, page: Any, server: Any) -> None:
        """Test that profile form displays current user data."""
        username = generate_unique_username()
        email = f"{username}@test.com"
        full_name = "Test User Profile"

        # Register
        page.goto(f"{BASE_URL}/register")
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#full_name").fill(full_name)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Login
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to profile
        page.goto(f"{BASE_URL}/profile")

        # Check profile form has user data
        expect(page.locator("#full_name")).to_have_value(full_name)
        expect(page.locator("#email")).to_have_value(email)

    def test_profile_form_has_required_elements(self, page: Any, server: Any) -> None:
        """Test that profile form has all required elements."""
        username = generate_unique_username()
        email = f"{username}@test.com"

        # Register and login
        page.goto(f"{BASE_URL}/register")
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to profile
        page.goto(f"{BASE_URL}/profile")

        # Check form elements exist
        expect(page.locator("#profileForm")).to_be_visible()
        expect(page.locator("#full_name")).to_be_visible()
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#profile-submit-btn")).to_be_visible()
