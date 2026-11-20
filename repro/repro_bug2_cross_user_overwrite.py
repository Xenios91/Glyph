"""Repro for BUG-2: cross-user overwrite in scan-report / LLM-result repositories.

Root cause hypothesis
---------------------
``ScanReportRepository.save_report`` (and the behavioral + LLM equivalents)
select the existing row using ``target_name`` ONLY. The ``user_id`` argument is
ignored on the read path and is only written when a brand-new row is created.

Therefore, when two different users scan the SAME target (same ``model_name`` /
``task_name`` / binary), the second user's save finds the first user's row and
overwrites it in place. The result:

  * only ONE row exists for the target (not one per user);
  * the second user's save overwrites the first user's stored content in place;
  * the row keeps the FIRST user's ``user_id`` (``save_report`` sets ``user_id``
    only on insert, never on update), so:
      - the SECOND user can no longer retrieve their own report
        (``get_report`` for them returns ``None``), and
      - the FIRST user can now see the SECOND user's findings
        (a cross-user data-isolation violation).

This is a data-integrity / isolation bug: per-user stored reports collapse into
a single shared row keyed only on the target name.

This script drives the REAL repository code against a throwaway SQLite database
and prints the row counts + per-user reads to prove the behaviour.
"""

import asyncio
import os
import sys
import tempfile

# Keep the app's rate limiter quiet (mirrors tests/conftest.py).
for _k, _v in {
    "GLYPH_RATE_LIMIT_LOGIN_MAX": "1000",
    "GLYPH_RATE_LIMIT_LOGIN_WINDOW": "60",
    "GLYPH_RATE_LIMIT_REGISTER_MAX": "1000",
    "GLYPH_RATE_LIMIT_REGISTER_WINDOW": "60",
    "GLYPH_RATE_LIMIT_PASSWORD_CHANGE_MAX": "1000",
    "GLYPH_RATE_LIMIT_PASSWORD_CHANGE_WINDOW": "60",
    "GLYPH_RATE_LIMIT_REFRESH_MAX": "1000",
    "GLYPH_RATE_LIMIT_REFRESH_WINDOW": "60",
}.items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402

from app.database import session_handler  # noqa: E402
from app.database.models import (  # noqa: E402
    Base,
    BehavioralScanReport,
    LLMAnalysisResult,
    ScanReport,
)
from app.database.behavioral_scan_report_repository import (  # noqa: E402
    BehavioralScanReportRepository,
)
from app.database.llm_result_repository import LLMResultRepository  # noqa: E402
from app.database.scan_report_repository import ScanReportRepository  # noqa: E402

DB_NAMES = ("models", "predictions", "functions", "auth", "binaries", "intelligence")


def _report_dict(model_name: str, marker: str) -> dict:
    """Build a ScanReportResponse-shaped dict with a per-user marker."""
    return {
        "model_name": model_name,
        "total_functions_scanned": 10,
        "total_found": 1,
        "critical_count": 0,
        "high_count": 1,
        "medium_count": 0,
        "low_count": 0,
        "results": [{"function": marker, "severity": "high"}],
    }


async def count_rows(model) -> int:
    from app.database.session_handler import get_async_session, close_async_session

    session = await get_async_session("intelligence")
    try:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())
    finally:
        await close_async_session(session)


async def main() -> int:
    tmp = tempfile.mkdtemp(prefix="glyph_bug2_")
    session_handler.set_database_urls(
        {name: f"sqlite+aiosqlite:///{tmp}/{name}.db" for name in DB_NAMES}
    )
    await session_handler.init_async_databases()

    target = "shared_target"
    user_a, user_b = 11, 22

    print("=" * 72)
    print("BUG-2  Cross-user overwrite in stored scan reports / LLM results")
    print("=" * 72)

    # --- Scenario 1: two users scan the same target -------------------------
    print("\n[1] ScanReport: user A saves, then user B saves the SAME target")
    await ScanReportRepository.save_report(_report_dict(target, "USER_A_FINDING"), user_id=user_a)
    n_after_a = await count_rows(ScanReport)
    print(f"    rows after user A ({user_a}) saves : {n_after_a}")

    await ScanReportRepository.save_report(_report_dict(target, "USER_B_FINDING"), user_id=user_b)
    n_after_b = await count_rows(ScanReport)
    print(f"    rows after user B ({user_b}) saves : {n_after_b}")

    row_a = await ScanReportRepository.get_report(target, user_id=user_a)
    row_b = await ScanReportRepository.get_report(target, user_id=user_b)
    print(f"    get_report(user A) -> {None if row_a is None else row_a.results_json!r}")
    print(f"    get_report(user B) -> {None if row_b is None else row_b.results_json!r}")

    # Confirmed behaviour: one shared row; it keeps user A's user_id, so user A
    # sees user B's content and user B sees nothing.
    bug2_scan = (
        n_after_b == 1
        and row_b is None
        and row_a is not None
        and "USER_B_FINDING" in (row_a.results_json or "")
    )
    print(f"    => single shared row; user B's scan overwrote user A's row: {bug2_scan}")

    # --- Scenario 2: behavioral scan reports (same pattern) -----------------
    print("\n[2] BehavioralScanReport: same pattern")
    bdict = _report_dict(target, "BEHAV_A")
    await BehavioralScanReportRepository.save_report(bdict, user_id=user_a)
    await BehavioralScanReportRepository.save_report(_report_dict(target, "BEHAV_B"), user_id=user_b)
    n_behav = await count_rows(BehavioralScanReport)
    behav_a = await BehavioralScanReportRepository.get_report(target, user_id=user_a)
    behav_b = await BehavioralScanReportRepository.get_report(target, user_id=user_b)
    print(f"    rows after both users save : {n_behav}")
    print(f"    get_report(user A) -> {None if behav_a is None else behav_a.results_json!r}")
    print(f"    get_report(user B) -> {None if behav_b is None else behav_b.results_json!r}")
    bug2_behav = (
        n_behav == 1
        and behav_b is None
        and behav_a is not None
        and "BEHAV_B" in (behav_a.results_json or "")
    )

    # --- Scenario 3: LLM analysis results (same pattern) --------------------
    print("\n[3] LLMAnalysisResult: user A analyzes, user B re-analyzes same finding")
    finding = dict(
        function_name="strcpy",
        containing_function="main",
        entrypoint="0x401000",
    )
    res_a = LLMAnalysisResult(
        target_name=target,
        function_name=finding["function_name"],
        containing_function=finding["containing_function"],
        entrypoint=finding["entrypoint"],
        status="success",
        analysis="USER_A_ANALYSIS",
        error="",
        model_name="model-x",
        elapsed_ms=10,
        confidence="high",
        verdict="VULNERABLE",
    )
    res_b = LLMAnalysisResult(
        target_name=target,
        function_name=finding["function_name"],
        containing_function=finding["containing_function"],
        entrypoint=finding["entrypoint"],
        status="success",
        analysis="USER_B_ANALYSIS",
        error="",
        model_name="model-x",
        elapsed_ms=12,
        confidence="high",
        verdict="VULNERABLE",
    )
    await LLMResultRepository.upsert_one(target, res_a, user_id=user_a)
    n_llm_a = await count_rows(LLMAnalysisResult)
    await LLMResultRepository.upsert_one(target, res_b, user_id=user_b)
    n_llm_b = await count_rows(LLMAnalysisResult)
    llm_a = await LLMResultRepository.get_for_target(target, user_id=user_a)
    llm_b = await LLMResultRepository.get_for_target(target, user_id=user_b)
    print(f"    rows after user A upsert : {n_llm_a}")
    print(f"    rows after user B upsert : {n_llm_b}")
    print(f"    get_for_target(user A) -> {len(llm_a)} row(s), analysis={llm_a[0].analysis if llm_a else None!r}")
    print(f"    get_for_target(user B) -> {len(llm_b)} row(s)")
    bug2_llm = (
        n_llm_b == 1
        and len(llm_b) == 0
        and len(llm_a) == 1
        and llm_a[0].analysis == "USER_B_ANALYSIS"
    )

    print("\n" + "=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"  BUG-2 (scan report cross-user overwrite)   : {'CONFIRMED' if bug2_scan else 'NOT reproduced'}")
    print(f"  BUG-2b (behavioral scan cross-user ovrw)   : {'CONFIRMED' if bug2_behav else 'NOT reproduced'}")
    print(f"  BUG-2c (LLM result cross-user overwrite)   : {'CONFIRMED' if bug2_llm else 'NOT reproduced'}")

    await session_handler.dispose_async_engines()
    return 0 if (bug2_scan and bug2_behav and bug2_llm) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
