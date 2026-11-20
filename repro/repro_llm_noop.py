"""Repro/verification: "Check with LLM" on the dangerous-functions page.

ORIGINAL BUG (root cause)
-------------------------
The endpoint's fail-fast check called only ``build_endpoint_url(llm)``
(app/api/v1/endpoints/dangerous_functions.py). That builds the URL but does NOT
run the SSRF guard. The guard ran inside ``stream_findings``
(app/services/llm_analysis_service.py), an *async generator* that only executes
on first iteration -- i.e. AFTER the 200 status and the ``text/event-stream``
headers were already sent. For a blocked LLM endpoint the guard
(app/utils/ssrf_guard.py) raised ``ValueError("host resolves to a non-public
address")`` mid-stream. The endpoint's ``event_stream`` only caught
``asyncio.CancelledError``, so the ``ValueError`` propagated out of the
StreamingResponse body iterator *after* the 200 was on the wire, with ZERO SSE
events. The frontend saw a 200 + empty stream, exited its reader loop without
calling onResult/onDone and without throwing, so no error banner appeared and
every badge silently reverted to "-". That was the reported "does nothing".

THE FIX (what this script now verifies)
---------------------------------------
The endpoint now calls ``await validate_llm_endpoint(llm)`` in its fail-fast
block, which runs the SSRF guard *before* the response is created. A blocked
endpoint therefore returns a proper ``503`` with error code
``LLM_ENDPOINT_BLOCKED`` and a human-readable message -- before any 200/SSE is
sent. The frontend's ``streamLlmAnalysis`` now surfaces that code + message
(non-2xx path) and, as defense in depth, throws if a stream ever ends without a
``done`` event.

LOCAL-LLM POLICY (what this script now verifies)
------------------------------------------------
The guard is opt-in strict: the LLM path passes ``allow_local=True`` so a
*local* LLM (loopback, ``localhost``, RFC1918 private LAN) is permitted -- the
DEFAULT ``base_url`` is ``http://localhost:11434`` (Ollama), which must work.
Link-local (incl. the cloud metadata endpoint ``169.254.169.254``), unspecified
(``0.0.0.0``/``::``), CGNAT, and every other non-public address remain blocked.

This script drives the REAL ASGI app with the REAL ``validate_llm_endpoint`` +
REAL ``ssrf_guard`` (only the DB boundary and per-user LLM config are stubbed)
and asserts the FIXED wire behavior. It is deterministic: it never makes a live
LLM call. Part 1 checks the guard/validation outcome for a local endpoint
directly; Part 2 checks the endpoint's fail-fast 503 for a still-blocked
non-local (link-local) endpoint.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from unittest import mock

# ---------------------------------------------------------------------------
# 1. Replicate tests/conftest.py environment setup so the app can be imported
#    and run outside of pytest.
# ---------------------------------------------------------------------------
for _mod in (
    "ghidra",
    "ghidra.app.decompiler",
    "ghidra.framework.options",
    "ghidra.util.task",
    "ghidra.program.model.listing",
    "ghidra.app.script",
    "java",
    "java.lang",
    "pyghidra",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

_db_dir = tempfile.mkdtemp(prefix="glyph_repro_llm_")
from app.database.session_handler import set_database_urls  # noqa: E402

set_database_urls({name: f"sqlite+aiosqlite:///{_db_dir}/{name}.db"
                   for name in ("models", "predictions", "functions", "auth", "binaries", "intelligence")})

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from app.auth.dependencies import get_current_active_user  # noqa: E402
from app.api.v1.endpoints.dangerous_functions import router as df_router  # noqa: E402
from app.core.rate_limiter import limiter  # noqa: E402
from app.config.settings import LLMConfig  # noqa: E402
from app.services.llm_analysis_service import (  # noqa: E402
    LLMEndpointBlockedError,
    validate_llm_endpoint,
)

# ---------------------------------------------------------------------------
# 2. Build the app exactly like tests/conftest.py::create_app_client does.
# ---------------------------------------------------------------------------
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    pass
app.include_router(df_router, prefix="/dangerous-functions")


def _mock_user():
    u = mock.Mock()
    u.id = 1
    u.username = "repro"
    u.email = "repro@example.com"
    u.is_active = True
    return u


app.dependency_overrides[get_current_active_user] = lambda: _mock_user()

# The REAL validate_llm_endpoint and the REAL ssrf_guard are used (NOT patched)
# -- that is the whole point of this repro. We only stub the DB boundary and the
# per-user LLM config.
report = mock.Mock()
report.user_id = 1

# THE REAL-WORLD SCENARIO: an enabled LLM pointed at a local endpoint. This is
# the DEFAULT base_url (http://localhost:11434) and the most common local setup.
# Under the "permit local always" policy this MUST now be allowed.
LOCAL_LLM = LLMConfig(enabled=True, base_url="http://localhost:11434", model="llama3")

# A still-blocked non-local endpoint: the cloud metadata link-local address.
# Link-local is NOT part of the "local" carve-out, so the guard must still
# reject it (SSRF-to-metadata protection) and the endpoint must return 503.
BLOCKED_LLM = LLMConfig(enabled=True, base_url="http://169.254.169.254:11434", model="llama3")

FINDING = {
    "function_name": "strcpy",
    "containing_function": "main",
    "entrypoint": "0x401000",
    "category": "Buffer Overflow",
    "severity": "High",
    "cwe": "CWE-120",
    "description": "Unbounded copy.",
    "safe_alternative": "strlcpy",
    "usage_context": ["strcpy(dst, src);"],
    "containing_function_code": "void main(){ strcpy(dst, src); }",
}

BODY = json.dumps({
    "target_name": "repro_target",
    "save": True,
    "findings": [FINDING],
}).encode("utf-8")


def build_scope() -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/dangerous-functions/llm-analysis",
        "raw_path": b"/dangerous-functions/llm-analysis",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(BODY)).encode())],
        "client": ("127.0.0.1", 43210),
        "server": ("testserver", 80),
    }


async def drive_asgi(llm: LLMConfig):
    """Drive the ASGI app directly and record every message sent on the wire."""
    scope = build_scope()
    wire: list[dict] = []
    body_sent = {"n": 0}

    # A real client that stays connected: return the body once, then BLOCK.
    block_forever = asyncio.Event()  # never set -> receive() blocks like a real server

    async def receive():
        body_sent["n"] += 1
        if body_sent["n"] == 1:
            return {"type": "http.request", "body": BODY, "more_body": False}
        await block_forever.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        wire.append(message)

    raised = None
    with (
        mock.patch("app.api.v1.endpoints.dangerous_functions.ScanReportRepository.get_report",
                   new=mock.AsyncMock(return_value=report)),
        mock.patch("app.api.v1.endpoints.dangerous_functions.LLMResultRepository.upsert_one",
                   new=mock.AsyncMock()),
        mock.patch("app.api.v1.endpoints.dangerous_functions.resolve_user_llm_config",
                   new=mock.AsyncMock(return_value=llm)),
    ):
        try:
            await asyncio.wait_for(app(scope, receive, send), timeout=15)
        except Exception as exc:  # noqa: BLE001 - capture any mid-stream crash
            raised = exc
    return wire, raised


# ---------------------------------------------------------------------------
# 3. Replay the frontend's non-2xx handling (streamLlmAnalysis, fixed).
# ---------------------------------------------------------------------------
def frontend_outcome(status: int, body: str):
    """Mirror of the FIXED streamLlmAnalysis non-2xx path.

    Returns (raised_code, raised_message) -- the LlmAnalysisRequestError the
    frontend throws, which runLLMAnalysis/retryLlmAnalysis catch and render as
    an error banner.
    """
    if status == 200:
        # Would enter the SSE reader; a stream with no `done` event now throws
        # STREAM_INCOMPLETE (defense in depth). Not the case for the fix.
        return None, None
    error_data = json.loads(body) if body else {}
    detail = error_data.get("detail") or {}
    error = detail.get("error") or {}
    code = error.get("code") or ("LLM_NOT_CONFIGURED" if status == 503 else "REQUEST_FAILED")
    message = error.get("message") or f"LLM analysis failed ({status})"
    return code, message


def _parse_wire(wire: list[dict]) -> tuple[int | None, str | None, str]:
    """Extract (status, content_type, body) from recorded ASGI messages."""
    start = next((m for m in wire if m["type"] == "http.response.start"), None)
    body_msgs = [m for m in wire if m["type"] == "http.response.body"]
    status = start["status"] if start else None
    ctype = next(
        (v.decode() for k, v in (start or {}).get("headers", []) if k == b"content-type"),
        None,
    )
    body = b"".join(m.get("body", b"") for m in body_msgs).decode("utf-8", "replace")
    return status, ctype, body


def main() -> int:
    print("=" * 78)
    print("VERIFY: local LLM endpoints are permitted; non-local (link-local) still blocked")
    print("=" * 78)
    print(f"Local LLM config (REAL default base_url): {LOCAL_LLM.base_url}  enabled={LOCAL_LLM.enabled}")
    print(f"Blocked LLM config (link-local metadata): {BLOCKED_LLM.base_url}  enabled={BLOCKED_LLM.enabled}")
    print("Using REAL validate_llm_endpoint + REAL ssrf_guard (no live LLM call)\n")

    # ------------------------------------------------------------------
    # Part 1: a LOCAL endpoint is NO LONGER blocked by the guard.
    # validate_llm_endpoint runs the guard with allow_local=True; localhost
    # resolves to loopback, which is permitted, so it must NOT raise.
    # ------------------------------------------------------------------
    print("--- Part 1: local endpoint (http://localhost:11434) ---")
    local_blocked = False
    local_error: str | None = None
    try:
        asyncio.run(validate_llm_endpoint(LOCAL_LLM))
    except LLMEndpointBlockedError as exc:
        local_blocked = True
        local_error = str(exc)
    print(f"  validate_llm_endpoint raised LLMEndpointBlockedError?  {local_blocked}")
    if local_error:
        print(f"  (unexpected) blocked message: {local_error!r}")
    print(f"  -> expected: NOT blocked (local carve-out permits loopback/localhost)\n")

    # ------------------------------------------------------------------
    # Part 2: a still-blocked non-local endpoint returns 503
    # LLM_ENDPOINT_BLOCKED BEFORE any 200/SSE is sent.
    # ------------------------------------------------------------------
    print("--- Part 2: blocked endpoint (http://169.254.169.254:11434) ---")
    wire, raised = asyncio.run(drive_asgi(BLOCKED_LLM))
    status, ctype, body = _parse_wire(wire)
    print(f"  http.response.start sent?  {status is not None}")
    print(f"  status code:                {status}")
    print(f"  content-type:               {ctype}")
    print(f"  SSE 'result' events:        {body.count('event: result')}")
    print(f"  SSE 'done' events:          {body.count('event: done')}")
    print(f"  exception raised mid-stream:{raised!r}")
    try:
        code = (json.loads(body).get("detail") or {}).get("error", {}).get("code")
    except Exception:  # noqa: BLE001
        code = None
    print(f"  error code in body:         {code}")
    print(f"  response body:              {body!r}\n")

    fcode, fmsg = frontend_outcome(status or 0, body)
    print("--- Frontend outcome (streamLlmAnalysis, fixed) ---")
    print(f"  LlmAnalysisRequestError thrown?  {fcode is not None}")
    print(f"  error.code:                     {fcode!r}")
    print(f"  error.message:                  {fmsg!r}")
    print(f"  -> runLLMAnalysis catch fires -> showErrorBanner(message). User sees a clear error.\n")

    print("=" * 78)
    local_ok = not local_blocked
    blocked_ok = (
        status == 503
        and ctype is not None
        and ctype.startswith("application/json")
        and body.count("event: result") == 0
        and body.count("event: done") == 0
        and raised is None
        and code == "LLM_ENDPOINT_BLOCKED"
        and fcode == "LLM_ENDPOINT_BLOCKED"
        and fmsg is not None
    )
    ok = local_ok and blocked_ok
    if ok:
        print("FIX VERIFIED:")
        print("  1. LOCAL endpoint (http://localhost:11434) is permitted -- validate_llm_endpoint")
        print("     does NOT raise (no LLM_ENDPOINT_BLOCKED), so a local Ollama works.")
        print("  2. NON-LOCAL endpoint (http://169.254.169.254:11434) still returns a proper 503")
        print("     LLM_ENDPOINT_BLOCKED BEFORE any 200/SSE is sent (no mid-stream crash), and")
        print("     the frontend surfaces the real error code + message as a banner.")
        print("=" * 78)
        return 0
    print("UNEXPECTED: the fixed behavior was NOT observed -- inspect above.")
    if not local_ok:
        print("  FAIL: local endpoint was still blocked (should be permitted).")
    if not blocked_ok:
        print("  FAIL: blocked endpoint did not return 503 LLM_ENDPOINT_BLOCKED.")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main())
