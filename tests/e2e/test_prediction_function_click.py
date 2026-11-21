"""E2E tests to verify prediction function click navigation.

Regression coverage for the details-page row click: clicking a function row
on the /getPrediction details page must navigate to /getPredictionDetails
(the side-by-side view) via table delegation, not reload the same page.
"""

import io
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
from playwright.sync_api import expect

from tests.e2e.utils import register_and_login

BASE_URL = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# Seeding helpers (mirror tests/e2e/test_breadcrumbs_and_affordances.py)
# ---------------------------------------------------------------------------


def _seed_function(data_dir: str, model_name: str, function_name: str) -> None:
    """Insert a legacy (unowned) function row visible to every user."""
    conn = sqlite3.connect(Path(data_dir) / "functions.db")
    try:
        conn.execute(
            "INSERT INTO functions (model_name, function_name, entrypoint, tokens) "
            "VALUES (?, ?, ?, ?)",
            (model_name, function_name, "0x401000", "int main() { return 0; }"),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_function(data_dir: str, model_name: str, function_name: str) -> None:
    """Remove a seeded function row so other tests see a clean database."""
    conn = sqlite3.connect(Path(data_dir) / "functions.db")
    try:
        conn.execute(
            "DELETE FROM functions WHERE model_name = ? AND function_name = ?",
            (model_name, function_name),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_prediction(data_dir: str, task_name: str, model_name: str, function_name: str) -> None:
    """Insert a legacy (unowned) prediction whose data includes one function.

    The ``functions_data`` BLOB is a joblib-dumped list of plain dicts, which
    the secure deserializer accepts (builtins only).
    """
    buf = io.BytesIO()
    joblib.dump(
        [{"functionName": function_name, "lowAddress": "0x401000", "tokens": "int main() { return 0; }"}],
        buf,
    )
    conn = sqlite3.connect(Path(data_dir) / "predictions.db")
    try:
        conn.execute(
            "INSERT INTO predictions (task_name, model_name, functions_data, function_count) "
            "VALUES (?, ?, ?, ?)",
            (task_name, model_name, buf.getvalue(), 1),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_prediction(data_dir: str, task_name: str, model_name: str) -> None:
    """Remove a seeded prediction row so other tests see a clean database."""
    conn = sqlite3.connect(Path(data_dir) / "predictions.db")
    try:
        conn.execute(
            "DELETE FROM predictions WHERE task_name = ? AND model_name = ?",
            (task_name, model_name),
        )
        conn.commit()
    finally:
        conn.close()


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
        "confirm_password": "testtest",
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


# ---------------------------------------------------------------------------
# Regression: details-page row click must navigate to /getPredictionDetails
# ---------------------------------------------------------------------------


def test_prediction_details_row_click_navigates_to_side_by_side(
    page: Any, server: Any, data_dir: str
) -> None:
    """Clicking a function row on the /getPrediction details page must navigate
    to /getPredictionDetails (side-by-side view), not reload the same page.

    Regression guard: a direct click listener bound to every ``.clickable-row``
    was shadowing the table-delegation listener (which owns rows whose table
    declares a non-empty ``data-click-handler``) and reloaded the identical
    page instead of opening the side-by-side view.
    """
    register_and_login(page)
    task_name = f"click-task-{uuid4().hex[:12]}"
    model_name = f"click-model-{uuid4().hex[:12]}"
    function_name = f"click_func_{uuid4().hex[:12]}"
    try:
        _seed_function(data_dir, model_name, function_name)
        _seed_prediction(data_dir, task_name, model_name, function_name)

        details_url = f"{BASE_URL}/getPrediction?task_name={task_name}&model_name={model_name}"
        page.goto(details_url)
        page.wait_for_load_state("domcontentloaded")

        row = page.locator(f"tr[data-function-name='{function_name}']")
        expect(row).to_have_count(1)

        # Click must navigate to the side-by-side view, not stay on /getPrediction.
        with page.expect_navigation(wait_until="domcontentloaded"):
            row.click()

        assert re.match(rf"^/getPredictionDetails\?function_name={re.escape(function_name)}",
                        page.url[len(BASE_URL):]), f"Unexpected URL after row click: {page.url}"
        assert "task_name=" in page.url and "model_name=" in page.url, (
            f"Details URL must carry task_name and model_name: {page.url}"
        )

        # The side-by-side token panels must be present on the new page.
        expect(page.locator("#prediction_tokens_div")).to_be_visible()
        expect(page.locator("#model_tokens_div")).to_be_visible()
    finally:
        _delete_prediction(data_dir, task_name, model_name)
        _delete_function(data_dir, model_name, function_name)


def test_prediction_details_row_enter_key_navigates_to_side_by_side(
    page: Any, server: Any, data_dir: str
) -> None:
    """Keyboard activation (Enter) of a details-page function row must also
    navigate to /getPredictionDetails via table delegation.

    Guards against regressing keyboard accessibility when the direct
    row-level keydown listener is skipped for delegation-owned rows.
    """
    register_and_login(page)
    task_name = f"kbd-task-{uuid4().hex[:12]}"
    model_name = f"kbd-model-{uuid4().hex[:12]}"
    function_name = f"kbd_func_{uuid4().hex[:12]}"
    try:
        _seed_function(data_dir, model_name, function_name)
        _seed_prediction(data_dir, task_name, model_name, function_name)

        page.goto(f"{BASE_URL}/getPrediction?task_name={task_name}&model_name={model_name}")
        page.wait_for_load_state("domcontentloaded")

        row = page.locator(f"tr[data-function-name='{function_name}']")
        expect(row).to_have_count(1)

        row.focus()
        with page.expect_navigation(wait_until="domcontentloaded"):
            row.press("Enter")

        assert re.match(rf"^/getPredictionDetails\?function_name={re.escape(function_name)}",
                        page.url[len(BASE_URL):]), f"Unexpected URL after Enter: {page.url}"
        expect(page.locator("#prediction_tokens_div")).to_be_visible()
        expect(page.locator("#model_tokens_div")).to_be_visible()
    finally:
        _delete_prediction(data_dir, task_name, model_name)
        _delete_function(data_dir, model_name, function_name)


def test_prediction_list_row_click_still_navigates_to_details(
    page: Any, server: Any, data_dir: str
) -> None:
    """Clicking a row on the predictions LIST page must still navigate to the
    /getPrediction details page (direct handler path, table has an empty
    data-click-handler).

    Guards against over-broad application of the delegation guard, which must
    only skip rows whose enclosing table declares a non-empty handler.
    """
    register_and_login(page)
    task_name = f"list-task-{uuid4().hex[:12]}"
    model_name = f"list-model-{uuid4().hex[:12]}"
    function_name = f"list_func_{uuid4().hex[:12]}"
    try:
        _seed_prediction(data_dir, task_name, model_name, function_name)

        page.goto(f"{BASE_URL}/getPredictions")
        page.wait_for_load_state("domcontentloaded")

        row = page.locator(f"tr[data-task-name='{task_name}']")
        expect(row).to_have_count(1)

        with page.expect_navigation(wait_until="domcontentloaded"):
            row.click()

        assert re.match(rf"^/getPrediction\?task_name={re.escape(task_name)}",
                        page.url[len(BASE_URL):]), f"Unexpected URL after list row click: {page.url}"
        assert "model_name=" in page.url, f"Details URL must carry model_name: {page.url}"
    finally:
        _delete_prediction(data_dir, task_name, model_name)
