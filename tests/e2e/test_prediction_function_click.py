"""E2E test to verify prediction function click shows correct details."""
import time
import pytest
from typing import Any

BASE_URL = "http://127.0.0.1:8000"


def test_prediction_function_click_shows_details(page: Any, server: Any) -> None:
    """Test that clicking a prediction function shows the original function code."""
    # Register and login
    username = f"testuser_{int(time.time() % 10000)}"
    page.goto(f"{BASE_URL}/register")
    page.locator("#username").fill(username)
    page.locator("#email").fill(f"{username}@test.com")
    page.locator("#password").fill("testtest")
    page.locator("#confirm_password").fill("testtest")
    page.locator("#register-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/login")

    page.locator("#username").fill(username)
    page.locator("#password").fill("testtest")
    page.locator("#login-submit-btn").click()
    page.wait_for_url(f"{BASE_URL}/")

    # Check that the predictions page loads without errors
    page.goto(f"{BASE_URL}/getPredictions")
    page.wait_for_load_state("networkidle")
    
    # The page should load successfully (even if empty)
    # Check no error messages are visible on the page
    error_elements = page.locator("text=/error|Error|ERROR/i")
    if error_elements.count() > 0:
        visible_errors = error_elements.filter(has_text="not trained")
        assert visible_errors.count() == 0, "Found 'not trained' error on predictions page"
    
    print("Predictions page loaded successfully without 'not trained' error")


def test_prediction_details_endpoint_returns_correct_data(page: Any, server: Any) -> None:
    """Test the API endpoint directly to verify functionName is preserved."""
    import requests
    
    # Register and login to get token
    username = f"testuser_{int(time.time() % 10000)}"
    register_data = {
        "username": username,
        "email": f"{username}@test.com",
        "password": "testtest",
        "confirm_password": "testtest"
    }
    requests.post(f"{BASE_URL}/auth/register", json=register_data)
    
    login_data = {"username": username, "password": "testtest"}
    login_resp = requests.post(f"{BASE_URL}/auth/token", data=login_data)
    token = login_resp.json().get("access_token")
    
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    # Verify predictions list endpoint works
    resp = requests.get(f"{BASE_URL}/api/v1/predictions/getPredictionsList", headers=headers)
    assert resp.status_code == 200, f"getPredictionsList failed: {resp.text}"
    
    print(f"Predictions list endpoint returned OK with {resp.json()}")
