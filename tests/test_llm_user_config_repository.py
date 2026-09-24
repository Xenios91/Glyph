"""Tests for LLMUserConfigRepository (per-user LLM configuration)."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.config.settings import LLMConfig, get_settings
from app.database.llm_user_config_repository import (
    LLMUserConfigRepository,
    resolve_user_llm_config,
)
from app.database.models import Base, LLMUserConfig, User
from app.database.session_handler import (
    DB_TABLE_MAP,
    async_engines,
    dispose_async_engines,
    get_async_session,
    init_async_databases,
)
from tests.factories import make_user

# ---------------------------------------------------------------------------
# Database lifecycle fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", autouse=True)
async def llm_user_config_db_lifecycle() -> AsyncGenerator[None, None]:
    """Initialize and cleanup in-memory databases for LLM user config tests."""
    await init_async_databases()

    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)

    yield
    await dispose_async_engines()


@pytest_asyncio.fixture
async def fresh_auth_tables() -> AsyncGenerator[None, None]:
    """Drop and recreate auth DB tables before each test."""
    target_tables = DB_TABLE_MAP.get("auth")
    if target_tables and "auth" in async_engines:
        async with async_engines["auth"].begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=target_tables)
            await conn.run_sync(Base.metadata.create_all, tables=target_tables)
    yield


async def _seed_user(user_id: int = 1, username: str = "testuser", email: str = "test@example.com") -> User:
    """Insert a user row (required by the LLMUserConfig foreign key)."""
    user = make_user(user_id=user_id, username=username, email=email)
    session = await get_async_session("auth")
    try:
        session.add(user)
        await session.commit()
        return user
    finally:
        await session.close()


class TestGetForUser:
    """get_for_user returns the stored row or None."""

    async def test_returns_none_when_absent(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        assert await LLMUserConfigRepository.get_for_user(1) is None

    async def test_returns_stored_row(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(1, {"model": "llama-3", "enabled": True})

        row = await LLMUserConfigRepository.get_for_user(1)
        assert row is not None
        assert row.user_id == 1
        assert row.model == "llama-3"
        assert row.enabled is True

    async def test_isolated_per_user(self, fresh_auth_tables: Any) -> None:
        await _seed_user(1)
        await _seed_user(2, username="user2", email="user2@example.com")
        await LLMUserConfigRepository.upsert(1, {"model": "user-one"})
        await LLMUserConfigRepository.upsert(2, {"model": "user-two"})

        row_one = await LLMUserConfigRepository.get_for_user(1)
        row_two = await LLMUserConfigRepository.get_for_user(2)
        assert row_one is not None and row_one.model == "user-one"
        assert row_two is not None and row_two.model == "user-two"


class TestUpsert:
    """upsert creates a row from global defaults then applies updates."""

    async def test_create_seeds_from_global_defaults(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        row = await LLMUserConfigRepository.upsert(1, {"model": "gpt-4o"})

        # Only the provided field is overridden; the rest inherit the global settings.
        globals_ = get_settings().llm
        assert row.model == "gpt-4o"
        assert row.enabled == globals_.enabled
        assert row.api_path == globals_.api_path
        assert row.timeout_seconds == globals_.timeout_seconds
        assert row.temperature == globals_.temperature
        assert row.max_concurrent == globals_.max_concurrent

    async def test_update_overwrites_existing_row(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(1, {"model": "old-model", "temperature": 0.5})

        row = await LLMUserConfigRepository.upsert(1, {"model": "new-model"})
        assert row.model == "new-model"
        # Untouched fields are preserved from the existing row.
        assert row.temperature == 0.5

    async def test_upsert_is_idempotent_single_row(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(1, {"model": "a"})
        await LLMUserConfigRepository.upsert(1, {"model": "b"})

        session = await get_async_session("auth")
        try:
            from sqlalchemy import func, select

            count = (
                await session.execute(select(func.count()).select_from(LLMUserConfig))
            ).scalar_one()
        finally:
            await session.close()
        assert count == 1


class TestDeleteForUser:
    """delete_for_user removes the row and reports whether anything was stored."""

    async def test_delete_existing_returns_true(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(1, {"model": "x"})

        assert await LLMUserConfigRepository.delete_for_user(1) is True
        assert await LLMUserConfigRepository.get_for_user(1) is None

    async def test_delete_absent_returns_false(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        assert await LLMUserConfigRepository.delete_for_user(1) is False


class TestResolveUserLlmConfig:
    """resolve_user_llm_config merges the user row over global defaults."""

    async def test_no_row_returns_global_defaults(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        resolved = await resolve_user_llm_config(1)
        assert resolved == get_settings().llm

    async def test_row_overrides_defaults_field_by_field(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(
            1, {"model": "llama-3", "base_url": "http://localhost:8000", "enabled": True},
        )

        resolved = await resolve_user_llm_config(1)
        assert resolved.model == "llama-3"
        assert resolved.base_url == "http://localhost:8000"
        assert resolved.enabled is True
        # Fields the user did not set fall back to the global settings.
        globals_ = get_settings().llm
        assert resolved.api_path == globals_.api_path
        assert resolved.temperature == globals_.temperature
        assert resolved.max_concurrent == globals_.max_concurrent

    async def test_returns_pydantic_llm_config(self, fresh_auth_tables: Any) -> None:
        await _seed_user()
        await LLMUserConfigRepository.upsert(1, {"model": "m"})
        resolved = await resolve_user_llm_config(1)
        assert isinstance(resolved, LLMConfig)
