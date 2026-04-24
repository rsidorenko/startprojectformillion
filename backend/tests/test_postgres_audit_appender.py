"""Contract tests for PostgresAuditAppender against PostgreSQL (opt-in via DATABASE_URL)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.application.interfaces import AuditEvent
from app.persistence.postgres_audit import PostgresAuditAppender
from app.shared.types import OperationOutcomeCategory

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = BACKEND_ROOT / "migrations" / "004_slice1_audit_events.sql"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


def _apply_schema_sql() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL audit appender tests")
    return url


def test_postgres_audit_appender_persists_row(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_schema_sql())
            cid = "test-correlation-slice1-audit-1"
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM slice1_audit_events WHERE correlation_id = $1::text",
                    cid,
                )
            appender = PostgresAuditAppender(pool)
            await appender.append(
                AuditEvent(
                    correlation_id=cid,
                    operation="uc01_bootstrap_identity",
                    outcome=OperationOutcomeCategory.SUCCESS,
                    internal_category=None,
                )
            )
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT correlation_id, operation, outcome, internal_category
                    FROM slice1_audit_events
                    WHERE correlation_id = $1::text
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    cid,
                )
            assert row is not None
            assert row["correlation_id"] == cid
            assert row["operation"] == "uc01_bootstrap_identity"
            assert row["outcome"] == OperationOutcomeCategory.SUCCESS.value
            assert row["internal_category"] is None
        finally:
            await pool.close()

    asyncio.run(main())
