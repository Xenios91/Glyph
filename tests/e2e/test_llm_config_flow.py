# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the LLM configuration flow (TESTS.md P1).

Profile -> LLM tab -> save endpoint settings -> "Test connection" against an
unreachable endpoint. The save must persist (reload retains the values) and
the connection test must surface a clear error instead of hanging. An
invalid base URL must surface the server's inline validation error.
"""

import re
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login

# Public IP literal with a port that is not an HTTP listener: DNS resolution
# succeeds (so the SSRF guard passes at save time) but the connection fails
# quickly, so the llm-test endpoint returns a clear error without hanging.
UNREACHABLE_BASE_URL = "http://8.8.8.8"
UNREACHABLE_PORT = "53"
TEST_MODEL = "e2e-unreachable-model"

# Prefixes of the error strings produced by test_llm_connection
# (app/services/llm_analysis_service.py). The exact suffix is
# environment-dependent (filtered vs. refused vs. protocol error), so the
# assertion targets the stable prefix.
KNOWN_ERROR_PREFIXES = (
    "Request timed out after",
    "Could not reach endpoint",
    "Endpoint returned HTTP",
    "Endpoint host is not a public address",
)


def _open_llm_tab(page: Any) -> None:
    """Navigate to the profile page and activate the LLM settings tab."""
    page.goto(f"{BASE_URL}/profile")
    page.wait_for_load_state("networkidle")
    page.evaluate("() => switchTab('tab-llm', 'panel-llm')")
    expect(page.locator("#panel-llm")).to_have_attribute("aria-hidden", "false")


def _fill_llm_endpoint(page: Any) -> None:
    """Fill the LLM form with an enabled-but-unreachable endpoint."""
    if not page.locator("#llm-enabled").is_checked():
        page.locator("#llm-enabled").check()
    page.locator("#llm-base-url").fill(UNREACHABLE_BASE_URL)
    page.locator("#llm-port").fill(UNREACHABLE_PORT)
    page.locator("#llm-model").fill(TEST_MODEL)
    # 60s is the minimum the LLMConfig model accepts (ge=60) and bounds the
    # worst case for the connection test.
    page.locator("#llm-timeout").fill("60")


class TestLLMConfigFlow:
    """Save/persist/test-connection flow for per-user LLM settings."""

    def test_llm_test_connection_failure_surfaces_error(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _open_llm_tab(page)
        _fill_llm_endpoint(page)

        # Act: save the settings
        page.locator("#llm-save-btn").click()

        # Assert: save succeeds (inline success + toast)
        expect(page.locator("#llm-success")).to_be_visible(timeout=10000)
        expect(page.locator(".toast-success").filter(has_text="LLM settings saved successfully")).to_be_visible(timeout=10000)

        # Assert: the save persisted - reloading retains the values
        page.reload()
        page.wait_for_load_state("networkidle")
        _open_llm_tab(page)
        expect(page.locator("#llm-enabled")).to_be_checked()
        expect(page.locator("#llm-base-url")).to_have_value(UNREACHABLE_BASE_URL)
        expect(page.locator("#llm-port")).to_have_value(UNREACHABLE_PORT)
        expect(page.locator("#llm-model")).to_have_value(TEST_MODEL)

        # Act: test the connection to the unreachable endpoint
        page.locator("#llm-test-btn").click()

        # Assert: the status box appears with an error state (not a hang)
        status_box = page.locator("#llm-test-status")
        expect(status_box).to_be_visible(timeout=60000)
        expect(status_box).to_have_class(re.compile(r"is-error"), timeout=60000)

        # Assert: the message is one of the known connection error strings
        message = page.locator("#llm-test-status-msg").text_content() or ""
        assert any(prefix in message for prefix in KNOWN_ERROR_PREFIXES), (
            f"Unexpected LLM test error message: {message!r}"
        )

        # Assert: the test button is re-enabled (the request completed)
        expect(page.locator("#llm-test-btn")).to_be_enabled()

    def test_invalid_base_url_shows_inline_validation_error(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _open_llm_tab(page)

        # Act: submit a base URL with an unsupported scheme
        page.locator("#llm-base-url").fill("ftp://example.com")
        page.locator("#llm-save-btn").click()

        # Assert: the server's validation message is shown inline
        error = page.locator("#llm-error")
        expect(error).to_be_visible(timeout=10000)
        expect(error).to_have_text("base_url must be an http(s) URL with a hostname")
