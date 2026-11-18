# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""P0 e2e: real, un-mocked long-running task lifecycle.

This test drives a REAL end-to-end task with NO mocking of the task API
(no ``page.route`` interception of ``/api/v1/tasks/execute``, status, or
results). It exercises the full production path:

    register/login -> upload a real ELF -> seed the extracted-function
    table -> execute a ``dangerous_functions`` task -> let the real
    background runner + real browser polling run to completion -> verify
    the results page renders -> verify the task auto-removes from the
    status bar.

Why the function table is seeded by hand
-----------------------------------------
The upload pipeline's ``DecompileStep`` requires Ghidra/JDK, which is not
available in this environment, so the background decompile task fails before
``SaveRawFunctionsStep`` ever runs. The binary *row* is, however, persisted
synchronously before the decompile task is queued (see
``post_upload_binary``), so we can seed a ``binary_functions`` row directly
in the ``binaries.db`` SQLite database. That row is what the real
``run_dangerous_functions_task`` runner loads, tokenizes, filters, and scans.

The seeded function body contains a ``strcpy(...)`` call, which the real
scanner (``_scan_function_bodies``) matches against the dangerous-function
catalog (``strcpy`` -> Buffer Overflow, High severity). The test therefore
asserts exactly one detected finding.
"""

import os
import re
import sqlite3
import time
from typing import Any

from playwright.sync_api import expect

from tests.e2e.utils import BASE_URL, generate_unique_username, register_and_login

# A minimal, valid-enough ELF header so the upload service's MIME sniffing
# accepts the file. The decompile step will (and should) fail on this stub;
# only the binary row + our seeded function matter for the task under test.
_SAMPLE_ELF = b"\x7fELF" + b"\x00" * 64

# Raw decompiled C code for the seeded function. ``raw_code.split()`` becomes
# the function's ``tokenList``; the scanner joins tokens and matches
# ``\bstrcpy\s*\(`` against the result, so this body yields exactly one
# detected dangerous function (strcpy).
_SEEDED_RAW_CODE = "int main() { char buf[16]; strcpy(buf, input); return 0; }"


def _seed_binary_functions(data_dir: str, binary_name: str) -> int:
    """Insert a ``binary_functions`` row for an uploaded binary.

    Returns the binary id. Retries briefly because the binary row is written
    by the server process; by the time the upload toast is visible the row is
    present, but a short poll makes the seed robust against any scheduling
    jitter.
    """
    db_path = os.path.join(data_dir, "binaries.db")
    deadline = time.time() + 15
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        binary_id: int | None = None
        while time.time() < deadline:
            cur.execute("SELECT id FROM binaries WHERE name = ?", (binary_name,))
            row = cur.fetchone()
            if row is not None:
                binary_id = int(row[0])
                break
            time.sleep(0.25)
        assert binary_id is not None, f"binary {binary_name!r} not found in {db_path}"

        cur.execute(
            "INSERT INTO binary_functions (binary_id, function_name, entrypoint, raw_code) "
            "VALUES (?, ?, ?, ?)",
            (binary_id, "main", "0x401000", _SEEDED_RAW_CODE),
        )
        conn.commit()
        return binary_id
    finally:
        conn.close()


def _task_uuid_from_url(url: str) -> str:
    match = re.search(r"task_uuid=([^&]+)", url)
    assert match is not None, f"no task_uuid in URL: {url}"
    return match.group(1)


def test_execute_real_task_completes_and_auto_removes(page: Any, server: Any, data_dir: Any) -> None:
    """Full real lifecycle: upload -> execute -> poll -> results -> auto-remove."""
    # Arrange: fresh authenticated user.
    register_and_login(page)
    page.goto(f"{BASE_URL}/binary-library")
    page.wait_for_load_state("networkidle")

    binary_name = generate_unique_username()
    page.locator("#binary-name").fill(binary_name)

    # Act: upload a real ELF (triggers the upload via the change event).
    page.locator("#upload-binary").set_input_files(
        {"name": "sample.bin", "mimeType": "application/octet-stream", "buffer": _SAMPLE_ELF}
    )

    # Assert: upload completes (progress -> "Upload complete!" -> toast -> row).
    expect(page.locator("#upload-progress")).to_be_visible(timeout=5000)
    expect(page.locator("#progress-text")).to_contain_text("Upload complete!", timeout=30000)
    toast = page.locator(".toast-success")
    expect(toast).to_be_visible(timeout=10000)
    expect(toast).to_contain_text(f"Binary \"{binary_name}\" uploaded successfully")
    row = page.locator("#binaries-tbody .binary-name").filter(has_text=binary_name)
    expect(row).to_be_visible(timeout=10000)

    # Seed the extracted-function table (decompile failed; row is present).
    binary_id = _seed_binary_functions(data_dir, binary_name)

    # Act: open the run-task page and execute a real dangerous-functions scan.
    page.goto(f"{BASE_URL}/run-task?binary_id={binary_id}&binary_name={binary_name}")
    page.wait_for_load_state("networkidle")
    page.select_option("#task-type", "dangerous_functions")
    page.click("#execute-btn")

    # Assert: the global status bar tracks the task as soon as /execute returns
    # a uuid. The entry lives inside the collapsed status-bar panel, so it is
    # attached to the DOM but not "visible" while the panel is closed — wait for
    # attachment (which happens the moment registerTask runs, well before the
    # page redirects to the results view).
    page.wait_for_selector(".status-entry", state="attached", timeout=10000)

    # Assert: real polling completes and the page redirects to the results view.
    page.wait_for_url(re.compile(r"/task-results\?task_uuid="), timeout=60000)
    task_uuid = _task_uuid_from_url(page.url)

    # Assert: the real scan results render (no mocking).
    expect(page.locator("#results-loading")).to_be_hidden(timeout=30000)
    expect(page.locator("#results-summary")).to_be_visible(timeout=30000)
    expect(page.locator("#summary-grid .summary-card")).to_have_count(6, timeout=30000)
    expect(page.locator("#comparisons-container")).to_be_visible(timeout=30000)
    expect(page.locator("#comparisons-list .comparison-block")).to_have_count(1, timeout=30000)

    # Assert: the completed task auto-removes from the status bar.
    expect(page.locator(f"#entry-{task_uuid}")).to_have_count(0, timeout=30000)
