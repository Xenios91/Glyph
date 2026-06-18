"""Test that the task modal is centered on the page."""
import time
import asyncio
from playwright.async_api import async_playwright, Page

BASE_URL = "http://127.0.0.1:8000"


def generate_unique_username():
    timestamp = int(time.time() * 1000) % 100000
    return f"testuser_{timestamp}"


async def register_and_login(page: Page) -> None:
    username = generate_unique_username()
    email = f"{username}@test.com"
    password = "SecurePass123!"

    await page.goto(f"{BASE_URL}/register", wait_until="load")
    await page.wait_for_selector("#registerForm[data-initialized='true']", timeout=10000)
    await page.locator("#username").fill(username)
    await page.locator("#email").fill(email)
    await page.locator("#full_name").fill("Test User")
    await page.locator("#password").fill(password)
    await page.locator("#confirm_password").fill(password)
    await page.locator("#register-submit-btn").click()
    await page.wait_for_url(f"{BASE_URL}/login")

    await page.locator("#username").fill(username)
    await page.locator("#password").fill(password)
    await page.locator("#login-submit-btn").click()
    await page.wait_for_url(f"{BASE_URL}/")
    print(f"Logged in as {username}")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await register_and_login(page)

        response = await page.goto(f"{BASE_URL}/binary-library", wait_until="load")
        await page.wait_for_timeout(3000)

        print(f"Status: {response.status if response else 'no response'}")
        print(f"Final URL: {page.url}")

        viewport = page.viewport_size
        print(f"Viewport: {viewport}")

        # Wait for binary_library.js to load and expose functions
        await page.wait_for_function("() => typeof window.hideTaskSelectionModal === 'function'", timeout=5000)

        # Directly manipulate DOM to show modal (mimicking what showTaskSelectionModal does)
        await page.evaluate("""() => {
            const overlay = document.getElementById('task-modal-overlay');
            if (overlay) {
                overlay.classList.add('is-visible');
            }
        }""")
        await page.wait_for_timeout(1000)

        overlay_info = await page.evaluate("""() => {
            const overlay = document.getElementById('task-modal-overlay');
            const s = window.getComputedStyle(overlay);
            return {
                classList: overlay.className,
                display: s.display,
                justifyContent: s.justifyContent,
                alignItems: s.alignItems,
                position: s.position,
                width: s.width,
                height: s.height,
                top: s.top,
                left: s.left
            };
        }""")
        print(f"Overlay info: {overlay_info}")

        modal_bbox = await page.locator(".task-modal").first.bounding_box()
        print(f"Modal bounding box: {modal_bbox}")

        if modal_bbox and viewport:
            modal_center_x = modal_bbox["x"] + modal_bbox["width"] / 2
            modal_center_y = modal_bbox["y"] + modal_bbox["height"] / 2
            viewport_center_x = viewport["width"] / 2
            viewport_center_y = viewport["height"] / 2
            offset_x = abs(modal_center_x - viewport_center_x)
            offset_y = abs(modal_center_y - viewport_center_y)
            print(f"Modal center: ({modal_center_x}, {modal_center_y})")
            print(f"Viewport center: ({viewport_center_x}, {viewport_center_y})")
            print(f"Offset X: {offset_x}px, Offset Y: {offset_y}px")

            if offset_x < 10 and offset_y < 10:
                print("SUCCESS: Modal is centered on the page!")
            else:
                print(f"FAILURE: Modal is NOT centered (offset X: {offset_x}px, Y: {offset_y}px)")

        await page.screenshot(path="/workspaces/Glyph/tests/e2e/screenshots/task_modal_center.png", full_page=True)
        print("Screenshot saved")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
