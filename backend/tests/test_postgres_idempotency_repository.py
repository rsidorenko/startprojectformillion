"""Contract tests for PostgresIdempotencyRepository against PostgreSQL (opt-in via DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.persistence.postgres_idempotency import PostgresIdempotencyRepository

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = BACKEND_ROOT / "migrations" / "002_idempotency_records.sql"
_KEY_PREFIX = "test_idem_pg_"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


def _apply_schema_sql() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL idempotency repository tests")
    return url


def test_postgres_idempotency_begin_or_get_and_complete(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            key = f"{_KEY_PREFIX}contract_1"
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM idempotency_records WHERE idempotency_key = $1::text",
                    key,
                )
            repo = PostgresIdempotencyRepository(pool)
            assert await repo.get(key) is None
            r1 = await repo.begin_or_get(key)
            assert r1.key == key and r1.completed is False
            r2 = await repo.begin_or_get(key)
            assert r2.completed is False
            await repo.complete(key)
            r3 = await repo.begin_or_get(key)
            assert r3.completed is True
            g = await repo.get(key)
            assert g is not None and g.completed is True
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_idempotency_complete_without_begin_or_get(pg_url: str) -> None:
    """Matches InMemoryIdempotencyRepository: complete materializes completed=True."""

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            key = f"{_KEY_PREFIX}complete_only"
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM idempotency_records WHERE idempotency_key = $1::text",
                    key,
                )
            repo = PostgresIdempotencyRepository(pool)
            assert await repo.get(key) is None
            await repo.complete(key)
            got = await repo.get(key)
            assert got is not None and got.completed is True
            r = await repo.begin_or_get(key)
            assert r.completed is True
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_idempotency_concurrent_begin_or_get_same_key(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=4)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            key = f"{_KEY_PREFIX}concurrent"
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM idempotency_records WHERE idempotency_key = $1::text",
                    key,
                )
            repo = PostgresIdempotencyRepository(pool)
            results = await asyncio.gather(*[repo.begin_or_get(key) for _ in range(20)])
            assert all(r.key == key and r.completed is False for r in results)
        finally:
            await pool.close()

    asyncio.run(main())
