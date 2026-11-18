"""P2 cross-cutting tests: secrets-in-response and status poll performance.

Covers the two non-functional requirements from TESTS.md:

* **Secrets** — an ``enc1:``-prefixed (encrypted) LLM API key must never appear
  in API responses or rendered HTML. The test performs a real round-trip:
  save a key through ``POST /config/save`` (encrypted at rest) then load the
  profile page (decrypted at the repository boundary) and assert neither the
  plaintext secret nor the encrypted token leaks, while the page still reflects
  that a key is stored.
* **Performance** — a smoke benchmark that ``GET /status/getStatus`` p95 stays
  well under the 2000ms client poll interval under 20 concurrent pollers.
"""

import asyncio
import math
import time
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import Mock

import httpx2
import pytest
import pytest_asyncio
from app.config.settings import LLMConfig
from app.database.models import Base, User
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    get_async_session,
    init_async_databases,
)
from app.processing.task_management import TaskManager
from fastapi.testclient import TestClient

from tests.factories import make_user

# A sentinel secret that is easy to spot if it ever leaks into a response.
_SECRET = "sk-super-secret-unique-xyz123"

# The status bar polls every 2s; p95 must stay well under this interval.
_POLL_INTERVAL_MS = 2000.0


# ---------------------------------------------------------------------------
# Database lifecycle (shared by the secrets round-trip test)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def secrets_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize the async DBs and provide fresh auth tables for the module."""
    await init_async_databases()

    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def seeded_user(secrets_db_lifecycle: Any) -> AsyncGenerator[User, None]:
    """Provide a fresh auth DB with a seeded user (id=1) for each test."""
    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    user = make_user(user_id=1, username="testuser", email="test@example.com")
    session = await get_async_session("auth")
    try:
        session.add(user)
        await session.commit()
    finally:
        await session.close()
    yield user


def _settings_mock() -> Any:
    """Build a settings mock with real scalar values (yaml.dump-safe)."""
    settings = Mock()
    settings.max_file_size_mb = 512
    settings.cpu_cores = 4
    settings.llm = LLMConfig()
    return settings


# ---------------------------------------------------------------------------
# Secrets-in-response
# ---------------------------------------------------------------------------


class TestSecretsInResponse:
    """The LLM API key must never appear in API responses or rendered HTML."""

    async def test_api_key_never_leaks(
        self,
        config_client: TestClient,
        web_client: TestClient,
        seeded_user: User,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
    ) -> None:
        """Save a key, then confirm neither plaintext nor ``enc1:`` token leaks."""
        from app.api.v1.endpoints import config as config_module

        # Keep the persisted config.yml out of the repo and use a settings mock
        # for the scalar fields; the LLM upsert/resolve use the real settings so
        # encryption and decryption are exercised for real.
        monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "config.yml")
        monkeypatch.setattr(config_module, "get_settings", lambda: _settings_mock())

        # 1) Save the key through the real upsert (encrypted at rest).
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(config_client.app),
            base_url="http://testserver",
        ) as cfg:
            save_resp = await cfg.post("/config/save", json={"llm": {"api_key": _SECRET}})

        assert save_resp.status_code == 200
        save_body = save_resp.json()
        assert save_body["success"] is True
        assert save_body["data"] == {}
        # Neither the plaintext secret nor the encrypted token may leak.
        assert _SECRET not in save_resp.text
        assert "enc1:" not in save_resp.text

        # 2) Load the profile page (real resolve decrypts at the boundary).
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(web_client.app),
            base_url="http://testserver",
        ) as web:
            profile_resp = await web.get("/profile", headers={"Accept": "text/html"})

        assert profile_resp.status_code == 200
        html = profile_resp.text
        assert _SECRET not in html
        assert "enc1:" not in html
        # The page must reflect that a key is stored (round-trip succeeded).
        assert "A key is already stored" in html


# ---------------------------------------------------------------------------
# Status poll performance
# ---------------------------------------------------------------------------


class TestStatusPollPerformance:
    """GET /status/getStatus must stay well under the 2s client poll interval."""

    async def test_get_status_p95_under_poll_interval(self, status_client: TestClient) -> None:
        """p95 latency stays well under 2000ms under 20 concurrent pollers."""
        job_uuid = TaskManager().get_uuid()
        TaskManager().register_task(job_uuid, "starting", owner_id=1)
        try:
            transport = httpx2.ASGITransport(status_client.app)
            async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
                poller_results = await asyncio.gather(
                    *[self._poller(client, job_uuid, polls_per_poller=5) for _ in range(20)]
                )

            flat = [ms for poller_latencies in poller_results for ms in poller_latencies]
            assert flat, "no latency samples collected"
            p95_ms = self._percentile(flat, 0.95)
            assert p95_ms < _POLL_INTERVAL_MS, (
                f"p95 latency {p95_ms:.1f}ms exceeded the {_POLL_INTERVAL_MS:.0f}ms poll interval "
                f"({len(flat)} requests, max {max(flat):.1f}ms)"
            )
        finally:
            TaskManager().remove_task(job_uuid)

    @staticmethod
    async def _poll_once(client: Any, job_uuid: str) -> float:
        """Issue one status poll and return its latency in milliseconds."""
        start = time.perf_counter()
        resp = await client.get("/status/getStatus", params={"uuid": job_uuid})
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "starting"
        return elapsed_ms

    @classmethod
    async def _poller(cls, client: Any, job_uuid: str, polls_per_poller: int) -> list[float]:
        """Simulate one poller issuing a burst of sequential status polls."""
        return [await cls._poll_once(client, job_uuid) for _ in range(polls_per_poller)]

    @staticmethod
    def _percentile(values: list[float], q: float) -> float:
        """Linear-interpolation percentile (q in [0, 1])."""
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        k = (len(ordered) - 1) * q
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return ordered[int(k)]
        return ordered[f] * (c - k) + ordered[c] * (k - f)
