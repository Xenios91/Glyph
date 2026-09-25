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


class TestViewStoredButtonState:
    """Tests for the 'View Stored Results' button enable/disable behavior."""

    def test_view_stored_button_disabled_after_results_loaded(self, page: Any, server: Any, tmp_path: Any) -> None:
        """The 'View Stored Results' button is disabled once the stored
        results for the selected target are displayed on the page.

        Regression test: the button used to stay enabled after the stored
        results had been loaded, so it could be clicked repeatedly even
        though there was nothing left to load.
        """
        register_and_login(page)

        # Upload a binary so at least one is available in the library.
        elf_path = tmp_path / "sample_elf"
        elf_path.write_bytes(_minimal_elf64())

        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        page.locator("#binary-name").fill("view_stored_btn_bin")
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

        # No stored report yet: the banner (and its buttons) are hidden.
        expect(page.locator("#stored-results-banner")).to_be_hidden()

        # Run a scan; the report is persisted and the results are displayed.
        page.locator("#scan-btn").click()
        page.wait_for_selector("#scan-summary", state="visible", timeout=30000)

        # The banner now shows, but the stored results are already on
        # screen, so the "View Stored Results" button must be disabled.
        expect(page.locator("#stored-results-banner")).to_be_visible()
        expect(page.locator("#view-stored-btn")).to_be_disabled()

        # Reload the page: the stored results are restored automatically on
        # target selection, so the button must stay disabled.
        page.reload()
        page.wait_for_load_state("networkidle")

        page.locator("#scan-target-type").select_option("binary")
        page.wait_for_function("() => !document.getElementById('scan-target-select').disabled")
        page.locator("#scan-target-select").select_option(index=1)

        page.wait_for_selector("#stored-results-banner", state="visible", timeout=30000)
        expect(page.locator("#view-stored-btn")).to_be_disabled()


class TestClearLlmButtonState:
    """Tests for the 'Clear LLM Results' button enable/disable behavior."""

    def test_clear_llm_button_disabled_without_results(self, page: Any, server: Any) -> None:
        """The 'Clear LLM Results' button is disabled when the current target
        has no LLM analysis results to clear."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # No findings and no LLM results: the button must stay disabled.
        page.evaluate(
            """() => {
                lastScanData = null;
                llmResults = {};
                hasStoredLlmResults = false;
                updateClearLlmButtonState();
            }"""
        )

        expect(page.locator("#clear-stored-btn")).to_be_disabled()

    def test_clear_llm_button_enabled_when_findings_have_llm_results(self, page: Any, server: Any) -> None:
        """The 'Clear LLM Results' button becomes enabled dynamically once LLM
        results exist for the findings currently on screen.

        Regression test: the button only re-evaluated its state when the scan
        target was selected, so after a scan's findings were analyzed with the
        LLM the button stayed disabled even though results existed to clear.
        """
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Simulate the state right after a scan produced findings for the
        # selected target and the LLM analysis of those findings completed:
        # fresh results are in memory while the stored-results flag still
        # reflects the pre-analysis check.
        page.evaluate(
            """() => {
                targetTypeSelect.value = 'model';
                targetSelect.value = 'sim-target';
                lastScanData = {
                    model_name: 'sim-target',
                    results: [
                        {
                            function_name: 'strcpy',
                            containing_function: 'main',
                            entrypoint: '0x401000',
                        },
                    ],
                };
                llmResults = {
                    0: {
                        status: 'success',
                        analysis: 'simulated analysis',
                        error: '',
                        model: 'simulated-model',
                        source: 'fresh',
                    },
                };
                hasStoredLlmResults = false;
                updateClearLlmButtonState();
            }"""
        )

        expect(page.locator("#clear-stored-btn")).to_be_enabled()


class TestLlmPendingSpinners:
    """Tests for the per-row LLM loading spinners shown while analysis runs."""

    def test_llm_spinner_shown_while_analysis_pending(self, page: Any, server: Any) -> None:
        """Each LLM cell shows a spinner badge while its finding's analysis
        is in flight, and the spinner is replaced once the result arrives."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Build the results table as if a scan had just produced two findings
        page.evaluate(
            """() => {
                displayResults(
                    {
                        model_name: 'spinner-target',
                        critical_count: 1,
                        high_count: 1,
                        medium_count: 0,
                        low_count: 0,
                        total_found: 2,
                        total_functions_scanned: 100,
                        results: [
                            {
                                function_name: 'strcpy',
                                containing_function: 'main',
                                entrypoint: '0x401000',
                            },
                            {
                                function_name: 'gets',
                                containing_function: 'read_input',
                                entrypoint: '0x402000',
                            },
                        ],
                    },
                    'spinner-target'
                );
            }"""
        )
        page.wait_for_selector("#scan-results-body tr[data-index='0']")

        # Simulate the state right after "Check with LLM" was clicked: the
        # LLM request is in flight, so the first row's index is pending while
        # the second already has a result.
        page.evaluate(
            """() => {
                llmResults[1] = {
                    status: 'success',
                    analysis: 'simulated analysis',
                    error: '',
                    model: 'simulated-model',
                    source: 'fresh',
                };
                llmPendingIndices.add(0);
                renderLlmBadges();
            }"""
        )

        # The pending row shows the spinner badge, the finished row its result.
        pending_badge = page.locator("#scan-results-body tr[data-index='0'] .llm-badge-pending")
        expect(pending_badge).to_be_visible()
        expect(pending_badge.locator(".llm-spinner")).to_be_visible()
        expect(page.locator("#scan-results-body tr[data-index='1'] .llm-badge-success")).to_be_visible()

        # When the pending result arrives, the spinner is replaced by the
        # result badge.
        page.evaluate(
            """() => {
                llmResults[0] = {
                    status: 'success',
                    analysis: 'simulated analysis',
                    error: '',
                    model: 'simulated-model',
                    source: 'fresh',
                };
                llmPendingIndices.clear();
                renderLlmBadges();
            }"""
        )

        expect(page.locator("#scan-results-body .llm-badge-pending")).to_have_count(0)
        expect(page.locator("#scan-results-body tr[data-index='0'] .llm-badge-success")).to_be_visible()


class TestLlmMarkdownPreview:
    """Tests that the LLM analysis modal renders its content as a Markdown
    preview instead of raw text."""

    def _open_llm_modal_with_analysis(self, page: Any, analysis: str) -> None:
        """Build scan results plus one successful LLM result and open the
        LLM modal for that finding."""
        page.evaluate(
            """(analysis) => {
                targetTypeSelect.value = 'model';
                targetSelect.value = 'md-target';
                lastScanData = {
                    model_name: 'md-target',
                    results: [
                        {
                            function_name: 'strcpy',
                            containing_function: 'main',
                            entrypoint: '0x401000',
                        },
                    ],
                };
                llmResults = {
                    0: {
                        status: 'success',
                        analysis: analysis,
                        error: '',
                        model: 'simulated-model',
                        source: 'fresh',
                    },
                };
                openLlmModal(0);
            }""",
            analysis,
        )

    def test_llm_modal_renders_markdown_preview(self, page: Any, server: Any) -> None:
        """The LLM analysis is rendered as formatted Markdown (headings,
        lists, code) rather than shown as raw text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # The Markdown renderer script must be loaded on the page.
        expect(page.locator("script[src*='js/markdown.js']")).to_have_count(1)
        assert page.evaluate("() => typeof renderMarkdown === 'function'") is True

        self._open_llm_modal_with_analysis(
            page,
            "# Exploitability\n\nThis is **plausible** because `strcpy` copies without bounds.\n\n"
            "## Risk\n\n- High confidence\n- Disagree with catalog severity\n\n"
            "```\nstrcpy(buf, input);\n```\n",
        )

        analysis = page.locator("#llm-modal-analysis")
        expect(analysis).to_be_visible()

        # Markdown structure is rendered as real elements, not raw text.
        expect(analysis.locator("h1")).to_have_text("Exploitability")
        expect(analysis.locator("h2")).to_have_text("Risk")
        expect(analysis.locator("strong")).to_have_text("plausible")
        expect(analysis.locator("code").first).to_have_text("strcpy")
        expect(analysis.locator("li")).to_have_count(2)
        expect(analysis.locator("pre code")).to_contain_text("strcpy(buf, input);")

        # The raw Markdown source markers must not be visible as literal text.
        expect(analysis).not_to_contain_text("**plausible**")
        expect(analysis).not_to_contain_text("```")

    def test_llm_modal_escapes_raw_html_in_analysis(self, page: Any, server: Any) -> None:
        """Raw HTML in the LLM analysis is escaped and shown as literal
        text; it is never injected into the DOM."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        self._open_llm_modal_with_analysis(
            page,
            "Analysis with <script>window.__pwned = true;</script> and <b>bold</b> tags.",
        )

        analysis = page.locator("#llm-modal-analysis")
        expect(analysis).to_be_visible()

        # No script or bold element may be created from the raw HTML.
        expect(analysis.locator("script")).to_have_count(0)
        expect(analysis.locator("b")).to_have_count(0)
        # The raw tags are displayed as escaped literal text.
        expect(analysis).to_contain_text("<script>")
        expect(analysis).to_contain_text("<b>bold</b>")
        # The payload never executed.
        assert page.evaluate("() => window.__pwned") is None

    def test_llm_modal_renders_markdown_links_safely(self, page: Any, server: Any) -> None:
        """Markdown links are rendered as anchors, but unsafe URL schemes
        (e.g. javascript:) are dropped and kept as plain text."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        self._open_llm_modal_with_analysis(
            page,
            "See [CWE-120](https://cwe.mitre.org/data/definitions/120.html) "
            "and [unsafe](javascript:alert(1)) for details.",
        )

        analysis = page.locator("#llm-modal-analysis")
        expect(analysis).to_be_visible()

        # The safe link is rendered as an anchor with its target URL.
        safe_link = analysis.locator("a", has_text="CWE-120")
        expect(safe_link).to_have_attribute(
            "href", "https://cwe.mitre.org/data/definitions/120.html"
        )
        # The unsafe link is not rendered as an anchor.
        expect(analysis.locator("a", has_text="unsafe")).to_have_count(0)
        expect(analysis).to_contain_text("unsafe")

    def test_llm_modal_invalid_markdown_degrades_gracefully(self, page: Any, server: Any) -> None:
        """Malformed Markdown (unclosed fences, unbalanced emphasis, broken
        links, stray table pipes) must not break the modal: the content is
        still displayed, degraded to plain text where needed, and no page
        error is raised."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/getDangerousFunctions")
        page.wait_for_load_state("networkidle")

        # Collect page errors to prove the renderer did not throw.
        page_errors: list = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        self._open_llm_modal_with_analysis(
            page,
            "Unclosed fence:\n```\nint x = 1;\n\n"
            "**unclosed bold and *unclosed italic\n"
            "[broken link with no url\n"
            "| header | without separator row\n"
            "~~~unclosed tilde fence\n"
            "#unclosed heading marker text\n",
        )

        analysis = page.locator("#llm-modal-analysis")
        expect(analysis).to_be_visible()

        # The modal content is non-empty: the source text is displayed even
        # though it is not valid Markdown.
        expect(analysis).to_contain_text("int x = 1;")
        expect(analysis).to_contain_text("unclosed bold")
        expect(analysis).to_contain_text("broken link with no url")
        expect(analysis).to_contain_text("header")

        # The renderer must not have thrown any page-level error.
        assert page_errors == []
