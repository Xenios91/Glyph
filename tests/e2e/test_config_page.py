# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the configuration page.

Tests the configuration page loads correctly and displays the expected
settings controls for upload and CPU configuration.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestConfigPage:
    """Tests for the configuration page."""

    def test_config_page_loads(self, page: Any, server: Any) -> None:
        """Test that the configuration page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Configuration")

    def test_config_shows_page_header(self, page: Any, server: Any) -> None:
        """Test that the config page shows the page header."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#config-title")).to_be_visible()
        expect(page.locator("#config-title")).to_contain_text("SYSTEM CONFIGURATION")

    def test_config_shows_upload_settings_card(self, page: Any, server: Any) -> None:
        """Test that the config page shows the upload settings card."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # Upload settings card
        expect(page.locator(".upload-card")).to_be_visible()
        expect(page.locator("#upload-settings-title")).to_contain_text("UPLOAD SETTINGS")

    def test_config_shows_cpu_settings_card(self, page: Any, server: Any) -> None:
        """Test that the config page shows the CPU settings card."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # CPU settings card
        expect(page.locator(".cpu-card")).to_be_visible()
        expect(page.locator("#cpu-settings-title")).to_contain_text("CPU SETTINGS")

    def test_config_shows_max_file_size_slider(self, page: Any, server: Any) -> None:
        """Test that the config page shows the max file size slider."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # Max file size slider
        slider = page.locator("#max-file-size")
        expect(slider).to_be_visible()
        expect(slider).to_have_attribute("type", "range")

        # Value display
        expect(page.locator("#max-file-size-val")).to_be_visible()

        # Precision input
        expect(page.locator("#max-file-size-input")).to_be_visible()

    def test_config_shows_cpu_cores_slider(self, page: Any, server: Any) -> None:
        """Test that the config page shows the CPU cores slider."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # CPU cores slider
        slider = page.locator("#cpu-cores")
        expect(slider).to_be_visible()
        expect(slider).to_have_attribute("type", "range")

        # Value display
        expect(page.locator("#cpu-cores-val")).to_be_visible()

    def test_config_slider_values_sync(self, page: Any, server: Any) -> None:
        """Test that slider and precision input values are in sync."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # Get initial values
        slider_value = page.locator("#max-file-size").get_attribute("value")
        input_value = page.locator("#max-file-size-input").input_value()

        assert slider_value == input_value, f"Slider value ({slider_value}) doesn't match input value ({input_value})"

    def test_config_has_save_button(self, page: Any, server: Any) -> None:
        """Test that the config page has a save button."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/config")
        page.wait_for_load_state("networkidle")

        # Save button should be visible
        save_button = page.locator("#save-config-btn")
        expect(save_button).to_be_visible()
