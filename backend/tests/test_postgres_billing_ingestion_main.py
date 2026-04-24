"""Opt-in: Postgres + billing operator async_main (DATABASE_URL)."""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg
import pytest

from app.application.billing_ingestion_main import BILLING_NORMALIZED_INGEST_ENABLE, async_main
from app.persistence.postgres_migrations import apply_postgres_migrations

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"
_PREFIX = "test_pbnmain_"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL billing main tests")
    return url


def _min_payload(ext: str, corr: str) -> str:
    t0 = "2026-01-20T10:00:00+00:00"
    return (
        f'{{"schema_version":1,'
        f'"billing_provider_key":"prov_main_ci",'
        f'"external_event_id":"{_PREFIX}{ext}",'
        f'"event_type":"payment_succeeded",'
        f'"event_effective_at":"{t0}",'
        f'"event_received_at":"{t0}",'
        f'"status":"accepted",'
        f'"ingestion_correlation_id":"{_PREFIX}{corr}"}}'
    )


async def _cleanup(pool: asyncpg.Pool) -> None:
    await apply_postgres_migrations(pool, migrations_directory=_MIGRATIONS_DIR)
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM billing_ingestion_audit_events WHERE external_event_id LIKE $1::text",
            f"{_PREFIX}%",
        )
        await conn.execute(
            "DELETE FROM billing_events_ledger WHERE external_event_id LIKE $1::text",
            f"{_PREFIX}%",
        )


@pytest.mark.asyncio
async def test_postgres_main_ingest_writes_ledger_and_audit(
    pg_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(BILLING_NORMALIZED_INGEST_ENABLE, "1")
    monkeypatch.setenv("BOT_TOKEN", "x" * 20)
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("APP_ENV", "test")

    pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
    try:
        await _cleanup(pool)
    finally:
        await pool.close()

    ext = "evt-1"
    f = tmp_path / "f.json"
    f.write_text(_min_payload(ext, "c1"), encoding="utf-8")
    code = await async_main(["--input-file", str(f)])
    assert code == 0
    eid = f"{_PREFIX}{ext}"

    pool2 = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
    try:
        async with pool2.acquire() as conn:
            n = await conn.fetchval(
                "SELECT count(*)::bigint FROM billing_events_ledger WHERE external_event_id = $1", eid
            )
        assert n == 1
        async with pool2.acquire() as conn:
            n2 = await conn.fetchval(
                "SELECT count(*)::bigint FROM billing_ingestion_audit_events WHERE external_event_id = $1", eid
            )
        assert n2 == 1
    finally:
        await pool2.close()
