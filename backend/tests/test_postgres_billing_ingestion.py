"""Opt-in: Postgres + IngestNormalizedBillingFactHandler (DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from app.application.billing_ingestion import IngestNormalizedBillingFactHandler, NormalizedBillingFactInput
from app.persistence import BillingEventAmountCurrency, BillingEventLedgerStatus, PostgresBillingEventsLedgerRepository
from app.persistence.postgres_migrations import apply_postgres_migrations

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"
_PREFIX = "test_pbing_"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL billing ingestion tests")
    return url


async def _cleanup_and_migrate(pool: asyncpg.Pool) -> None:
    await apply_postgres_migrations(pool, migrations_directory=_MIGRATIONS_DIR)
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM billing_events_ledger WHERE internal_fact_ref LIKE $1::text",
            f"{_PREFIX}%",
        )


def test_postgres_ingest_handler_persists_and_idempotent_replay(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            await _cleanup_and_migrate(pool)
            repo = PostgresBillingEventsLedgerRepository(pool)
            handler = IngestNormalizedBillingFactHandler(repo)
            t0 = datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc)
            t1 = datetime(2026, 1, 10, 8, 0, 1, tzinfo=timezone.utc)
            ext = f"{_PREFIX}ext-1"
            in1 = NormalizedBillingFactInput(
                billing_provider_key="provider_ingest_ci",
                external_event_id=ext,
                event_type="payment_succeeded",
                event_effective_at=t0,
                event_received_at=t1,
                status=BillingEventLedgerStatus.ACCEPTED,
                ingestion_correlation_id="corr-pg-1",
                internal_user_id=f"{_PREFIX}u1",
                amount_currency=BillingEventAmountCurrency(
                    amount_minor_units=100,
                    currency_code="USD",
                ),
            )
            r1 = await handler.handle(in1)
            assert r1.is_idempotent_replay is False
            ref1 = r1.record.internal_fact_ref
            r2 = await handler.handle(
                NormalizedBillingFactInput(
                    billing_provider_key="provider_ingest_ci",
                    external_event_id=ext,
                    event_type="payment_succeeded",
                    event_effective_at=t0,
                    event_received_at=t1,
                    status=BillingEventLedgerStatus.ACCEPTED,
                    ingestion_correlation_id="corr-pg-2",
                    internal_user_id=f"{_PREFIX}u1",
                )
            )
            assert r2.is_idempotent_replay is True
            assert r2.record.internal_fact_ref == ref1
            async with pool.acquire() as conn:
                n = await conn.fetchval("SELECT count(*)::bigint FROM billing_events_ledger WHERE external_event_id = $1", ext)
            assert n == 1
        finally:
            await pool.close()

    asyncio.run(main())
