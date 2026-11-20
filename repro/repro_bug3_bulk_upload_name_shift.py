"""Repro for BUG-3: POST /binaries/uploadBulk mis-assigns names when a
name contains a comma.

Root cause hypothesis
---------------------
``post_upload_bulk`` parses the comma-separated ``names`` form field with a
naive split:

    name_list = [n.strip() for n in names.split(",") if n.strip()]
    ...
    for idx, file in enumerate(files):
        name = name_list[idx] if idx < len(name_list) else (file.filename or f"binary_{idx}")

The endpoint's own OpenAPI description says: "Comma-separated names for each
binary. Must match the number of files."

If a single name legitimately contains a comma (e.g. "firmware, v2"), the split
produces one EXTRA element, so every binary from that position on is shifted by
one: file i gets the name intended for file i+1, and the last file falls back to
its raw filename. The per-file ``name`` in the response (and the stored binary
name) no longer matches what the caller intended — with no error, no warning,
and no way to escape a comma.

This script hits the REAL endpoint through a FastAPI TestClient (with the
upload service + background pipeline mocked) and prints the resulting
file->name assignments.
"""

import os
import sys
from unittest import mock

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

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.v1.endpoints import binaries as binaries_ep  # noqa: E402
from app.auth.dependencies import get_current_active_user  # noqa: E402


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(binaries_ep.router, prefix="/v1/binaries")

    mock_user = mock.Mock()
    mock_user.id = 1
    mock_user.username = "tester"
    mock_user.email = "t@example.com"
    mock_user.is_active = True

    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    return TestClient(app)


def main() -> int:
    print("=" * 72)
    print("BUG-3  uploadBulk name shift when a name contains a comma")
    print("=" * 72)

    client = build_client()

    # Three files; the MIDDLE name contains a comma.
    files = [
        ("files", ("a.bin", b"ELF-a-bytes", "application/octet-stream")),
        ("files", ("b.bin", b"ELF-b-bytes", "application/octet-stream")),
        ("files", ("c.bin", b"ELF-c-bytes", "application/octet-stream")),
    ]
    intended = ["alpha", "firmware, v2", "gamma"]
    names_csv = ",".join(intended)

    captured: list[tuple[str, str]] = []  # (filename, name passed to the service)

    async def fake_upload_binary(*, file_stream, name, user_id, filename):
        captured.append((filename, name))
        return (len(captured), f"/tmp/{filename}")

    with mock.patch.object(
        binaries_ep._upload_service, "upload_binary", side_effect=fake_upload_binary
    ), mock.patch.object(binaries_ep, "_run_upload_pipeline"):
        resp = client.post(
            "/v1/binaries/uploadBulk",
            data={"names": names_csv},
            files=files,
        )

    print(f"\n    HTTP status : {resp.status_code}")
    body = resp.json()
    results = body.get("data", {}).get("results", [])

    print(f"    names form  : {names_csv!r}")
    print(f"    intended    : {intended}")
    print(f"    assigned    :")
    for r in results:
        print(f"      file {r.get('binary_id')} -> name={r.get('name')!r} (status={r.get('status')})")

    assigned = [r.get("name") for r in results]
    # The expected (buggy) shift:
    #   a.bin -> "alpha"
    #   b.bin -> "firmware"        (truncated at the comma!)
    #   c.bin -> " v2".strip() -> "v2"
    #   (gamma is dropped entirely)
    shifted = assigned == ["alpha", "firmware", "v2"]
    correct = assigned == intended

    print(f"\n    intended == assigned : {correct}")
    print(f"    shifted/truncated    : {shifted}")

    print("\n" + "=" * 72)
    print("RESULT")
    print("=" * 72)
    print(f"  BUG-3 (name shift on comma in name): {'CONFIRMED' if (shifted and not correct) else 'NOT reproduced'}")
    return 0 if (shifted and not correct) else 1


if __name__ == "__main__":
    raise SystemExit(main())
