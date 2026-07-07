# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for the binary detail page.

Tests the binary detail page including tab navigation, information panel,
functions table, and call graph controls.
"""

from typing import Any

from playwright.sync_api import expect
from tests.e2e.utils import BASE_URL, register_and_login


def _navigate_to_binary_detail(page: Any, tab: str = None) -> None:
    """Navigate to binary detail page and reveal the content for structural testing.

    The binary detail page loads content dynamically via API calls. Since test
    users have no binaries, the API returns 403 and the content stays hidden.
    This helper reveals the static HTML structure for testing.

    Args:
        page: Playwright page object
        tab: Optional tab id to activate ('info', 'functions', 'callgraph')
    """
    page.goto(f"{BASE_URL}/binary/1")
    page.wait_for_load_state("networkidle")
    # Reveal the detail content div so static structure can be tested
    page.evaluate("() => { const el = document.getElementById('detail-content'); if (el) el.style.display = 'block'; }")
    # Optionally activate a specific tab panel
    if tab:
        page.evaluate(f"""() => {{
            var tabButtons = document.querySelectorAll('.tab-btn');
            var tabPanels = document.querySelectorAll('.tab-panel');
            tabButtons.forEach(function(btn) {{
                var isActive = btn.getAttribute('data-tab') === '{tab}';
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            }});
            tabPanels.forEach(function(panel) {{
                var panelId = 'panel-{tab}';
                var isActive = panel.id === panelId;
                panel.classList.toggle('active', isActive);
                panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
            }});
        }}""")


class TestBinaryDetailPage:
    """Tests for the binary detail page layout and structure."""

    def test_binary_detail_page_loads(self, page: Any, server: Any) -> None:
        """Test that the binary detail page loads with correct title."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        expect(page).to_have_title("Glyph - Binary Details")

    def test_binary_detail_shows_page_header(self, page: Any, server: Any) -> None:
        """Test that the binary detail page shows the page header."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        expect(page.locator(".page-header")).to_be_visible()
        expect(page.locator(".page-header .title")).to_contain_text("BINARY DETAILS")

    def test_binary_detail_shows_loading_state(self, page: Any, server: Any) -> None:
        """Test that the binary detail page shows a loading state initially."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")

        # Loading indicator should be present
        loading = page.locator("#detail-loading")
        assert loading.count() == 1

    def test_binary_detail_has_tab_navigation(self, page: Any, server: Any) -> None:
        """Test that the binary detail page has tab navigation."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        expect(page.locator(".tab-nav")).to_be_visible()
        expect(page.locator(".tab-nav")).to_have_attribute("role", "tablist")

    def test_binary_detail_has_info_tab(self, page: Any, server: Any) -> None:
        """Test that the binary detail page has the INFORMATION tab."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        info_tab = page.locator("#tab-info")
        expect(info_tab).to_be_visible()
        expect(info_tab).to_contain_text("INFORMATION")
        expect(info_tab).to_have_attribute("role", "tab")

    def test_binary_detail_has_functions_tab(self, page: Any, server: Any) -> None:
        """Test that the binary detail page has the FUNCTIONS tab."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        functions_tab = page.locator("#tab-functions")
        expect(functions_tab).to_be_visible()
        expect(functions_tab).to_contain_text("FUNCTIONS")
        expect(functions_tab).to_have_attribute("role", "tab")

    def test_binary_detail_has_callgraph_tab(self, page: Any, server: Any) -> None:
        """Test that the binary detail page has the CALL GRAPH tab."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        callgraph_tab = page.locator("#tab-callgraph")
        expect(callgraph_tab).to_be_visible()
        expect(callgraph_tab).to_contain_text("CALL GRAPH")
        expect(callgraph_tab).to_have_attribute("role", "tab")

    def test_info_tab_is_active_by_default(self, page: Any, server: Any) -> None:
        """Test that the INFORMATION tab is active by default."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        info_tab = page.locator("#tab-info")
        expect(info_tab).to_have_attribute("aria-selected", "true")

        info_panel = page.locator("#panel-info")
        expect(info_panel).to_have_attribute("aria-hidden", "false")


class TestBinaryDetailInfoTab:
    """Tests for the INFORMATION tab panel."""

    def test_info_panel_exists(self, page: Any, server: Any) -> None:
        """Test that the info panel exists with correct ARIA attributes."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        info_panel = page.locator("#panel-info")
        expect(info_panel).to_have_attribute("role", "tabpanel")
        expect(info_panel).to_have_attribute("aria-labelledby", "tab-info")

    def test_info_tab_shows_info_grid(self, page: Any, server: Any) -> None:
        """Test that the info tab shows the info grid container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        # Info grid container should exist
        info_grid = page.locator("#info-grid")
        assert info_grid.count() == 1


class TestBinaryDetailFunctionsTab:
    """Tests for the FUNCTIONS tab panel."""

    def test_functions_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the FUNCTIONS tab shows the functions panel."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        # Switch to functions tab via JS
        page.evaluate("() => switchTab('functions')")

        functions_tab = page.locator("#tab-functions")
        expect(functions_tab).to_have_attribute("aria-selected", "true")

        functions_panel = page.locator("#panel-functions")
        expect(functions_panel).to_have_attribute("aria-hidden", "false")

    def test_functions_panel_exists(self, page: Any, server: Any) -> None:
        """Test that the functions panel exists with correct ARIA attributes."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        functions_panel = page.locator("#panel-functions")
        expect(functions_panel).to_have_attribute("role", "tabpanel")
        expect(functions_panel).to_have_attribute("aria-labelledby", "tab-functions")

    def test_functions_tab_shows_functions_table_structure(self, page: Any, server: Any) -> None:
        """Test that the functions tab has the functions table structure."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        # Functions table body should exist
        tbody = page.locator("#functions-tbody")
        assert tbody.count() == 1

    def test_functions_tab_shows_pagination_container(self, page: Any, server: Any) -> None:
        """Test that the functions tab has a pagination container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        pagination = page.locator("#functions-pagination")
        assert pagination.count() == 1

    def test_functions_tab_has_empty_state_container(self, page: Any, server: Any) -> None:
        """Test that the functions tab has an empty state container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator("#functions-empty")
        assert empty_state.count() == 1


class TestBinaryDetailCallGraphTab:
    """Tests for the CALL GRAPH tab panel."""

    def test_callgraph_tab_switches_panel(self, page: Any, server: Any) -> None:
        """Test that clicking the CALL GRAPH tab shows the call graph panel."""
        register_and_login(page)
        _navigate_to_binary_detail(page)

        # Switch to callgraph tab via JS
        page.evaluate("() => switchTab('callgraph')")

        callgraph_tab = page.locator("#tab-callgraph")
        expect(callgraph_tab).to_have_attribute("aria-selected", "true")

        callgraph_panel = page.locator("#panel-callgraph")
        expect(callgraph_panel).to_have_attribute("aria-hidden", "false")

    def test_callgraph_panel_exists(self, page: Any, server: Any) -> None:
        """Test that the call graph panel exists with correct ARIA attributes."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        callgraph_panel = page.locator("#panel-callgraph")
        expect(callgraph_panel).to_have_attribute("role", "tabpanel")
        expect(callgraph_panel).to_have_attribute("aria-labelledby", "tab-callgraph")

    def test_callgraph_shows_load_graph_button(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the LOAD GRAPH button."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#btn-load-graph")).to_be_visible()
        expect(page.locator("#btn-load-graph")).to_contain_text("LOAD GRAPH")

    def test_callgraph_shows_reset_view_button(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the RESET VIEW button."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#btn-reset-view")).to_be_visible()
        expect(page.locator("#btn-reset-view")).to_contain_text("RESET VIEW")

    def test_callgraph_shows_export_svg_button(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the EXPORT SVG button."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#btn-export-svg")).to_be_visible()
        expect(page.locator("#btn-export-svg")).to_contain_text("EXPORT SVG")

    def test_callgraph_shows_stats_section(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the stats section."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator(".callgraph-stats")).to_be_visible()

    def test_callgraph_shows_nodes_stat(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the nodes stat."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#stat-nodes")).to_be_visible()

    def test_callgraph_shows_edges_stat(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the edges stat."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#stat-edges")).to_be_visible()

    def test_callgraph_shows_entry_points_stat(self, page: Any, server: Any) -> None:
        """Test that the call graph tab shows the entry points stat."""
        register_and_login(page)
        _navigate_to_binary_detail(page, "callgraph")

        expect(page.locator("#stat-entry-points")).to_be_visible()

    def test_callgraph_has_loading_indicator(self, page: Any, server: Any) -> None:
        """Test that the call graph tab has a loading indicator."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        loading = page.locator("#graph-loading")
        assert loading.count() == 1

    def test_callgraph_has_empty_state_container(self, page: Any, server: Any) -> None:
        """Test that the call graph tab has an empty state container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        empty_state = page.locator("#graph-empty")
        assert empty_state.count() == 1

    def test_callgraph_has_canvas_container(self, page: Any, server: Any) -> None:
        """Test that the call graph tab has a canvas container."""
        register_and_login(page)

        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("networkidle")

        graph_container = page.locator("#graph-container")
        assert graph_container.count() == 1

        graph_canvas = page.locator("#graph-canvas")
        assert graph_canvas.count() == 1
