# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the dangerous functions scanner page.

Tests that the dangerous functions scanner page loads correctly and displays
the expected UI elements for scanning binaries for insecure functions.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


class TestDangerousFunctionsPage:
    """Tests for the dangerous functions scanner page."""

    def test_dangerous_functions_page_loads(self, page: Any, server: Any) -> None:
        """Test that the dangerous functions page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Dangerous Function Scanner")

    def test_dangerous_functions_shows_scanner_controls(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows the control elements."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check target type selector
        expect(page.locator("#scan-target-type")).to_be_visible()

        # Check target selector
        expect(page.locator("#scan-target-select")).to_be_visible()

        # Check scan button
        expect(page.locator("#scan-btn")).to_be_visible()

        # Check go back button
        expect(page.locator(".back-btn")).to_be_visible()

    def test_dangerous_functions_has_target_type_options(self, page: Any, server: Any) -> None:
        """Test that the scanner page has all three target type options."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check the target type dropdown has the expected options
        target_type = page.locator("#scan-target-type")
        options = target_type.locator("option")
        option_count = options.count()
        assert option_count == 3, f"Expected 3 target type options, got {option_count}"

    def test_dangerous_functions_shows_description(self, page: Any, server: Any) -> None:
        """Test that the scanner page shows a description text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Check description paragraph exists
        expect(page.locator(".scanner-description")).to_be_visible()


def _minimal_elf64() -> bytes:
    """Return a minimal 64-bit ELF header.

    libmagic classifies this as ``application/octet-stream`` (or an ELF type),
    both of which are accepted by the binary upload validator. The file does
    not need to be decompilable for the button-state test.
    """
    import struct

    e_ident = bytes([0x7F, 0x45, 0x4C, 0x46, 0x02, 0x01, 0x01, 0x00, 0x00, 0, 0, 0, 0, 0, 0])
    header = e_ident + struct.pack(
        "<HHIQQQIHHHHHH",
        2,  # e_type: ET_EXEC
        0x3E,  # e_machine: EM_X86_64
        1,  # e_version
        0x401000,  # e_entry
        64,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        56,  # e_phentsize
        1,  # e_phnum
        64,  # e_shentsize
        0,  # e_shnum
        0,  # e_shstrndx
    )
    return header


class TestLlmButtonState:
    """Tests for the 'Check with LLM' button enable/disable behavior."""

    def test_llm_button_disabled_with_no_target(self, page: Any, server: Any) -> None:
        """The LLM button is disabled until a scan target is selected."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # No target selected yet, so the LLM button must be disabled.
        expect(page.locator("#llm-check-btn")).to_be_disabled()

    def test_llm_button_enabled_when_binary_selected(self, page: Any, server: Any, tmp_path: Any) -> None:
        """The LLM button becomes enabled once a binary is selected as the target.

        Regression test: the button used to stay disabled even after a binary
        was selected because it only enabled after a scan produced findings.
        """
        register_and_login(page)

        # Upload a binary so at least one is available in the library.
        elf_path = tmp_path / "sample_elf"
        elf_path.write_bytes(_minimal_elf64())

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        page.locator("#binary-name").fill("llm_btn_regression_bin")
        page.locator("#upload-binary").set_input_files(str(elf_path))

        # Wait until the uploaded binary appears in the library table.
        page.wait_for_selector("#binaries-tbody tr", timeout=30000)

        # Go to the scanner page and switch the target type to binary.
        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        page.locator("#scan-target-type").select_option("binary")

        # Wait for the target dropdown to be populated and enabled.
        page.wait_for_function("() => !document.getElementById('scan-target-select').disabled")

        # Select the first available binary option (index 0 is the placeholder).
        page.locator("#scan-target-select").select_option(index=1)

        # The LLM button must now be enabled, even before any scan has run.
        expect(page.locator("#llm-check-btn")).to_be_enabled()
