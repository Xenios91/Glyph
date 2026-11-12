# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for profile management.

Tests profile editing, password change, API keys, and accessibility settings
on the profile page.
"""

from typing import Any
from uuid import uuid4

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestProfilePage:
    """Tests for the profile page layout and tabs."""

    def test_profile_page_loads(self, page: Any, server: Any) -> None:
        """Test that the profile page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Profile")

    def test_profile_shows_username(self, page: Any, server: Any) -> None:
        """Test that the profile page displays the username."""
        username = register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".profile-username")).to_contain_text(username)

    def test_profile_shows_email(self, page: Any, server: Any) -> None:
        """Test that the profile page displays the email."""
        username = register_and_login(page)
        email = f"{username}@test.com"

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".profile-email")).to_contain_text(email)

    def test_profile_shows_avatar(self, page: Any, server: Any) -> None:
        """Test that the profile page shows the user avatar with initials."""
        username = register_and_login(page)
        expected_initials = username[:2].upper()

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        avatar = page.locator(".avatar-initials")
        expect(avatar).to_be_visible()
        expect(avatar).to_have_text(expected_initials)

    def test_profile_shows_tab_navigation(self, page: Any, server: Any) -> None:
        """Test that the profile page shows all tab navigation items."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Check all tabs are present
        expect(page.locator("#tab-profile")).to_be_visible()
        expect(page.locator("#tab-password")).to_be_visible()
        expect(page.locator("#tab-apikeys")).to_be_visible()
        expect(page.locator("#tab-llm")).to_be_visible()
        expect(page.locator("#tab-accessibility")).to_be_visible()

    def test_profile_tab_is_active_by_default(self, page: Any, server: Any) -> None:
        """Test that the Profile tab is active by default."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Profile tab should be selected
        profile_tab = page.locator("#tab-profile")
        expect(profile_tab).to_have_attribute("aria-selected", "true")

        # Profile panel should be visible
        profile_panel = page.locator("#panel-profile")
        expect(profile_panel).to_have_attribute("aria-hidden", "false")


class TestProfileEditing:
    """Tests for editing profile information."""

    def test_profile_form_has_required_elements(self, page: Any, server: Any) -> None:
        """Test that the profile edit form has all required elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#profileForm")).to_be_visible()
        expect(page.locator("#full_name")).to_be_visible()
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#profile-submit-btn")).to_be_visible()

    def test_profile_form_shows_user_data(self, page: Any, server: Any) -> None:
        """Test that the profile form displays current user data."""
        username = register_and_login(page)
        email = f"{username}@test.com"

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#email")).to_have_value(email)


class TestPasswordTab:
    """Tests for the password change tab."""

    def test_password_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the Password tab shows the password panel."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Use JS to switch tab (more reliable than click in headless)
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        # Password tab should be selected
        password_tab = page.locator("#tab-password")
        expect(password_tab).to_have_attribute("aria-selected", "true")

        # Password panel should be visible
        password_panel = page.locator("#panel-password")
        expect(password_panel).to_have_attribute("aria-hidden", "false")

    def test_password_form_has_required_fields(self, page: Any, server: Any) -> None:
        """Test that the password form has all required fields."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab via JS
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        expect(page.locator("#passwordForm")).to_be_visible()
        expect(page.locator("#current_password")).to_be_visible()
        expect(page.locator("#new_password")).to_be_visible()
        expect(page.locator("#confirm_password")).to_be_visible()
        expect(page.locator("#password-submit-btn")).to_be_visible()

    def test_password_fields_have_correct_types(self, page: Any, server: Any) -> None:
        """Test that password form fields are password type inputs."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab via JS
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        expect(page.locator("#current_password")).to_have_attribute("type", "password")
        expect(page.locator("#new_password")).to_have_attribute("type", "password")
        expect(page.locator("#confirm_password")).to_have_attribute("type", "password")

    def test_new_password_has_minlength(self, page: Any, server: Any) -> None:
        """Test that the new password field has a minimum length requirement."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to password tab via JS
        page.evaluate("() => switchTab('tab-password', 'panel-password')")

        minlength = page.locator("#new_password").get_attribute("minlength")
        assert minlength == "8", f"Expected minlength=8, got {minlength}"


class TestAPIKeysTab:
    """Tests for the API keys tab."""

    def test_api_keys_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the API Keys tab shows the API keys panel."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Use JS to switch tab (more reliable than click in headless)
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        # API keys tab should be selected
        api_keys_tab = page.locator("#tab-apikeys")
        expect(api_keys_tab).to_have_attribute("aria-selected", "true")

        # API keys panel should be visible
        api_keys_panel = page.locator("#panel-apikeys")
        expect(api_keys_panel).to_have_attribute("aria-hidden", "false")

    def test_api_keys_shows_create_button(self, page: Any, server: Any) -> None:
        """Test that the API keys panel shows the create key button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to API keys tab via JS
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        expect(page.locator("#create-api-key-btn")).to_be_visible()
        assert page.locator("#apiKeysList").count() == 1


class TestLLMSettingsTab:
    """Tests for the LLM settings tab."""

    def test_llm_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the LLM tab shows the LLM settings panel."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Use JS to switch tab (more reliable than click in headless)
        page.evaluate("() => switchTab('tab-llm', 'panel-llm')")

        # LLM tab should be selected
        llm_tab = page.locator("#tab-llm")
        expect(llm_tab).to_have_attribute("aria-selected", "true")

        # LLM panel should be visible
        llm_panel = page.locator("#panel-llm")
        expect(llm_panel).to_have_attribute("aria-hidden", "false")

    def test_llm_panel_shows_settings_fields(self, page: Any, server: Any) -> None:
        """Test that the LLM panel shows all settings fields and buttons."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to LLM tab via JS
        page.evaluate("() => switchTab('tab-llm', 'panel-llm')")

        expect(page.locator("#llm-enabled")).to_be_visible()
        expect(page.locator("#llm-base-url")).to_be_visible()
        expect(page.locator("#llm-api-key")).to_be_visible()
        expect(page.locator("#llm-test-btn")).to_be_visible()
        expect(page.locator("#llm-save-btn")).to_be_visible()


class TestAccessibilityTab:
    """Tests for the accessibility tab."""

    def test_accessibility_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the Accessibility tab shows the accessibility panel."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Use JS to switch tab (more reliable than click in headless)
        page.evaluate("() => switchTab('tab-accessibility', 'panel-accessibility')")

        # Accessibility tab should be selected
        accessibility_tab = page.locator("#tab-accessibility")
        expect(accessibility_tab).to_have_attribute("aria-selected", "true")

        # Accessibility panel should be visible
        accessibility_panel = page.locator("#panel-accessibility")
        expect(accessibility_panel).to_have_attribute("aria-hidden", "false")

    def test_accessibility_shows_dyslexia_font_toggle(self, page: Any, server: Any) -> None:
        """Test that the accessibility panel shows the dyslexia font toggle."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")

        # Switch to accessibility tab via JS
        page.evaluate("() => switchTab('tab-accessibility', 'panel-accessibility')")

        expect(page.locator("#dyslexia-font-toggle")).to_be_visible()


class TestAPIKeyDeleteConfirmation:
    """R9/R10: deleting an API key must use the styled confirm modal."""

    def test_api_key_delete_uses_styled_confirm_modal(self, page: Any, server: Any) -> None:
        """Create a key, then verify cancel keeps it and confirm deletes it."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/profile")
        page.wait_for_load_state("networkidle")
        page.evaluate("() => switchTab('tab-apikeys', 'panel-apikeys')")

        # Create a key through the real form.
        key_name = f"e2e_key_{uuid4().hex[:8]}"
        page.locator("#create-api-key-btn").click()
        expect(page.locator("#createApiKeyModal")).to_be_visible()
        page.locator("#key_name").fill(key_name)
        page.locator("#create-key-submit-btn").click()
        expect(page.locator("#apiKeySecret")).to_be_visible()

        # Closing the modal refreshes the list, which now contains the key.
        # After creation the form (and its Cancel button) is hidden, so close
        # via the page-level Escape handler, which also refreshes the list.
        page.keyboard.press("Escape")
        expect(page.locator("#createApiKeyModal")).to_have_count(1)
        expect(page.locator("#createApiKeyModal")).not_to_be_visible()
        expect(page.locator("#apiKeysList .api-key-item")).to_have_count(1)
        expect(page.locator("#apiKeysList .api-key-item strong")).to_contain_text(key_name)

        native_dialogs: list[str] = []

        def _on_dialog(dialog: Any) -> None:
            native_dialogs.append(dialog.message)
            dialog.dismiss()

        page.on("dialog", _on_dialog)

        # Clicking Delete opens the styled modal naming the key.
        page.locator(".delete-api-key-btn").click()
        overlay = page.locator(".confirm-modal-overlay")
        expect(overlay).to_be_visible()
        expect(page.locator(".confirm-modal-title")).to_contain_text("Delete API Key")
        expect(page.locator(".confirm-modal-message")).to_contain_text(key_name)

        # Cancelling keeps the key.
        page.locator(".confirm-modal .cyber-btn", has_text="Cancel").click()
        expect(overlay).to_have_count(0)
        expect(page.locator("#apiKeysList .api-key-item")).to_have_count(1)

        # Confirming deletes the key.
        page.locator(".delete-api-key-btn").click()
        expect(overlay).to_be_visible()
        page.locator(".confirm-modal .cyber-btn", has_text="Delete").click()
        expect(page.locator("#apiKeysList .api-key-item")).to_have_count(0)
        expect(page.locator("#apiKeysList .no-api-keys")).to_be_visible()
        assert not native_dialogs, f"Native dialog opened: {native_dialogs}"
