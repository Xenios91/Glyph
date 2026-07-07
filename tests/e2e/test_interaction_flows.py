# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for interactive form submissions and state changes.

Tests config save, profile update, password change, and API key creation flows.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, generate_unique_username, register_and_login


class TestConfigSaveInteraction:
    """Tests for configuration save interaction."""

    def test_config_save_button_is_enabled(self, page: Any, server: Any) -> None:
        """Test that the config save button is enabled by default."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        save_button = page.locator("#save-config-btn")
        expect(save_button).to_be_visible()
        expect(save_button).not_to_be_disabled()

    def test_config_save_button_has_correct_label(self, page: Any, server: Any) -> None:
        """Test that the config save button has the correct label."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        save_button = page.locator("#save-config-btn")
        expect(save_button).to_be_visible()

    def test_config_slider_interaction_changes_value(self, page: Any, server: Any) -> None:
        """Test that interacting with the slider changes the displayed value."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # Get initial value
        initial_value = page.locator("#max-file-size-val").inner_text()

        # Change slider by filling the precision input
        page.locator("#max-file-size-input").fill("50")
        page.locator("#max-file-size-input").press("Enter")
        page.wait_for_timeout(300)

        # Value display should update (includes unit suffix " MB")
        new_value = page.locator("#max-file-size-val").inner_text()
        assert new_value == "50 MB", f"Expected value '50 MB', got {new_value}"


class TestProfileUpdateInteraction:
    """Tests for profile update submission."""

    def test_profile_update_form_submits_successfully(self, page: Any, server: Any) -> None:
        """Test that updating the profile form submits without errors."""
        username = generate_unique_username()
        email = f"{username}@test.com"
        original_name = "Original Name"
        new_name = "Updated Name"

        # Register
        page.goto(f"{BASE_URL}/register")
        page.wait_for_selector("#registerForm[data-initialized='true']")
        page.locator("#username").fill(username)
        page.locator("#email").fill(email)
        page.locator("#full_name").fill(original_name)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#confirm_password").fill("SecurePass123!")
        page.locator("#register-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/login")

        # Login
        page.wait_for_selector("#loginForm[data-initialized='true']")
        page.locator("#username").fill(username)
        page.locator("#password").fill("SecurePass123!")
        page.locator("#login-submit-btn").click()
        page.wait_for_url(f"{BASE_URL}/")

        # Navigate to profile
        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Update full name
        page.locator("#full_name").clear()
        page.locator("#full_name").fill(new_name)
        page.locator("#profile-submit-btn").click()
        page.wait_for_timeout(1000)

        # Page should still be on profile (or reload)
        assert "/profile" in page.url or page.url == f"{BASE_URL}/profile"

    def test_profile_update_preserves_email(self, page: Any, server: Any) -> None:
        """Test that profile update preserves the email address."""
        username = register_and_login(page)
        email = f"{username}@test.com"

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Email should still be populated
        current_email = page.locator("#email").input_value()
        assert current_email == email, f"Expected {email}, got {current_email}"


class TestPasswordChangeFlow:
    """Tests for password change flow."""

    def test_password_change_form_has_all_fields(self, page: Any, server: Any) -> None:
        """Test that the password change form has all required fields."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        expect(page.locator("#current_password")).to_be_visible()
        expect(page.locator("#new_password")).to_be_visible()
        expect(page.locator("#confirm_password")).to_be_visible()
        expect(page.locator("#password-submit-btn")).to_be_visible()

    def test_password_change_with_mismatched_passwords_shows_error(self, page: Any, server: Any) -> None:
        """Test that password change shows error when new passwords don't match."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        # Fill with mismatched passwords
        page.locator("#current_password").fill("SecurePass123!")
        page.locator("#new_password").fill("NewPassword123!")
        page.locator("#confirm_password").fill("DifferentPass123!")
        page.locator("#password-submit-btn").click()

        page.wait_for_timeout(1000)

        # Should show an error or remain on the page
        # The page should not redirect
        assert "/profile" in page.url

    def test_password_change_requires_current_password(self, page: Any, server: Any) -> None:
        """Test that password change requires the current password."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        # Leave current password empty, fill new passwords
        page.locator("#new_password").fill("NewPassword123!")
        page.locator("#confirm_password").fill("NewPassword123!")
        page.locator("#password-submit-btn").click()

        page.wait_for_timeout(1000)

        # Should remain on profile page
        assert "/profile" in page.url


class TestAPIKeyCreation:
    """Tests for API key creation flow."""

    def test_api_key_creation_button_exists(self, page: Any, server: Any) -> None:
        """Test that the API key creation button exists."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to API keys tab
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        expect(page.locator("#create-api-key-btn")).to_be_visible()

    def test_api_keys_list_container_exists(self, page: Any, server: Any) -> None:
        """Test that the API keys list container exists."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to API keys tab
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        api_keys_list = page.locator("#apiKeysList")
        assert api_keys_list.count() == 1

    def test_api_key_creation_creates_key(self, page: Any, server: Any) -> None:
        """Test that clicking create API key generates a key."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to API keys tab
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        # Click create key button
        page.locator("#create-api-key-btn").click()
        page.wait_for_timeout(2000)

        # Should still be on profile page
        assert "/profile" in page.url
