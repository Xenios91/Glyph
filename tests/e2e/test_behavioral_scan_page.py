# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the behavioral scan page.

Tests that the behavioral scan page loads correctly and displays the
expected UI elements for scanning binaries for malware-associated
behaviors using the behavioral signature catalog.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestBehavioralScanPage:
    """Tests for the behavioral scan page structure and controls."""

    def test_behavioral_scan_page_loads(self, page: Any, server: Any) -> None:
        """Test that the behavioral scan page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Behavioral Scan")

    def test_behavioral_scan_shows_scanner_controls(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows the control elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # Check target type selector
        expect(page.locator("#scan-target-type")).to_be_visible()

        # Check target selector
        expect(page.locator("#scan-target-select")).to_be_visible()

        # Check scan button
        expect(page.locator("#scan-btn")).to_be_visible()

        # Check go back button
        expect(page.locator(".back-btn")).to_be_visible()

    def test_behavioral_scan_has_target_type_options(self, page: Any, server: Any) -> None:
        """Test that the scanner page has all three target type options."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # Check the target type dropdown has the expected options
        target_type = page.locator("#scan-target-type")
        options = target_type.locator("option")
        option_count = options.count()
        assert option_count == 3, f"Expected 3 target type options, got {option_count}"

        # Verify the specific option values
        values = [options.nth(i).get_attribute("value") for i in range(option_count)]
        assert values == ["model", "prediction", "binary"], f"Unexpected option values: {values}"

    def test_behavioral_scan_shows_description(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows a description text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # Check description paragraph exists
        expect(page.locator(".scanner-description")).to_be_visible()

    def test_behavioral_scan_shows_severity_cards(self, page: Any, server: Any) -> None:
        """Test that the severity cards are present in the summary section."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # The summary section is hidden until a scan completes, but the
        # severity card elements exist in the DOM.
        expect(page.locator("#critical-count")).to_have_count(1)
        expect(page.locator("#high-count")).to_have_count(1)
        expect(page.locator("#medium-count")).to_have_count(1)
        expect(page.locator("#low-count")).to_have_count(1)
        expect(page.locator("#total-count")).to_have_count(1)

    def test_behavioral_scan_results_table_columns(self, page: Any, server: Any) -> None:
        """Test that the results table has the expected column headers."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # The table headers exist in the DOM (hidden until results are shown).
        headers = page.locator(".scan-results-table th")
        header_count = headers.count()
        assert header_count == 4, f"Expected 4 column headers, got {header_count}"

        # Verify the specific column headers
        expected_headers = ["Behavior", "Category", "Containing Function", "Severity"]
        for i, expected in enumerate(expected_headers):
            actual = headers.nth(i).inner_text().strip()
            assert actual == expected, f"Column {i}: expected '{expected}', got '{actual}'"

    def test_behavioral_scan_stored_results_banner(self, page: Any, server: Any) -> None:
        """Test that the stored results banner exists in the DOM (hidden by default)."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # The banner exists but is hidden by default
        banner = page.locator("#stored-results-banner")
        expect(banner).to_have_count(1)
        expect(banner).to_be_hidden()

        # The banner contains the view and delete buttons
        expect(page.locator("#view-stored-btn")).to_have_count(1)
        expect(page.locator("#delete-stored-btn")).to_have_count(1)

    def test_behavioral_scan_finding_modal_structure(self, page: Any, server: Any) -> None:
        """Test that the finding detail modal has the expected structure."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # The modal exists in the DOM (hidden by default)
        modal = page.locator("#context-modal")
        expect(modal).to_have_count(1)
        expect(modal).to_be_hidden()

        # The modal has the expected metadata fields
        expect(page.locator("#modal-behavior-name")).to_have_count(1)
        expect(page.locator("#modal-behavior-category")).to_have_count(1)
        expect(page.locator("#modal-containing-function")).to_have_count(1)
        expect(page.locator("#modal-severity")).to_have_count(1)
        expect(page.locator("#modal-attck")).to_have_count(1)
        expect(page.locator("#modal-description")).to_have_count(1)
        expect(page.locator("#modal-matched-evidence")).to_have_count(1)

        # The modal has a close button
        expect(page.locator("#modal-close-btn")).to_have_count(1)

    def test_behavioral_scan_no_llm_controls(self, page: Any, server: Any) -> None:
        """Test that the behavioral scan page has NO LLM analysis controls.

        Unlike the dangerous functions page, the behavioral scan page does not
        offer LLM-based analysis. The LLM check button, LLM modal, and clear
        LLM results button must all be absent.
        """
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # LLM check button must not exist
        expect(page.locator("#llm-check-btn")).to_have_count(0)

        # LLM modal must not exist
        expect(page.locator("#llm-modal")).to_have_count(0)
        expect(page.locator("#llm-modal-analysis")).to_have_count(0)

        # Clear LLM results button must not exist
        expect(page.locator("#clear-stored-btn")).to_have_count(0)

    def test_behavioral_scan_no_taint_controls(self, page: Any, server: Any) -> None:
        """Test that the behavioral scan page has NO taint analysis controls.

        Unlike the dangerous functions page, the behavioral scan page does not
        offer per-finding taint analysis. The taint analyze button must be absent.
        """
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # Taint analysis button must not exist
        expect(page.locator("#taint-analyze-btn")).to_have_count(0)

    def test_behavioral_scan_navbar_link_present(self, page: Any, server: Any) -> None:
        """Test that the behavioral scan link is present in the ANALYSIS navbar dropdown."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")

        # Open the ANALYSIS dropdown via JavaScript (hover is unreliable in headless)
        page.evaluate("""
            const analysisMenu = document.getElementById('analysis-menu');
            const toggle = analysisMenu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
            if (analysisMenu && toggle) {
                analysisMenu.classList.add('is-open');
                toggle.setAttribute('aria-expanded', 'true');
            }
        """)

        # The behavioral scan link should be present in the dropdown
        behavioral_link = page.locator('a[role="menuitem"][aria-label="Behavioral Scan"]')
        expect(behavioral_link).to_have_count(1)
        expect(behavioral_link).to_have_attribute("href", "/getBehavioralScan")

    def test_behavioral_scan_scan_button_disabled_initially(self, page: Any, server: Any) -> None:
        """Test that the scan button is disabled until a target is selected."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getBehavioralScan")
        page.wait_for_load_state("networkidle")

        # No target selected: the button must be disabled
        expect(page.locator("#scan-btn")).to_be_disabled()
