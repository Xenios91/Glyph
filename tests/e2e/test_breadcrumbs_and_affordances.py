# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""E2E tests for R7 (breadcrumbs on deep pages) and R22 (clickable row affordances).

R7: the five deep pages (binary detail, function, symbols, prediction,
prediction function details) must render an accessible breadcrumb
(``nav[aria-label="Breadcrumb"]``) whose parent crumbs are links and whose
current-page crumb is plain text marked with ``aria-current="page"``.

R22: clickable table rows (models, symbols, prediction list, prediction
details, binary functions) must carry the ``clickable-row`` affordance class
plus a pointer cursor, and the server-rendered tables must show a trailing
chevron cell.

Seeded rows are legacy (``user_id`` NULL) so they are visible to every
registered test user, or owned by the test user (binaries).
"""

import io
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login

# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed_model(data_dir: str, name: str) -> None:
    """Insert a legacy (unowned) model row visible to every user."""
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        conn.execute(
            "INSERT INTO models (model_name, model_data, label_encoder_data) "
            "VALUES (?, x'00', x'00')",
            (name,),
        )
        conn.commit()
    finally:
        conn.close()


def _delete_model(data_dir: str, name: str) -> None:
    """Remove a seeded model row so other tests see a clean database."""
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        conn.execute("DELETE FROM models WHERE model_name = ?", (name,))
        conn.commit()
    finally:
        conn.close()


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


def _seed_binary(data_dir: str, username: str, name: str) -> int:
    """Insert a binary owned by the test user plus one decompiled function."""
    auth = sqlite3.connect(Path(data_dir) / "auth.db")
    try:
        row = auth.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        auth.close()
    assert row is not None, f"Seeded user {username!r} not found in auth.db"
    user_id = row[0]

    conn = sqlite3.connect(Path(data_dir) / "binaries.db")
    try:
        cur = conn.execute(
            "INSERT INTO binaries (name, file_path, file_size, mime_type, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, "/tmp/seeded-binary.bin", 100, "application/octet-stream", user_id),
        )
        binary_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO binary_functions (binary_id, function_name, entrypoint, raw_code) "
            "VALUES (?, ?, ?, ?)",
            (binary_id, "main", "0x401000", "int main() { return 0; }"),
        )
        conn.commit()
    finally:
        conn.close()
    return binary_id


def _delete_binary(data_dir: str, binary_id: int) -> None:
    """Remove a seeded binary and its functions so other tests see a clean DB."""
    conn = sqlite3.connect(Path(data_dir) / "binaries.db")
    try:
        conn.execute("DELETE FROM binary_functions WHERE binary_id = ?", (binary_id,))
        conn.execute("DELETE FROM binaries WHERE id = ?", (binary_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def _assert_breadcrumb(page: Any, links: list[tuple[str, str]], current_text: str | None = None) -> None:
    """Assert the breadcrumb structure: parent crumbs are links, last is text.

    Args:
        page: Playwright page object.
        links: Expected (text, href) pairs for the parent crumbs, in order.
        current_text: Optional exact text of the current-page crumb.
    """
    nav = page.locator('nav[aria-label="Breadcrumb"]')
    expect(nav).to_have_count(1)

    items = nav.locator("ol.breadcrumb-list > li.breadcrumb-item")
    expect(items).to_have_count(len(links) + 1)

    for index, (text, href) in enumerate(links):
        link = items.nth(index).locator("a")
        expect(link).to_have_count(1)
        expect(link).to_have_text(text)
        expect(link).to_have_attribute("href", href)

    last = items.last
    expect(last).to_have_attribute("aria-current", "page")
    expect(last.locator("a")).to_have_count(0)
    span = last.locator("span")
    expect(span).to_have_count(1)
    if current_text is not None:
        expect(span).to_have_text(current_text)


def _assert_pointer_cursor(page: Any, selector: str) -> None:
    """Assert the first element matching *selector* computes to a pointer cursor."""
    cursor = page.evaluate(
        "(sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).cursor : null; }",
        selector,
    )
    assert cursor == "pointer", f"Expected pointer cursor on {selector!r}, got {cursor!r}"


def _assert_row_affordance(page: Any, row: Any) -> None:
    """Assert a row carries the clickable-row class, chevron cell, and pointer cursor."""
    classes = row.get_attribute("class") or ""
    assert "clickable-row" in classes, f"Row must carry the clickable-row class, got classes={classes!r}"
    expect(row.locator("td.chevron-cell .row-chevron")).to_have_count(1)
    cursor = row.evaluate("el => getComputedStyle(el).cursor")
    assert cursor == "pointer", f"Row must compute to a pointer cursor, got {cursor!r}"


# ---------------------------------------------------------------------------
# R7: Breadcrumbs on the five deep pages
# ---------------------------------------------------------------------------


class TestBreadcrumbs:
    """R7: each deep page renders an accessible breadcrumb trail."""

    def test_binary_detail_page_breadcrumb(self, page: Any, server: Any) -> None:
        """The binary detail page shows LIBRARY / <binary> with LIBRARY linked."""
        register_and_login(page)
        page.goto(f"{BASE_URL}/binary/1")
        page.wait_for_load_state("domcontentloaded")
        _assert_breadcrumb(page, [("LIBRARY", "/binary-library")])

    def test_symbols_page_breadcrumb(self, page: Any, server: Any) -> None:
        """The symbols page shows MODELS / <model> with MODELS linked."""
        register_and_login(page)
        model_name = f"bc-model-{uuid4().hex[:12]}"
        page.goto(f"{BASE_URL}/getSymbols?model_name={model_name}")
        page.wait_for_load_state("domcontentloaded")
        _assert_breadcrumb(page, [("MODELS", "/getModels")], current_text=model_name)

    def test_function_page_breadcrumb_model_branch(self, page: Any, server: Any, data_dir: str) -> None:
        """The function page (model source) shows SYMBOLS / <model> / <function>."""
        register_and_login(page)
        model_name = f"bc-model-{uuid4().hex[:12]}"
        function_name = f"bc_func_{uuid4().hex[:12]}"
        try:
            _seed_function(data_dir, model_name, function_name)
            page.goto(f"{BASE_URL}/getFunction?model_name={model_name}&function_name={function_name}")
            page.wait_for_load_state("domcontentloaded")
            _assert_breadcrumb(
                page,
                [
                    ("SYMBOLS", f"/getSymbols?model_name={model_name}"),
                    (model_name, "/getModels"),
                ],
                current_text=function_name,
            )
        finally:
            _delete_function(data_dir, model_name, function_name)

    def test_prediction_page_breadcrumb(self, page: Any, server: Any, data_dir: str) -> None:
        """The prediction page shows PREDICTIONS / <task> with PREDICTIONS linked."""
        register_and_login(page)
        task_name = f"bc-task-{uuid4().hex[:12]}"
        model_name = f"bc-model-{uuid4().hex[:12]}"
        function_name = f"bc_func_{uuid4().hex[:12]}"
        try:
            _seed_prediction(data_dir, task_name, model_name, function_name)
            page.goto(f"{BASE_URL}/getPrediction?task_name={task_name}&model_name={model_name}")
            page.wait_for_load_state("domcontentloaded")
            _assert_breadcrumb(page, [("PREDICTIONS", "/getPredictions")], current_text=task_name)
        finally:
            _delete_prediction(data_dir, task_name, model_name)

    def test_prediction_details_page_breadcrumb(self, page: Any, server: Any, data_dir: str) -> None:
        """The prediction details page shows PREDICTIONS / <task> / <function>."""
        register_and_login(page)
        task_name = f"bc-task-{uuid4().hex[:12]}"
        model_name = f"bc-model-{uuid4().hex[:12]}"
        function_name = f"bc_func_{uuid4().hex[:12]}"
        try:
            _seed_function(data_dir, model_name, function_name)
            _seed_prediction(data_dir, task_name, model_name, function_name)
            page.goto(
                f"{BASE_URL}/getPredictionDetails"
                f"?model_name={model_name}&function_name={function_name}&task_name={task_name}"
            )
            page.wait_for_load_state("domcontentloaded")
            _assert_breadcrumb(
                page,
                [
                    ("PREDICTIONS", "/getPredictions"),
                    (task_name, f"/getPrediction?task_name={task_name}&model_name={model_name}"),
                ],
                current_text=function_name,
            )
        finally:
            _delete_function(data_dir, model_name, function_name)
            _delete_prediction(data_dir, task_name, model_name)


# ---------------------------------------------------------------------------
# R22: Clickable row affordances
# ---------------------------------------------------------------------------


class TestClickableRowAffordances:
    """R22: clickable rows carry the affordance class, chevron, and pointer cursor."""

    def test_model_rows_have_clickable_affordance(self, page: Any, server: Any, data_dir: str) -> None:
        """Model table rows carry clickable-row, a chevron cell, and pointer cursor."""
        register_and_login(page)
        model_name = f"aff-model-{uuid4().hex[:12]}"
        try:
            _seed_model(data_dir, model_name)
            page.goto(f"{BASE_URL}/getModels")
            page.wait_for_load_state("domcontentloaded")
            row = page.locator(f"tr[data-model-name='{model_name}']")
            expect(row).to_have_count(1)
            _assert_row_affordance(page, row)
        finally:
            _delete_model(data_dir, model_name)

    def test_symbols_rows_have_clickable_affordance(self, page: Any, server: Any, data_dir: str) -> None:
        """Symbols table rows carry clickable-row, a chevron cell, and pointer cursor."""
        register_and_login(page)
        model_name = f"aff-model-{uuid4().hex[:12]}"
        function_name = f"aff_func_{uuid4().hex[:12]}"
        try:
            _seed_model(data_dir, model_name)
            _seed_function(data_dir, model_name, function_name)
            page.goto(f"{BASE_URL}/getSymbols?model_name={model_name}")
            page.wait_for_load_state("domcontentloaded")
            row = page.locator(f"tr[id='{function_name}-id']")
            expect(row).to_have_count(1)
            _assert_row_affordance(page, row)
        finally:
            _delete_function(data_dir, model_name, function_name)
            _delete_model(data_dir, model_name)

    def test_prediction_list_rows_have_clickable_affordance(self, page: Any, server: Any, data_dir: str) -> None:
        """Prediction list rows carry clickable-row, a chevron cell, and pointer cursor."""
        register_and_login(page)
        task_name = f"aff-task-{uuid4().hex[:12]}"
        model_name = f"aff-model-{uuid4().hex[:12]}"
        function_name = f"aff_func_{uuid4().hex[:12]}"
        try:
            _seed_prediction(data_dir, task_name, model_name, function_name)
            page.goto(f"{BASE_URL}/getPredictions")
            page.wait_for_load_state("domcontentloaded")
            row = page.locator(f"tr[data-task-name='{task_name}']")
            expect(row).to_have_count(1)
            _assert_row_affordance(page, row)
        finally:
            _delete_prediction(data_dir, task_name, model_name)

    def test_prediction_detail_rows_have_clickable_affordance(self, page: Any, server: Any, data_dir: str) -> None:
        """Prediction detail rows carry clickable-row, a chevron cell, and pointer cursor."""
        register_and_login(page)
        task_name = f"aff-task-{uuid4().hex[:12]}"
        model_name = f"aff-model-{uuid4().hex[:12]}"
        function_name = f"aff_func_{uuid4().hex[:12]}"
        try:
            _seed_prediction(data_dir, task_name, model_name, function_name)
            page.goto(f"{BASE_URL}/getPrediction?task_name={task_name}&model_name={model_name}")
            page.wait_for_load_state("domcontentloaded")
            row = page.locator(f"tr[data-function-name='{function_name}']")
            expect(row).to_have_count(1)
            _assert_row_affordance(page, row)
        finally:
            _delete_prediction(data_dir, task_name, model_name)

    def test_binary_function_rows_have_clickable_affordance(self, page: Any, server: Any, data_dir: str) -> None:
        """JS-rendered binary function rows carry the clickable-row class and pointer cursor."""
        username = register_and_login(page)
        binary_name = f"aff-bin-{uuid4().hex[:12]}"
        try:
            binary_id = _seed_binary(data_dir, username, binary_name)
            page.goto(f"{BASE_URL}/binary/{binary_id}")
            row = page.locator("#functions-tbody tr.clickable-row")
            expect(row).to_have_count(1, timeout=15000)
            _assert_pointer_cursor(page, "#functions-tbody tr")
            # The breadcrumb binary-name crumb is updated by the page JS.
            expect(page.locator("#breadcrumb-binary-name")).to_have_text(binary_name, timeout=15000)
        finally:
            _delete_binary(data_dir, binary_id)
