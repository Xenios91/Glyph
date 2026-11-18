# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright e2e tests for call graph rendering (gaps C1, C2, C3).

These tests exercise the call-graph visualization on the binary detail page.
The real ``GET /api/v1/call-graph/{binary_id}/graph`` endpoint requires a
decompiled binary (Ghidra/JDK), which is unavailable in this environment, so
every test mocks that endpoint via ``page.route`` and returns the exact
``CallGraphResponse`` envelope (see plans/e2e-harness-brief.md §6).

Covered gaps (plans/e2e-test-coverage-gaps.md):
- C1 — Load & render graph
- C2 — Empty & error states
- C3 — Interactions (reset view, export SVG, tooltip, wheel zoom, node drag)
"""

import json
import time
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login

# Glob matching the call-graph endpoint for the test binary (/binary/1).
GRAPH_URL = "**/api/v1/call-graph/*/graph"

# RGB of a regular (non-entry) node fill (#7dd8d8). Used to locate a node on
# the canvas by pixel-scanning for its fill colour.
NORMAL_NODE_RGB = (125, 216, 216)


def _graph_payload() -> dict:
    """Build a mocked CallGraphResponse envelope: 5 nodes, 6 edges, 2 entries."""
    return {
        "success": True,
        "data": {
            "binary_id": 1,
            "nodes": [
                {"name": "main", "entrypoint": "0x401000", "callers": [], "callees": ["init", "run"]},
                {"name": "init", "entrypoint": "0x401100", "callers": ["main"], "callees": ["process"]},
                {"name": "run", "entrypoint": "0x401200", "callers": ["main"], "callees": ["process", "cleanup"]},
                {"name": "process", "entrypoint": "0x401300", "callers": ["init", "run"], "callees": []},
                {"name": "cleanup", "entrypoint": "0x401400", "callers": ["run"], "callees": []},
            ],
            "edges": [
                {"caller": "main", "callee": "init", "call_count": 1},
                {"caller": "main", "callee": "run", "call_count": 1},
                {"caller": "init", "callee": "process", "call_count": 2},
                {"caller": "run", "callee": "process", "call_count": 1},
                {"caller": "run", "callee": "cleanup", "call_count": 1},
                {"caller": "main", "callee": "cleanup", "call_count": 1},
            ],
            "total_nodes": 5,
            "total_edges": 6,
            "entry_points": ["main", "init"],
        },
        "message": "Call graph generated",
        "metadata": {"timestamp": "2026-11-14T00:00:00Z", "request_id": "e2e-cg-1"},
    }


def _empty_payload() -> dict:
    """Build a mocked CallGraphResponse envelope containing no nodes."""
    return {
        "success": True,
        "data": {
            "binary_id": 1,
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "entry_points": [],
        },
        "message": "Call graph generated",
        "metadata": {"timestamp": "2026-11-14T00:00:00Z", "request_id": "e2e-cg-empty"},
    }


def _goto_callgraph_tab(page: Any) -> None:
    """Navigate to the binary detail page and reveal the call-graph tab.

    The test user owns no binaries, so the detail API returns 403 and the
    content stays hidden. We force-reveal the static structure and activate the
    call-graph tab so the canvas obtains a real layout size.
    """
    page.goto(f"{BASE_URL}/binary/1")
    page.wait_for_load_state("networkidle")
    page.evaluate(
        "() => { const el = document.getElementById('detail-content'); if (el) el.classList.remove('is-hidden'); }"
    )
    page.evaluate("() => switchTab('callgraph')")


def _canvas_data_url(page: Any) -> str:
    """Return the canvas contents as a data URL (empty string if absent)."""
    return page.evaluate(
        "() => { const c = document.getElementById('graph-canvas'); return c ? c.toDataURL() : ''; }"
    )


def _wait_for_canvas_stable(page: Any, timeout_ms: int = 8000, interval_ms: int = 120) -> None:
    """Wait until the force layout settles (two consecutive identical frames)."""
    prev = None
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        cur = _canvas_data_url(page)
        if cur and cur == prev:
            return
        prev = cur
        page.wait_for_timeout(interval_ms)


def _wait_for_canvas_change(page: Any, baseline: str, timeout_ms: int = 4000, interval_ms: int = 60) -> None:
    """Wait until the canvas differs from the baseline capture."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if _canvas_data_url(page) != baseline:
            return
        page.wait_for_timeout(interval_ms)


def _find_node_page_pos(page: Any, rgb: tuple, tolerance: int = 45) -> dict | None:
    """Locate a rendered node by pixel-scanning the canvas for its fill colour.

    Returns the node centre in page (viewport) coordinates, or None if no
    matching cluster is found.
    """
    r0, g0, b0 = rgb
    return page.evaluate(
        """([r0, g0, b0, tol]) => {
            const canvas = document.getElementById('graph-canvas');
            if (!canvas) return null;
            const ctx = canvas.getContext('2d');
            const w = canvas.width, h = canvas.height;
            if (!w || !h) return null;
            const data = ctx.getImageData(0, 0, w, h).data;
            const cell = 24;
            const cols = Math.ceil(w / cell);
            const rows = Math.ceil(h / cell);
            const counts = new Array(cols * rows).fill(0);
            for (let y = 0; y < h; y += 2) {
                for (let x = 0; x < w; x += 2) {
                    const i = (y * w + x) * 4;
                    if (data[i + 3] < 128) continue;
                    if (Math.abs(data[i] - r0) <= tol && Math.abs(data[i + 1] - g0) <= tol && Math.abs(data[i + 2] - b0) <= tol) {
                        counts[Math.floor(x / cell) + Math.floor(y / cell) * cols]++;
                    }
                }
            }
            let best = -1, bestCount = 0;
            for (let k = 0; k < counts.length; k++) {
                if (counts[k] > bestCount) { bestCount = counts[k]; best = k; }
            }
            if (best < 0) return null;
            const bx = Math.floor(best / cols) * cell;
            const by = (best % cols) * cell;
            const x1 = Math.min(w, bx + cell), y1 = Math.min(h, by + cell);
            let sx = 0, sy = 0, n = 0;
            for (let y = by; y < y1; y++) {
                for (let x = bx; x < x1; x++) {
                    const i = (y * w + x) * 4;
                    if (data[i + 3] < 128) continue;
                    if (Math.abs(data[i] - r0) <= tol && Math.abs(data[i + 1] - g0) <= tol && Math.abs(data[i + 2] - b0) <= tol) {
                        sx += x; sy += y; n++;
                    }
                }
            }
            if (n === 0) return null;
            const dpr = window.devicePixelRatio || 1;
            const rect = canvas.getBoundingClientRect();
            return { x: rect.left + (sx / n) / dpr, y: rect.top + (sy / n) / dpr };
        }""",
        [r0, g0, b0, tolerance],
    )


def _load_graph_simple(page: Any) -> None:
    """Mock the endpoint, load the graph, and wait for the layout to settle."""
    payload = _graph_payload()
    page.route(
        GRAPH_URL,
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)),
    )
    page.click("#btn-load-graph")
    expect(page.locator("#graph-loading")).to_be_hidden()
    expect(page.locator("#graph-container")).to_be_visible()
    page.locator("#graph-canvas").scroll_into_view_if_needed()
    _wait_for_canvas_stable(page)
    page.unroute(GRAPH_URL)


class TestCallGraphLoadAndRender:
    """C1 — Load & render the call graph from a mocked endpoint."""

    def test_load_graph_renders(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        payload = _graph_payload()
        held: list = []

        def hold_handler(route: Any) -> None:
            # Do not fulfill: keep the request pending so the loading state
            # remains visible deterministically.
            held.append(route)

        page.route(GRAPH_URL, hold_handler)

        try:
            # Act
            page.click("#btn-load-graph")

            # Wait until the request is intercepted (loading is shown while pending).
            deadline = time.time() + 5
            while not held and time.time() < deadline:
                page.wait_for_timeout(20)
            assert held, "graph request was not intercepted by the mock route"

            # Assert: loading indicator is visible while the request is in flight.
            expect(page.locator("#graph-loading")).to_be_visible()

            # Fulfil the held request with the mocked CallGraphResponse.
            held[0].fulfill(status=200, content_type="application/json", body=json.dumps(payload))

            # Assert: loading hidden, container + canvas visible.
            expect(page.locator("#graph-loading")).to_be_hidden()
            expect(page.locator("#graph-container")).to_be_visible()
            expect(page.locator("#graph-canvas")).to_be_visible()

            # Assert: stats match the mocked response.
            expect(page.locator("#stat-nodes")).to_have_text("5")
            expect(page.locator("#stat-edges")).to_have_text("6")
            expect(page.locator("#stat-entry-points")).to_have_text("2")

            # Assert: controls are enabled once the graph is loaded.
            expect(page.locator("#btn-reset-view")).to_be_enabled()
            expect(page.locator("#btn-export-svg")).to_be_enabled()

            # Assert: the canvas actually rendered nodes/edges (non-blank).
            page.locator("#graph-canvas").scroll_into_view_if_needed()
            _wait_for_canvas_stable(page)
            non_blank = page.evaluate(
                """() => {
                    const c = document.getElementById('graph-canvas');
                    const ctx = c.getContext('2d');
                    const d = ctx.getImageData(0, 0, c.width, c.height).data;
                    let n = 0;
                    for (let i = 3; i < d.length; i += 4) { if (d[i] > 0) n++; }
                    return n;
                }"""
            )
            assert non_blank > 100, f"canvas appears blank (only {non_blank} non-transparent px)"
        finally:
            page.unroute(GRAPH_URL)


class TestCallGraphEmptyAndError:
    """C2 — Empty and error states of the call graph."""

    def test_empty_graph_shows_empty_state(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        payload = _empty_payload()
        page.route(
            GRAPH_URL,
            lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)),
        )
        try:
            # Act
            page.click("#btn-load-graph")

            # Assert: the empty state is shown and the canvas stays hidden.
            expect(page.locator("#graph-empty")).to_be_visible()
            expect(page.locator("#graph-loading")).to_be_hidden()
            expect(page.locator("#graph-container")).to_be_hidden()
            expect(page.locator("#btn-load-graph")).to_be_enabled()
        finally:
            page.unroute(GRAPH_URL)

    def test_api_error_shows_error_state(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        page.route(
            GRAPH_URL,
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"detail": "Internal Server Error"}),
            ),
        )
        try:
            # Act
            page.click("#btn-load-graph")

            # Assert: the error state is shown with the API error message.
            expect(page.locator("#graph-error")).to_be_visible()
            expect(page.locator("#graph-error-message")).to_have_text("Internal Server Error")
            expect(page.locator("#graph-loading")).to_be_hidden()
            expect(page.locator("#graph-container")).to_be_hidden()
            expect(page.locator("#btn-load-graph")).to_be_enabled()
        finally:
            page.unroute(GRAPH_URL)


class TestCallGraphInteractions:
    """C3 — Call graph interactions: reset, export, tooltip, zoom, drag."""

    def test_reset_view_recenters(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        _load_graph_simple(page)
        base = _canvas_data_url(page)
        box = page.locator("#graph-canvas").bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Act: zoom in to change the view, then reset it.
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -240)
        _wait_for_canvas_change(page, base)
        zoomed = _canvas_data_url(page)
        assert zoomed != base, "wheel zoom did not change the rendered view"

        page.click("#btn-reset-view")
        _wait_for_canvas_change(page, zoomed)
        reset = _canvas_data_url(page)

        # Assert: the view changed after resetting (re-centred).
        assert reset != zoomed, "reset view did not change the rendered view"

    def test_export_svg_download(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        _load_graph_simple(page)

        # Act: trigger the SVG export and capture the download.
        with page.expect_download() as download_info:
            page.click("#btn-export-svg")
        download = download_info.value

        # Assert: a download with the expected filename was produced.
        assert download.suggested_filename == "call_graph_1.svg"

    def test_tooltip_on_hover(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        _load_graph_simple(page)
        pos = _find_node_page_pos(page, NORMAL_NODE_RGB)
        assert pos is not None, "could not locate a rendered node on the canvas"

        # Act: hover the located node.
        page.mouse.move(pos["x"], pos["y"], steps=2)

        # Assert: the tooltip is shown with the expected structure.
        expect(page.locator("#graph-tooltip")).to_be_visible()
        expect(page.locator("#graph-tooltip .tooltip-name")).to_have_count(1)
        expect(page.locator("#graph-tooltip")).to_contain_text("Address:")
        expect(page.locator("#graph-tooltip")).to_contain_text("Callers:")
        expect(page.locator("#graph-tooltip")).to_contain_text("Callees:")

    def test_wheel_zoom(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        _load_graph_simple(page)
        base = _canvas_data_url(page)
        box = page.locator("#graph-canvas").bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # Act: scroll the wheel to zoom.
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -240)
        _wait_for_canvas_change(page, base)
        after = _canvas_data_url(page)

        # Assert: the rendered view changed (zoom applied).
        assert after != base, "wheel zoom did not change the rendered view"

    def test_node_drag(self, page: Any, server: Any) -> None:
        # Arrange
        register_and_login(page)
        _goto_callgraph_tab(page)
        _load_graph_simple(page)
        pos = _find_node_page_pos(page, NORMAL_NODE_RGB)
        assert pos is not None, "could not locate a rendered node on the canvas"
        base = _canvas_data_url(page)

        # Act: drag the located node to a new position.
        page.mouse.move(pos["x"], pos["y"])
        page.mouse.down()
        page.mouse.move(pos["x"] + 50, pos["y"] + 30, steps=5)
        page.mouse.up()
        _wait_for_canvas_change(page, base)
        after = _canvas_data_url(page)

        # Assert: the rendered view changed (node moved).
        assert after != base, "dragging a node did not change the rendered view"
