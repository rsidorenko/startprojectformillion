"""Opt-in async env process on PostgreSQL: DATABASE_URL + env process builder + one iteration."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import httpx
import pytest

from app.persistence.postgres_migrations import apply_postgres_migrations
from app.persistence.postgres_user_identity import internal_user_id_for_telegram
from app.runtime.telegram_httpx_live_process import build_slice1_httpx_live_process_from_env_async
from app.security.idempotency import build_bootstrap_idempotency_key
from app.shared.types import OperationOutcomeCategory, SubscriptionSnapshotState

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"

_TG_USER = 8_888_888_801_931
_UPDATE_ID = 9_131
_CORR_ID = "c5f67890123456789abcdef0a1b2c3d4"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL slice-1 env async process integration test")
    return url


def _start_update(*, update_id: int, user_id: int) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "is_bot": False, "first_name": "T"},
            "chat": {"id": user_id, "type": "private"},
            "text": "/start",
        },
    }


async def _cleanup_test_rows(
    conn: asyncpg.Connection,
    *,
    telegram_user_id: int,
    idempotency_key: str,
    correlation_id: str,
) -> None:
    internal = internal_user_id_for_telegram(telegram_user_id)
    await conn.execute("DELETE FROM slice1_audit_events WHERE correlation_id = $1::text", correlation_id)
    await conn.execute(
        "DELETE FROM slice1_uc01_outbound_deliveries WHERE idempotency_key = $1::text",
        idempotency_key,
    )
    await conn.execute("DELETE FROM idempotency_records WHERE idempotency_key = $1::text", idempotency_key)
    await conn.execute("DELETE FROM subscription_snapshots WHERE internal_user_id = $1::text", internal)
    await conn.execute("DELETE FROM user_identities WHERE telegram_user_id = $1::bigint", telegram_user_id)


def test_postgres_slice1_env_async_process_run_until_stopped_writes_rows(
    pg_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("SLICE1_USE_POSTGRES_REPOS", "1")

    idem_key = build_bootstrap_idempotency_key(_TG_USER, _UPDATE_ID)
    send_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_posts
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={"ok": True, "result": [_start_update(update_id=_UPDATE_ID, user_id=_TG_USER)]},
            )
        if request.url.path.endswith("/sendMessage"):
            send_posts += 1
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(404)

    async def main() -> None:
        conn = await asyncpg.connect(pg_url)
        try:
            await apply_postgres_migrations(conn, migrations_directory=_MIGRATIONS_DIR)
            await _cleanup_test_rows(
                conn,
                telegram_user_id=_TG_USER,
                idempotency_key=idem_key,
                correlation_id=_CORR_ID,
            )
        finally:
            await conn.close()

        transport = httpx.MockTransport(handler)
        try:
            async with httpx.AsyncClient(transport=transport) as ac:
                process = await build_slice1_httpx_live_process_from_env_async(client=ac)
                try:
                    summary = await process.run_until_stopped(
                        max_iterations=1,
                        correlation_id=_CORR_ID,
                    )
                    assert summary.send_count == 1
                    assert summary.fetch_failure_count == 0
                    assert summary.send_failure_count == 0
                    assert send_posts == 1

                    vconn = await asyncpg.connect(pg_url)
                    try:
                        ident = await vconn.fetchrow(
                            "SELECT internal_user_id FROM user_identities WHERE telegram_user_id = $1::bigint",
                            _TG_USER,
                        )
                        assert ident is not None
                        assert ident["internal_user_id"] == internal_user_id_for_telegram(_TG_USER)

                        idem = await vconn.fetchrow(
                            "SELECT completed FROM idempotency_records WHERE idempotency_key = $1::text",
                            idem_key,
                        )
                        assert idem is not None
                        assert idem["completed"] is True

                        snap = await vconn.fetchrow(
                            "SELECT state_label FROM subscription_snapshots WHERE internal_user_id = $1::text",
                            internal_user_id_for_telegram(_TG_USER),
                        )
                        assert snap is not None
                        assert snap["state_label"] == SubscriptionSnapshotState.INACTIVE.value

                        audit = await vconn.fetchrow(
                            """
                            SELECT operation, outcome
                            FROM slice1_audit_events
                            WHERE correlation_id = $1::text
                            ORDER BY id DESC
                            LIMIT 1
                            """,
                            _CORR_ID,
                        )
                        assert audit is not None
                        assert audit["operation"] == "uc01_bootstrap_identity"
                        assert audit["outcome"] == OperationOutcomeCategory.SUCCESS.value
                    finally:
                        await vconn.close()
                finally:
                    await process.aclose()
        finally:
            c2 = await asyncpg.connect(pg_url)
            try:
                await _cleanup_test_rows(
                    c2,
                    telegram_user_id=_TG_USER,
                    idempotency_key=idem_key,
                    correlation_id=_CORR_ID,
                )
            finally:
                await c2.close()

    asyncio.run(main())
