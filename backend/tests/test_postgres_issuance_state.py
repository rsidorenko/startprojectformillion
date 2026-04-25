"""PostgresIssuanceStateRepository (opt-in via DATABASE_URL, real PostgreSQL)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.persistence.issuance_state_record import IssuanceStatePersistence
from app.persistence.postgres_issuance_state import PostgresIssuanceStateRepository, _assert_non_secret_provider_ref
from app.security.errors import InternalErrorCategory, PersistenceDependencyError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = BACKEND_ROOT / "migrations" / "011_issuance_state.sql"
_KEY_PREFIX = "test_pgis_"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL issuance_state tests")
    return url


def _apply_011() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


_FORBIDDEN = (
    "PRIVATE KEY",
    "BEGIN ",
    "token=",
    "postgres://",
    "postgresql://",
    "Bearer ",
    "vpn://",
)


def _assert_no_forbidden_in_text(s: str) -> None:
    u = s.upper()
    for frag in _FORBIDDEN:
        assert frag not in u


def test_migrations_list_includes_011() -> None:
    assert "011_issuance_state.sql" in _MIGRATION_PATH.name


def test_reject_ref_looks_like_secret() -> None:
    with pytest.raises(ValueError, match="opaque non-secret"):
        _assert_non_secret_provider_ref("https://x.example/v?token=abc")

    with pytest.raises(ValueError, match="opaque non-secret"):
        _assert_non_secret_provider_ref("prefix postgresql://hidden")


@pytest.mark.asyncio
async def test_pool_acquire_error_wraps_as_dependency() -> None:
    class _FailOnEnter:
        async def __aenter__(self) -> object:
            raise OSError("simulated transport failure to pool")

        async def __aexit__(self, *args: object) -> None:
            return None

    class _BadPool:
        def acquire(self) -> _FailOnEnter:
            return _FailOnEnter()

    repo: PostgresIssuanceStateRepository = PostgresIssuanceStateRepository(_BadPool())  # type: ignore[arg-type]
    with pytest.raises(PersistenceDependencyError) as excinfo:
        await repo.issue_or_get(
            internal_user_id="u1",
            issue_idempotency_key="ik1",
            provider_issuance_ref="issuance-ref:fake:ok",
        )
    assert excinfo.value.category is InternalErrorCategory.PERSISTENCE_TRANSIENT


def test_postgres_issuance_issue_idempotent_and_no_overwrite_ref(pg_url: str) -> None:
    user = f"{_KEY_PREFIX}user-1"
    ikey = f"{_KEY_PREFIX}ik-issue-1"
    first_ref = f"issuance-ref:fake:{_KEY_PREFIX}a"[:64]
    alt_ref = f"issuance-ref:fake:{_KEY_PREFIX}different"[:64]

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM issuance_state WHERE internal_user_id = $1::text",
                    user,
                )
            repo = PostgresIssuanceStateRepository(pool)
            a = await repo.issue_or_get(
                internal_user_id=user,
                issue_idempotency_key=ikey,
                provider_issuance_ref=first_ref,
            )
            assert a.state is IssuanceStatePersistence.ISSUED
            assert a.provider_issuance_ref == first_ref
            _assert_no_forbidden_in_text(a.provider_issuance_ref)
            b = await repo.issue_or_get(
                internal_user_id=user,
                issue_idempotency_key=ikey,
                provider_issuance_ref=alt_ref,
            )
            assert b.provider_issuance_ref == first_ref, "second issue must not overwrite ref"
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_same_idem_different_user_no_collision(pg_url: str) -> None:
    u1 = f"{_KEY_PREFIX}user-a"
    u2 = f"{_KEY_PREFIX}user-b"
    ikey = f"{_KEY_PREFIX}shared-ik"
    r1s = f"issuance-ref:u1"
    r2s = f"issuance-ref:u2"

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            for u in (u1, u2):
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM issuance_state WHERE internal_user_id = $1::text",
                        u,
                    )
            repo = PostgresIssuanceStateRepository(pool)
            a = await repo.issue_or_get(
                internal_user_id=u1, issue_idempotency_key=ikey, provider_issuance_ref=r1s
            )
            b = await repo.issue_or_get(
                internal_user_id=u2, issue_idempotency_key=ikey, provider_issuance_ref=r2s
            )
            assert a.internal_user_id == u1 and b.internal_user_id == u2
            assert a.provider_issuance_ref != b.provider_issuance_ref
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_mark_revoked_idempotent_and_get_current(pg_url: str) -> None:
    user = f"{_KEY_PREFIX}user-rev"
    ikey = f"{_KEY_PREFIX}ik-r"
    ref = f"issuance-ref:rev-{_KEY_PREFIX}z"[:64]

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM issuance_state WHERE internal_user_id = $1::text",
                    user,
                )
            repo = PostgresIssuanceStateRepository(pool)
            _ = await repo.issue_or_get(
                internal_user_id=user,
                issue_idempotency_key=ikey,
                provider_issuance_ref=ref,
            )
            m1 = await repo.mark_revoked(internal_user_id=user, issue_idempotency_key=ikey)
            assert m1 is not None
            assert m1.state is IssuanceStatePersistence.REVOKED
            assert m1.revoked_at is not None
            m2 = await repo.mark_revoked(internal_user_id=user, issue_idempotency_key=ikey)
            assert m2 is not None
            assert m2.state is IssuanceStatePersistence.REVOKED
            cur = await repo.get_current_for_user(user)
            assert cur is not None
            assert cur.state is IssuanceStatePersistence.REVOKED
            for bit in (str(m1), repr(m1.provider_issuance_ref), cur.provider_issuance_ref):
                _assert_no_forbidden_in_text(bit)
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_mark_revoke_missing_row_returns_none(pg_url: str) -> None:
    user = f"{_KEY_PREFIX}nope-user"
    ikey = f"{_KEY_PREFIX}ik-miss"

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM issuance_state WHERE internal_user_id = $1::text",
                    user,
                )
            repo = PostgresIssuanceStateRepository(pool)
            m = await repo.mark_revoked(internal_user_id=user, issue_idempotency_key=ikey)
            assert m is None
        finally:
            await pool.close()

    asyncio.run(main())
