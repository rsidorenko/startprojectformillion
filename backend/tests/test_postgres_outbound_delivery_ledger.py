"""Opt-in tests for PostgresOutboundDeliveryLedger (DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.persistence.postgres_migrations import apply_postgres_migrations
from app.persistence.postgres_outbound_delivery import PostgresOutboundDeliveryLedger

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping Postgres outbound delivery ledger tests")
    return url


def test_postgres_outbound_delivery_pending_sent_roundtrip(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        key = "0" * 64
        try:
            await apply_postgres_migrations(pool, migrations_directory=_MIGRATIONS_DIR)
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM slice1_uc01_outbound_deliveries WHERE idempotency_key = $1::text",
                    key,
                )
            ledger = PostgresOutboundDeliveryLedger(pool)
            assert await ledger.get_status(key) is None
            await ledger.ensure_pending(key)
            st1 = await ledger.get_status(key)
            assert st1 is not None and st1.status == "pending" and st1.telegram_message_id is None
            await ledger.ensure_pending(key)
            await ledger.mark_sent(key, 4242)
            st2 = await ledger.get_status(key)
            assert st2 is not None and st2.status == "sent" and st2.telegram_message_id == 4242
            await ledger.mark_sent(key, 9999)
            st3 = await ledger.get_status(key)
            assert st3 is not None and st3.telegram_message_id == 4242
        finally:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM slice1_uc01_outbound_deliveries WHERE idempotency_key = $1::text",
                    key,
                )
            await pool.close()

    asyncio.run(main())
