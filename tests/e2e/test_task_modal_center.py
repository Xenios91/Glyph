# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for task modal centering.

Tests that the task selection modal is properly centered on the viewport
when displayed on the binary library page.
"""

from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login


class TestTaskModalCentering:
    """Tests for task modal positioning."""

    def test_task_modal_is_centered_on_viewport(self, page: Any, server: Any) -> None:
        """Test that the task modal overlay is centered in the viewport."""
        register_and_login(page)

        # Navigate to binary library
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Wait for binary_library.js to load and expose functions
        page.wait_for_function("() => typeof window.hideTaskSelectionModal === 'function'", timeout=10000)

        # Directly manipulate DOM to show modal (mimicking what showTaskSelectionModal does)
        page.evaluate("""() => {
            const overlay = document.getElementById('task-modal-overlay');
            if (overlay) {
                overlay.classList.add('is-visible');
            }
        }""")
        page.wait_for_timeout(500)

        # Get overlay styles
        overlay_info = page.evaluate("""() => {
            const overlay = document.getElementById('task-modal-overlay');
            const s = window.getComputedStyle(overlay);
            return {
                classList: overlay.className,
                display: s.display,
                justifyContent: s.justifyContent,
                alignItems: s.alignItems,
                position: s.position,
            };
        }""")

        # Verify overlay uses flexbox centering
        assert overlay_info["display"] == "flex", f"Expected display:flex, got {overlay_info['display']}"
        assert overlay_info["justifyContent"] == "center", f"Expected justifyContent:center, got {overlay_info['justifyContent']}"
        assert overlay_info["alignItems"] == "center", f"Expected alignItems:center, got {overlay_info['alignItems']}"

    def test_task_modal_position_is_centered(self, page: Any, server: Any) -> None:
        """Test that the task modal element is visually centered on screen."""
        register_and_login(page)

        # Navigate to binary library
        page.goto(f"{BASE_URL}/binary-library")
        page.wait_for_load_state("networkidle")

        # Wait for binary_library.js to load
        page.wait_for_function("() => typeof window.hideTaskSelectionModal === 'function'", timeout=10000)

        # Show modal
        page.evaluate("""() => {
            const overlay = document.getElementById('task-modal-overlay');
            if (overlay) {
                overlay.classList.add('is-visible');
            }
        }""")
        page.wait_for_timeout(500)

        # Get modal bounding box and viewport size
        result = page.evaluate("""() => {
            const modal = document.querySelector('.task-modal');
            const rect = modal.getBoundingClientRect();
            return {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
            };
        }""")

        # Calculate centers
        modal_center_x = result["x"] + result["width"] / 2
        modal_center_y = result["y"] + result["height"] / 2
        viewport_center_x = result["viewportWidth"] / 2
        viewport_center_y = result["viewportHeight"] / 2

        # Allow 20px tolerance for rounding differences
        offset_x = abs(modal_center_x - viewport_center_x)
        offset_y = abs(modal_center_y - viewport_center_y)
        assert offset_x < 20, f"Modal is not horizontally centered (offset: {offset_x}px)"
        assert offset_y < 20, f"Modal is not vertically centered (offset: {offset_y}px)"
