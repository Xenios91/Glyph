# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""E2E tests for the behavioral-scan page (gap S1-S5).

Exercises the full behavioral-scan flow end-to-end against a live app:
scan a model, scan a prediction task, scan a binary, inspect a finding
detail modal, and paginate a large result set.

Findings are produced by seeding functions whose decompiled token bodies
contain the malicious patterns the behavioral signature catalog detects
(system / execve calls, /etc/passwd and VirtualAlloc string literals, an
in-place XOR decode heuristic, a CreateThread function-pointer reference,
and a hex-escape obfuscated string).

Seeded model / prediction rows are legacy (``user_id`` NULL) so they are
visible to every registered test user; the binary is owned by the test user.
"""

import io
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
import pytest
from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, register_and_login

# ---------------------------------------------------------------------------
# Malicious / benign function bodies (decompiled token text)
# ---------------------------------------------------------------------------

# A benign function that matches no behavioral signature.
BENIGN_BODY = "int main() { return 0; }"

# Functions whose bodies trigger specific behavioral signatures.
SYSTEM_BODY = "int run_cmd() { system(\"cmd\"); return 0; }"
EXECVE_BODY = "int spawn() { char *args[] = {\"sh\", 0}; execve(\"/bin/sh\", args, 0); return 0; }"
PASSWD_BODY = "char *read_pass() { return \"/etc/passwd\"; }"
VIRTALLOC_BODY = "void *alloc_mem() { return VirtualAlloc(0, 0x1000, 4, 4); }"
XOR_BODY = "int decode(unsigned char *buf, int n) { for (int i = 0; i < n; i++) { buf[i] ^= 0x5A; } return n; }"
THREAD_PTR_BODY = "void start_thread(void) { CreateThread_t fp = CreateThread; fp(0, 0, 0, 0); }"
HEXSTR_BODY = "char *obf() { return \"\\x41\\x42\\x43\\x44\\x45\"; }"

# Binary: one function per signature (8 distinct findings).
BINARY_FUNCTIONS: dict[str, str] = {
    "fn_system": SYSTEM_BODY,
    "fn_execve": EXECVE_BODY,
    "fn_passwd": PASSWD_BODY,
    "fn_virtalloc": VIRTALLOC_BODY,
    "fn_xor": XOR_BODY,
    "fn_thread": THREAD_PTR_BODY,
    "fn_hexstr": HEXSTR_BODY,
    "fn_benign": BENIGN_BODY,
}

# Expected behavior names detected for the binary scan.
EXPECTED_BINARY_FINDINGS = {
    "system",
    "execve",
    "password_file_access",
    "windows_memory_allocation",
    "in_place_decode",
    "thread_creation",
    "obfuscated_string",
}

# Prediction: four functions (system, execve, /etc/passwd, VirtualAlloc).
PREDICTION_FUNCTIONS: dict[str, str] = {
    "pred_system": SYSTEM_BODY,
    "pred_execve": EXECVE_BODY,
    "pred_passwd": PASSWD_BODY,
    "pred_virtalloc": VIRTALLOC_BODY,
}

# Expected behavior names detected for the prediction scan.
EXPECTED_PREDICTION_FINDINGS = {
    "system",
    "execve",
    "password_file_access",
    "windows_memory_allocation",
}

# Model for pagination: 25 functions that each trigger the "system" signature.
PAGINATION_COUNT = 25


def _model_name() -> str:
    return f"bscan_clean_{uuid4().hex[:8]}"


def _pagination_model_name() -> str:
    return f"bscan_paged_{uuid4().hex[:8]}"


def _prediction_name() -> str:
    return f"bscan_pred_{uuid4().hex[:8]}"


def _binary_name() -> str:
    return f"bscan_bin_{uuid4().hex[:8]}.bin"


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


def _seed_function(data_dir: str, model_name: str, function_name: str, body: str) -> None:
    """Insert a legacy (unowned) function row with the given token body."""
    conn = sqlite3.connect(Path(data_dir) / "functions.db")
    try:
        conn.execute(
            "INSERT INTO functions (model_name, function_name, entrypoint, tokens) "
            "VALUES (?, ?, ?, ?)",
            (model_name, function_name, "0x401000", body),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_prediction(data_dir: str, task_name: str, model_name: str, functions: dict[str, str]) -> None:
    """Insert a legacy (unowned) prediction whose data holds the given functions.

    ``functions_data`` is a joblib-dumped list of plain dicts (builtins only),
    which the secure deserializer accepts.
    """
    payload = [
        {"functionName": fn, "lowAddress": "0x401000", "tokens": body}
        for fn, body in functions.items()
    ]
    buf = io.BytesIO()
    joblib.dump(payload, buf)
    conn = sqlite3.connect(Path(data_dir) / "predictions.db")
    try:
        conn.execute(
            "INSERT INTO predictions (task_name, model_name, functions_data, function_count) "
            "VALUES (?, ?, ?, ?)",
            (task_name, model_name, buf.getvalue(), len(payload)),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_binary(data_dir: str, username: str, name: str, functions: dict[str, str]) -> int:
    """Insert a binary owned by the test user plus its decompiled functions."""
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
            (name, "/tmp/bscan-seeded.bin", 100, "application/octet-stream", user_id),
        )
        binary_id = int(cur.lastrowid)
        for fn, body in functions.items():
            conn.execute(
                "INSERT INTO binary_functions (binary_id, function_name, entrypoint, raw_code) "
                "VALUES (?, ?, ?, ?)",
                (binary_id, fn, "0x401000", body),
            )
        conn.commit()
    finally:
        conn.close()
    return binary_id


def _delete_model(data_dir: str, name: str) -> None:
    conn = sqlite3.connect(Path(data_dir) / "models.db")
    try:
        conn.execute("DELETE FROM models WHERE model_name = ?", (name,))
        conn.commit()
    finally:
        conn.close()


def _delete_functions(data_dir: str, model_name: str) -> None:
    conn = sqlite3.connect(Path(data_dir) / "functions.db")
    try:
        conn.execute("DELETE FROM functions WHERE model_name = ?", (model_name,))
        conn.commit()
    finally:
        conn.close()


def _delete_prediction(data_dir: str, task_name: str) -> None:
    conn = sqlite3.connect(Path(data_dir) / "predictions.db")
    try:
        conn.execute("DELETE FROM predictions WHERE task_name = ?", (task_name,))
        conn.commit()
    finally:
        conn.close()


def _delete_binary(data_dir: str, binary_id: int) -> None:
    conn = sqlite3.connect(Path(data_dir) / "binaries.db")
    try:
        conn.execute("DELETE FROM binary_functions WHERE binary_id = ?", (binary_id,))
        conn.execute("DELETE FROM binaries WHERE id = ?", (binary_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A per-module data directory holding the app's SQLite databases."""
    return str(tmp_path_factory.mktemp("bscan_data"))


@pytest.fixture(scope="module")
def seeded(data_dir: str, page: Any) -> dict[str, Any]:
    """Register/login once and seed all behavioral-scan fixtures."""
    username = register_and_login(page)
    clean_model = _model_name()
    paged_model = _pagination_model_name()
    prediction = _prediction_name()
    binary_name = _binary_name()

    _seed_model(data_dir, clean_model)
    _seed_function(data_dir, clean_model, "benign_fn", BENIGN_BODY)

    _seed_model(data_dir, paged_model)
    for i in range(PAGINATION_COUNT):
        _seed_function(data_dir, paged_model, f"paged_fn_{i:02d}", SYSTEM_BODY)

    _seed_prediction(data_dir, prediction, clean_model, PREDICTION_FUNCTIONS)

    binary_id = _seed_binary(data_dir, username, binary_name, BINARY_FUNCTIONS)

    yield {
        "username": username,
        "clean_model": clean_model,
        "paged_model": paged_model,
        "prediction": prediction,
        "binary_name": binary_name,
        "binary_id": binary_id,
    }

    # Cleanup so other tests see a clean database.
    _delete_model(data_dir, clean_model)
    _delete_functions(data_dir, clean_model)
    _delete_model(data_dir, paged_model)
    _delete_functions(data_dir, paged_model)
    _delete_prediction(data_dir, prediction)
    _delete_binary(data_dir, binary_id)


@pytest.fixture()
def scan_page(page: Any) -> Any:
    """Navigate to the behavioral scan page in a clean state."""
    page.goto(f"{BASE_URL}/behavioral-scan", wait_until="networkidle")
    expect(page.locator("#scan-btn")).to_be_visible()
    return page


# ---------------------------------------------------------------------------
# Page interaction helpers
# ---------------------------------------------------------------------------


def _select_target(page: Any, target_type: str, target_value: str) -> None:
    """Set the target type + target and wait for the scan button to be enabled."""
    page.locator("#scan-target-type").select_option(target_type)
    # Wait for the target dropdown to be populated (not the loading placeholder).
    expect(page.locator("#scan-target-select option")).not_to_have_count(0)
    page.locator("#scan-target-select").select_option(value=target_value)
    expect(page.locator("#scan-btn")).to_be_enabled(timeout=10_000)


def _run_scan(page: Any, expected_total: int) -> None:
    """Click scan and wait until the report with ``expected_total`` findings renders."""
    page.locator("#scan-btn").click()
    expect(page.locator("#scan-summary")).to_be_visible(timeout=30_000)
    expect(
        page.locator("#total-count"),
        timeout=30_000,
    ).to_have_text(str(expected_total))


def _severity_counts(page: Any) -> dict[str, int]:
    return {
        "critical": int(page.locator("#critical-count").inner_text()),
        "high": int(page.locator("#high-count").inner_text()),
        "medium": int(page.locator("#medium-count").inner_text()),
        "low": int(page.locator("#low-count").inner_text()),
        "total": int(page.locator("#total-count").inner_text()),
    }


def _finding_rows(page: Any) -> list[str]:
    """Return the behavior names of the findings currently shown in the table."""
    rows = page.locator("#scan-results-body tr")
    count = rows.count()
    names: list[str] = []
    for i in range(count):
        names.append(rows.nth(i).locator("td").first.inner_text().strip())
    return names


# ---------------------------------------------------------------------------
# S1: scan a model
# ---------------------------------------------------------------------------


def test_s1_scan_model_clean_no_findings(scan_page: Any, seeded: dict[str, Any]) -> None:
    """Scanning a model with only a benign function reports zero findings."""
    page = scan_page
    model = seeded["clean_model"]
    _select_target(page, "model", model)
    _run_scan(page, expected_total=0)

    # The "no findings" empty state is shown and the results table is hidden.
    expect(page.locator("#no-results-message")).to_be_visible()
    expect(page.locator("#scan-results-container")).to_be_hidden()

    counts = _severity_counts(page)
    assert counts == {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}, counts
    # The summary shows how many functions were scanned (1 benign function).
    assert int(page.locator("#total-scanned").inner_text()) == 1
    # The scanned target name is displayed.
    expect(page.locator("#scan-target-name")).to_have_text(model)


# ---------------------------------------------------------------------------
# S2: scan a binary
# ---------------------------------------------------------------------------


def test_s2_scan_binary_detects_findings(scan_page: Any, seeded: dict[str, Any]) -> None:
    """Scanning the seeded binary detects all 7 expected behaviors."""
    page = scan_page
    binary = seeded["binary_name"]
    _select_target(page, "binary", binary)
    _run_scan(page, expected_total=len(EXPECTED_BINARY_FINDINGS))

    expect(page.locator("#no-results-message")).to_be_hidden()
    expect(page.locator("#scan-results-container")).to_be_visible()

    counts = _severity_counts(page)
    assert counts["total"] == 7, counts
    # system / execve / password_file_access / windows_memory_allocation are High.
    assert counts["high"] == 4, counts
    # in_place_decode / thread_creation / obfuscated_string are Medium.
    assert counts["medium"] == 3, counts
    assert counts["critical"] == 0 and counts["low"] == 0, counts

    # All 7 expected behaviors are present in the result rows.
    rows = _finding_rows(page)
    assert set(rows) == EXPECTED_BINARY_FINDINGS, rows
    # 8 functions were scanned (7 malicious + 1 benign).
    assert int(page.locator("#total-scanned").inner_text()) == 8
    expect(page.locator("#scan-target-name")).to_have_text(binary)


# ---------------------------------------------------------------------------
# S3: scan a prediction task
# ---------------------------------------------------------------------------


def test_s3_scan_prediction_detects_findings(scan_page: Any, seeded: dict[str, Any]) -> None:
    """Scanning the seeded prediction task detects its 4 behaviors."""
    page = scan_page
    prediction = seeded["prediction"]
    _select_target(page, "prediction", prediction)
    _run_scan(page, expected_total=len(EXPECTED_PREDICTION_FINDINGS))

    expect(page.locator("#scan-results-container")).to_be_visible()

    counts = _severity_counts(page)
    assert counts["total"] == 4, counts
    assert counts["high"] == 4, counts  # all four are High severity
    assert counts["critical"] == 0 and counts["medium"] == 0 and counts["low"] == 0, counts

    rows = _finding_rows(page)
    assert set(rows) == EXPECTED_PREDICTION_FINDINGS, rows
    # 4 functions were scanned.
    assert int(page.locator("#total-scanned").inner_text()) == 4
    expect(page.locator("#scan-target-name")).to_have_text(prediction)


# ---------------------------------------------------------------------------
# S4: finding detail modal
# ---------------------------------------------------------------------------


def test_s4_finding_detail_modal(scan_page: Any, seeded: dict[str, Any]) -> None:
    """Clicking a finding row opens a detail modal with metadata, evidence, and code."""
    page = scan_page
    binary = seeded["binary_name"]
    _select_target(page, "binary", binary)
    _run_scan(page, expected_total=len(EXPECTED_BINARY_FINDINGS))

    # Click the first finding row to open the detail modal.
    page.locator("#scan-results-body tr").first.click()
    expect(page.locator("#context-modal")).to_be_visible()

    # The modal is populated with the finding's metadata.
    behavior = page.locator("#modal-behavior-name").inner_text().strip()
    assert behavior in EXPECTED_BINARY_FINDINGS, behavior
    assert page.locator("#modal-behavior-category").inner_text().strip() != ""
    assert page.locator("#modal-containing-function").inner_text().strip() != ""
    # A severity badge is rendered in the modal.
    expect(page.locator("#modal-severity .severity-badge")).to_have_count(1)
    assert page.locator("#modal-description").inner_text().strip() != ""

    # Matched evidence is populated (not the "no evidence" placeholder).
    evidence = page.locator("#modal-matched-evidence").inner_text()
    assert evidence.strip() != ""
    assert "No matched evidence" not in evidence

    # The containing function code section is visible and non-empty.
    expect(page.locator("#containing-code-section")).to_be_visible()
    assert page.locator("#modal-containing-code").inner_text().strip() != ""

    # Closing the modal hides it again.
    page.locator("#modal-close-btn").click()
    expect(page.locator("#context-modal")).to_be_hidden()


# ---------------------------------------------------------------------------
# S5: pagination with many results
# ---------------------------------------------------------------------------


def test_s5_pagination_many_results(scan_page: Any, seeded: dict[str, Any]) -> None:
    """A 25-finding report paginates correctly (10 per page across 3 pages)."""
    page = scan_page
    model = seeded["paged_model"]
    _select_target(page, "model", model)
    _run_scan(page, expected_total=PAGINATION_COUNT)

    expect(page.locator("#scan-results-container")).to_be_visible()
    counts = _severity_counts(page)
    assert counts["total"] == PAGINATION_COUNT, counts
    # All 25 findings are High (system).
    assert counts["high"] == PAGINATION_COUNT, counts

    # Wait for the pagination controls to appear.
    pagination = page.locator("#scan-results-pagination")
    expect(pagination).to_be_visible(timeout=10_000)

    # Set the page size to 10 rows.
    pagination.locator("select").select_option("10")

    # Page 1 shows 10 rows.
    expect(page.locator("#scan-results-body tr")).to_have_count(10)
    expect(pagination).to_contain_text("Page 1 of 3")

    # Navigate to page 2.
    pagination.locator('button[aria-label*="page 2"]').click()
    expect(pagination).to_contain_text("Page 2 of 3")
    expect(page.locator("#scan-results-body tr")).to_have_count(10)

    # Navigate to the last page (3), which shows the remaining 5 rows.
    pagination.locator('button[aria-label*="page 3"]').click()
    expect(pagination).to_contain_text("Page 3 of 3")
    expect(page.locator("#scan-results-body tr")).to_have_count(5)

    # Every row on the last page is a "system" finding.
    rows = _finding_rows(page)
    assert rows == ["system"] * 5, rows
