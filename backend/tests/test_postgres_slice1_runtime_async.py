"""Opt-in async httpx live runtime on PostgreSQL: DATABASE_URL + SLICE1_USE_POSTGRES_REPOS + one /start iteration."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import httpx
import pytest

from app.persistence.postgres_migrations import apply_postgres_migrations
from app.persistence.postgres_user_identity import internal_user_id_for_telegram
from app.runtime.telegram_httpx_live_configured import build_slice1_httpx_live_runtime_app_from_config_async
from app.security.config import RuntimeConfig
from app.security.idempotency import build_bootstrap_idempotency_key
from app.shared.types import OperationOutcomeCategory, SubscriptionSnapshotState

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = BACKEND_ROOT / "migrations"

_TG_USER = 8_888_888_800_920
_UPDATE_ID = 9_120
_CORR_BOOT = "d4e5f67890123456789abcdef0a1b2c3"

_TG_USER_REPLAY = 8_888_888_800_921
_UPDATE_ID_REPLAY = 9_121
_CORR_REPLAY_FIRST = "e5f6a7890123456789abcdef01b2c34"
_CORR_REPLAY_SECOND = "f6a7b890123456789abcdef012c3456"

_TG_SENDFAIL = 8_888_888_800_922
_UPDATE_SENDFAIL = 9_122
_CORR_SENDFAIL_FIRST = "a0b1c2d3e4f567890123456789abcd01"
_CORR_SENDFAIL_SECOND = "b1c2d3e4f567890123456789abcd012"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL slice-1 async runtime integration test")
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
    correlation_ids: tuple[str, ...],
) -> None:
    internal = internal_user_id_for_telegram(telegram_user_id)
    for cid in correlation_ids:
        await conn.execute("DELETE FROM slice1_audit_events WHERE correlation_id = $1::text", cid)
    await conn.execute("DELETE FROM idempotency_records WHERE idempotency_key = $1::text", idempotency_key)
    await conn.execute(
        "DELETE FROM slice1_uc01_outbound_deliveries WHERE idempotency_key = $1::text",
        idempotency_key,
    )
    await conn.execute("DELETE FROM subscription_snapshots WHERE internal_user_id = $1::text", internal)
    await conn.execute("DELETE FROM user_identities WHERE telegram_user_id = $1::bigint", telegram_user_id)


def test_postgres_slice1_async_runtime_start_iteration_writes_rows(
    pg_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLICE1_USE_POSTGRES_REPOS", "1")
    idem_key = build_bootstrap_idempotency_key(_TG_USER, _UPDATE_ID)
    corr_ids = (_CORR_BOOT,)
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
                correlation_ids=corr_ids,
            )
        finally:
            await conn.close()

        cfg = RuntimeConfig(
            bot_token="1234567890tok",
            database_url=pg_url,
            app_env="development",
            debug_safe=False,
        )
        transport = httpx.MockTransport(handler)
        try:
            async with httpx.AsyncClient(transport=transport) as ac:
                app = await build_slice1_httpx_live_runtime_app_from_config_async(cfg, client=ac)
                try:
                    summary = await app.run_iterations(1, correlation_id=_CORR_BOOT)
                    assert summary.fetch_failure_count == 0
                    assert summary.send_failure_count == 0
                    assert summary.send_count == 1
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
                            _CORR_BOOT,
                        )
                        assert audit is not None
                        assert audit["operation"] == "uc01_bootstrap_identity"
                        assert audit["outcome"] == OperationOutcomeCategory.SUCCESS.value
                    finally:
                        await vconn.close()
                finally:
                    await app.aclose()
        finally:
            c2 = await asyncpg.connect(pg_url)
            try:
                await _cleanup_test_rows(
                    c2,
                    telegram_user_id=_TG_USER,
                    idempotency_key=idem_key,
                    correlation_ids=corr_ids,
                )
            finally:
                await c2.close()

    asyncio.run(main())


def test_postgres_slice1_async_runtime_same_start_update_replay_idempotent(
    pg_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SLICE1_USE_POSTGRES_REPOS", "1")
    idem_key = build_bootstrap_idempotency_key(_TG_USER_REPLAY, _UPDATE_ID_REPLAY)
    corr_ids = (_CORR_REPLAY_FIRST, _CORR_REPLAY_SECOND)
    send_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_posts
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [_start_update(update_id=_UPDATE_ID_REPLAY, user_id=_TG_USER_REPLAY)],
                },
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
                telegram_user_id=_TG_USER_REPLAY,
                idempotency_key=idem_key,
                correlation_ids=corr_ids,
            )
        finally:
            await conn.close()

        cfg = RuntimeConfig(
            bot_token="1234567890tok",
            database_url=pg_url,
            app_env="development",
            debug_safe=False,
        )
        transport = httpx.MockTransport(handler)
        try:
            async with httpx.AsyncClient(transport=transport) as ac:
                app = await build_slice1_httpx_live_runtime_app_from_config_async(cfg, client=ac)
                try:
                    s1 = await app.run_iterations(1, correlation_id=_CORR_REPLAY_FIRST)
                    s2 = await app.run_iterations(1, correlation_id=_CORR_REPLAY_SECOND)
                    assert s1.fetch_failure_count == 0
                    assert s1.send_failure_count == 0
                    assert s1.send_count == 1
                    assert s1.noop_count == 0
                    assert s2.fetch_failure_count == 0
                    assert s2.send_failure_count == 0
                    assert s2.send_count == 0
                    assert s2.noop_count == 1
                    assert send_posts == 1

                    vconn = await asyncpg.connect(pg_url)
                    try:
                        n_idents = await vconn.fetchval(
                            "SELECT COUNT(*)::int FROM user_identities WHERE telegram_user_id = $1::bigint",
                            _TG_USER_REPLAY,
                        )
                        assert n_idents == 1

                        idem = await vconn.fetchrow(
                            "SELECT completed FROM idempotency_records WHERE idempotency_key = $1::text",
                            idem_key,
                        )
                        assert idem is not None
                        assert idem["completed"] is True
                        n_idem = await vconn.fetchval(
                            "SELECT COUNT(*)::int FROM idempotency_records WHERE idempotency_key = $1::text",
                            idem_key,
                        )
                        assert n_idem == 1

                        internal = internal_user_id_for_telegram(_TG_USER_REPLAY)
                        n_snaps = await vconn.fetchval(
                            "SELECT COUNT(*)::int FROM subscription_snapshots WHERE internal_user_id = $1::text",
                            internal,
                        )
                        assert n_snaps == 1
                        snap = await vconn.fetchrow(
                            "SELECT state_label FROM subscription_snapshots WHERE internal_user_id = $1::text",
                            internal,
                        )
                        assert snap is not None
                        assert snap["state_label"] == SubscriptionSnapshotState.INACTIVE.value

                        n_audit_first = await vconn.fetchval(
                            """
                            SELECT COUNT(*)::int
                            FROM slice1_audit_events
                            WHERE correlation_id = $1::text
                              AND operation = 'uc01_bootstrap_identity'
                              AND outcome = $2::text
                            """,
                            _CORR_REPLAY_FIRST,
                            OperationOutcomeCategory.SUCCESS.value,
                        )
                        assert n_audit_first == 1
                        n_audit_second = await vconn.fetchval(
                            """
                            SELECT COUNT(*)::int
                            FROM slice1_audit_events
                            WHERE correlation_id = $1::text
                            """,
                            _CORR_REPLAY_SECOND,
                        )
                        assert n_audit_second == 0
                    finally:
                        await vconn.close()
                finally:
                    await app.aclose()
        finally:
            c2 = await asyncpg.connect(pg_url)
            try:
                await _cleanup_test_rows(
                    c2,
                    telegram_user_id=_TG_USER_REPLAY,
                    idempotency_key=idem_key,
                    correlation_ids=corr_ids,
                )
            finally:
                await c2.close()

    asyncio.run(main())


def test_postgres_slice1_async_runtime_send_fail_then_replay_sends_once(
    pg_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First Telegram send fails after UC-01 commit; second poll with same update delivers once."""
    monkeypatch.setenv("SLICE1_USE_POSTGRES_REPOS", "1")
    idem_key = build_bootstrap_idempotency_key(_TG_SENDFAIL, _UPDATE_SENDFAIL)
    corr_ids = (_CORR_SENDFAIL_FIRST, _CORR_SENDFAIL_SECOND)
    send_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_posts
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [_start_update(update_id=_UPDATE_SENDFAIL, user_id=_TG_SENDFAIL)],
                },
            )
        if request.url.path.endswith("/sendMessage"):
            send_posts += 1
            if send_posts == 1:
                return httpx.Response(503, json={"ok": False})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 777}})
        return httpx.Response(404)

    async def main() -> None:
        conn = await asyncpg.connect(pg_url)
        try:
            await apply_postgres_migrations(conn, migrations_directory=_MIGRATIONS_DIR)
            await _cleanup_test_rows(
                conn,
                telegram_user_id=_TG_SENDFAIL,
                idempotency_key=idem_key,
                correlation_ids=corr_ids,
            )
        finally:
            await conn.close()

        cfg = RuntimeConfig(
            bot_token="1234567890tok",
            database_url=pg_url,
            app_env="development",
            debug_safe=False,
        )
        transport = httpx.MockTransport(handler)
        try:
            async with httpx.AsyncClient(transport=transport) as ac:
                app = await build_slice1_httpx_live_runtime_app_from_config_async(cfg, client=ac)
                try:
                    s1 = await app.run_iterations(1, correlation_id=_CORR_SENDFAIL_FIRST)
                    s2 = await app.run_iterations(1, correlation_id=_CORR_SENDFAIL_SECOND)
                    assert s1.fetch_failure_count == 0
                    assert s1.send_failure_count == 1
                    assert s1.send_count == 0
                    assert s2.fetch_failure_count == 0
                    assert s2.send_failure_count == 0
                    assert s2.send_count == 1
                    assert send_posts == 2

                    vconn = await asyncpg.connect(pg_url)
                    try:
                        row = await vconn.fetchrow(
                            """
                            SELECT delivery_status, telegram_message_id
                            FROM slice1_uc01_outbound_deliveries
                            WHERE idempotency_key = $1::text
                            """,
                            idem_key,
                        )
                        assert row is not None
                        assert row["delivery_status"] == "sent"
                        assert row["telegram_message_id"] == 777
                    finally:
                        await vconn.close()
                finally:
                    await app.aclose()
        finally:
            c2 = await asyncpg.connect(pg_url)
            try:
                await _cleanup_test_rows(
                    c2,
                    telegram_user_id=_TG_SENDFAIL,
                    idempotency_key=idem_key,
                    correlation_ids=corr_ids,
                )
            finally:
                await c2.close()

    asyncio.run(main())
