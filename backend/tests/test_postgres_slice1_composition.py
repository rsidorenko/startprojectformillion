"""Opt-in slice-1 composition flow on PostgreSQL (DATABASE_URL): migrations → UC-01 → UC-02 → audit → replay."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.application.bootstrap import build_slice1_composition
from app.application.handlers import BootstrapIdentityInput, GetSubscriptionStatusInput
from app.persistence.postgres_audit import PostgresAuditAppender
from app.persistence.postgres_idempotency import PostgresIdempotencyRepository
from app.persistence.postgres_migrations import apply_postgres_migrations
from app.persistence.postgres_subscription_snapshot import PostgresSubscriptionSnapshotReader
from app.persistence.postgres_user_identity import PostgresUserIdentityRepository, internal_user_id_for_telegram
from app.security.idempotency import build_bootstrap_idempotency_key
from app.shared.types import OperationOutcomeCategory, SafeUserStatusCategory, SubscriptionSnapshotState

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"

_TG_USER = 8_888_888_800_910
_UPDATE_ID = 9_101
# require_correlation_id: exactly 32 lowercase hex chars
_CORR_BOOT_1 = "a1b2c3d4e5f67890123456789abcdef0"
_CORR_BOOT_2 = "b2c3d4e5f67890123456789abcdef0a1"
_CORR_STATUS = "c3d4e5f67890123456789abcdef0a1b2"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL slice-1 composition integration test")
    return url


async def _cleanup_test_rows(
    conn: asyncpg.Connection,
    *,
    telegram_user_id: int,
    idempotency_key: str,
    correlation_ids: tuple[str, str],
) -> None:
    internal = internal_user_id_for_telegram(telegram_user_id)
    for cid in correlation_ids:
        await conn.execute("DELETE FROM slice1_audit_events WHERE correlation_id = $1::text", cid)
    await conn.execute("DELETE FROM idempotency_records WHERE idempotency_key = $1::text", idempotency_key)
    await conn.execute("DELETE FROM subscription_snapshots WHERE internal_user_id = $1::text", internal)
    await conn.execute("DELETE FROM user_identities WHERE telegram_user_id = $1::bigint", telegram_user_id)


def test_postgres_slice1_composition_bootstrap_status_audit_idempotent_replay(pg_url: str) -> None:
    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        idem_key = build_bootstrap_idempotency_key(_TG_USER, _UPDATE_ID)
        corr_pair = (_CORR_BOOT_1, _CORR_BOOT_2)
        try:
            await apply_postgres_migrations(pool, migrations_directory=_MIGRATIONS_DIR)
            async with pool.acquire() as conn:
                await _cleanup_test_rows(conn, telegram_user_id=_TG_USER, idempotency_key=idem_key, correlation_ids=corr_pair)

            composition = build_slice1_composition(
                identity=PostgresUserIdentityRepository(pool),
                idempotency=PostgresIdempotencyRepository(pool),
                snapshots=PostgresSubscriptionSnapshotReader(pool),
                audit=PostgresAuditAppender(pool),
            )

            r1 = await composition.bootstrap.handle(
                BootstrapIdentityInput(
                    telegram_user_id=_TG_USER,
                    telegram_update_id=_UPDATE_ID,
                    correlation_id=_CORR_BOOT_1,
                ),
            )
            assert r1.outcome == OperationOutcomeCategory.SUCCESS
            assert r1.idempotent_replay is False
            assert r1.internal_user_id == internal_user_id_for_telegram(_TG_USER)
            assert r1.user_safe is None

            snap = await composition.snapshots.get_for_user(r1.internal_user_id or "")
            assert snap is not None
            assert snap.state_label == SubscriptionSnapshotState.INACTIVE.value

            st = await composition.get_status.handle(
                GetSubscriptionStatusInput(telegram_user_id=_TG_USER, correlation_id=_CORR_STATUS),
            )
            assert st.outcome == OperationOutcomeCategory.SUCCESS
            assert st.safe_status == SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE
            assert st.user_safe is None

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT operation, outcome
                    FROM slice1_audit_events
                    WHERE correlation_id = $1::text
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    _CORR_BOOT_1,
                )
            assert row is not None
            assert row["operation"] == "uc01_bootstrap_identity"
            assert row["outcome"] == OperationOutcomeCategory.SUCCESS.value

            r2 = await composition.bootstrap.handle(
                BootstrapIdentityInput(
                    telegram_user_id=_TG_USER,
                    telegram_update_id=_UPDATE_ID,
                    correlation_id=_CORR_BOOT_2,
                ),
            )
            assert r2.outcome == OperationOutcomeCategory.SUCCESS
            assert r2.idempotent_replay is True
            assert r2.internal_user_id == r1.internal_user_id

            snap2 = await composition.snapshots.get_for_user(r1.internal_user_id or "")
            assert snap2 == snap

            async with pool.acquire() as conn:
                replay_audit = await conn.fetchrow(
                    "SELECT id FROM slice1_audit_events WHERE correlation_id = $1::text",
                    _CORR_BOOT_2,
                )
            assert replay_audit is None
        finally:
            async with pool.acquire() as conn:
                await _cleanup_test_rows(conn, telegram_user_id=_TG_USER, idempotency_key=idem_key, correlation_ids=corr_pair)
            await pool.close()

    asyncio.run(main())
