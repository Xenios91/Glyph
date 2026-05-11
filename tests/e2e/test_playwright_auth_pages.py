# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Playwright tests for authentication page loading.

Note: Playwright has incomplete type stubs, so we suppress unknown type errors.
See: https://github.com/microsoft/pyright/discussions/6243
"""

from typing import Any

import sys
import subprocess
import time
import os
import pytest
import requests
from playwright.sync_api import expect


BASE_URL = "http://127.0.0.1:8000"


def wait_for_server(url: str, timeout: int = 30) -> None:
    """Wait for the server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code < 500:
                return
        except requests.ConnectionError:
            time.sleep(1)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def server() -> Any:
    """Start the FastAPI server for testing."""
    env = os.environ.copy()
    env["GLYPH_JWT_SECRET_KEY"] = "test-secret-key-for-playwright"
    env["GLYPH_DATABASE_URL"] = "sqlite+aiosqlite:///./test_playwright_auth.db"
    # Set generous rate limits for testing
    env["GLYPH_RATE_LIMIT_LOGIN_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_LOGIN_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_REGISTER_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_REGISTER_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW"] = "60"
    env["GLYPH_RATE_LIMIT_REFRESH_MAX"] = "100"
    env["GLYPH_RATE_LIMIT_REFRESH_WINDOW"] = "60"
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd="/workspaces/Glyph",
        env=env,
    )
    wait_for_server(BASE_URL)
    yield process
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    # Clean up test database
    db_path = "/workspaces/Glyph/test_playwright_auth.db"
    if os.path.exists(db_path):
        os.remove(db_path)


def test_login_page_loads(page: Any, server: Any) -> None:
    """Test that the login page loads successfully."""
    page.goto(f"{BASE_URL}/login")
    
    # Check the page loads with expected title
    expect(page).to_have_title("Glyph - Login")
    
    # Check the login form is present
    expect(page.locator("#loginForm")).to_be_visible()
    
    # Check the login title is present
    expect(page.locator("#login-title")).to_be_visible()
    expect(page.locator("#login-title")).to_have_text("LOGIN")
    
    # Check username input is present
    expect(page.locator("#username")).to_be_visible()
    
    # Check password input is present
    expect(page.locator("#password")).to_be_visible()
    
    # Check the login submit button is present
    expect(page.locator("#login-submit-btn")).to_be_visible()


def test_register_page_loads(page: Any, server: Any) -> None:
    """Test that the registration page loads successfully."""
    page.goto(f"{BASE_URL}/register")
    
    # Check the page loads with expected title
    expect(page).to_have_title("Glyph - Register")
    
    # Check the registration form is present
    expect(page.locator("#registerForm")).to_be_visible()
    
    # Check the register title is present
    expect(page.locator("#register-title")).to_be_visible()
    expect(page.locator("#register-title")).to_have_text("REGISTER")
    
    # Check username input is present
    expect(page.locator("#username")).to_be_visible()
    
    # Check email input is present
    expect(page.locator("#email")).to_be_visible()
    
    # Check full name input is present
    expect(page.locator("#full_name")).to_be_visible()
    
    # Check password input is present
    expect(page.locator("#password")).to_be_visible()
    
    # Check confirm password input is present
    expect(page.locator("#confirm_password")).to_be_visible()
    
    # Check the register submit button is present
    expect(page.locator("#register-submit-btn")).to_be_visible()
    
    # Check the link to login page is present (in the auth-links section)
    expect(page.locator('.auth-links a[href="/login"]')).to_be_visible()
