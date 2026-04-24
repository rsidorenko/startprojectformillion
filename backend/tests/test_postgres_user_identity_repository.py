"""Contract tests for PostgresUserIdentityRepository against a real PostgreSQL (opt-in via DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.persistence.postgres_user_identity import PostgresUserIdentityRepository

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = BACKEND_ROOT / "migrations" / "001_user_identities.sql"
_TG_LO = 8_888_888_800_000


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


def _apply_schema_sql() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL identity repository tests")
    return url


def test_postgres_identity_creates_once_and_reuses(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            telegram_user_id = _TG_LO + 1
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM user_identities WHERE telegram_user_id = $1::bigint",
                    telegram_user_id,
                )
            repo = PostgresUserIdentityRepository(pool)
            a = await repo.create_if_absent(telegram_user_id)
            b = await repo.create_if_absent(telegram_user_id)
            assert a.internal_user_id == b.internal_user_id == f"u{telegram_user_id}"
            found = await repo.find_by_telegram_user_id(telegram_user_id)
            assert found is not None
            assert found.telegram_user_id == telegram_user_id
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_identity_find_returns_none_when_missing(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            telegram_user_id = _TG_LO + 2
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM user_identities WHERE telegram_user_id = $1::bigint",
                    telegram_user_id,
                )
            repo = PostgresUserIdentityRepository(pool)
            assert await repo.find_by_telegram_user_id(telegram_user_id) is None
        finally:
            await pool.close()

    asyncio.run(main())
