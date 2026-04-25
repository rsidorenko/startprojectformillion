"""IssuanceService + PostgresIssuanceStateRepository (DATABASE_URL opt-in)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest

from app.issuance.contracts import (
    CreateAccessOutcome,
    IssuanceOperationType,
    IssuanceOutcomeCategory,
    IssuanceRequest,
    ProviderCreateResult,
)
from app.issuance.fake_provider import FakeIssuanceProvider, FakeProviderMode
from app.issuance.service import IssuanceService
from app.persistence.issuance_state_record import IssuanceStatePersistence
from app.persistence.postgres_issuance_state import PostgresIssuanceStateRepository
from app.shared.correlation import new_correlation_id
from app.shared.types import SubscriptionSnapshotState

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = BACKEND_ROOT / "migrations" / "011_issuance_state.sql"
_KEY_PREFIX = "test_pgis_svc_"


def _database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture
def pg_url() -> str:
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL not set; skipping PostgreSQL issuance service integration")
    return url


def _apply_011() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


def _req(
    *,
    internal_user_id: str,
    op: IssuanceOperationType,
    sub: SubscriptionSnapshotState | None,
    idem: str,
    link: str | None = None,
) -> IssuanceRequest:
    return IssuanceRequest(
        internal_user_id=internal_user_id,
        subscription_state=sub,
        operation=op,
        idempotency_key=idem,
        correlation_id=new_correlation_id(),
        link_issue_idempotency_key=link,
    )


_FORBIDDEN = (
    "PRIVATE KEY",
    "BEGIN ",
    "token=",
    "postgres://",
    "postgresql://",
    "Bearer ",
    "vpn://",
)


def _assert_no_forbidden(s: str) -> None:
    u = s.upper()
    for frag in _FORBIDDEN:
        assert frag not in u


def test_postgres_issuance_service_duplicate_issue_second_instance_no_provider_call(pg_url: str) -> None:
    uid = f"{_KEY_PREFIX}u-dup"
    ikey = f"{_KEY_PREFIX}ik-dup"

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM issuance_state WHERE internal_user_id = $1::text", uid)
            repo = PostgresIssuanceStateRepository(pool)
            p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
            svc1 = IssuanceService(p, operational_state=repo)
            a = await svc1.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            assert a.category is IssuanceOutcomeCategory.ISSUED
            assert p.create_or_ensure_calls == 1
            svc2 = IssuanceService(p, operational_state=repo)
            b = await svc2.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            assert b.category is IssuanceOutcomeCategory.ALREADY_ISSUED
            assert a.safe_ref == b.safe_ref
            assert p.create_or_ensure_calls == 1
            _assert_no_forbidden(a.safe_ref or "")
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_service_revoke_second_instance_after_issue_first(pg_url: str) -> None:
    uid = f"{_KEY_PREFIX}u-rev-cross"
    ikey = f"{_KEY_PREFIX}ik-rev-cross"

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM issuance_state WHERE internal_user_id = $1::text", uid)
            repo = PostgresIssuanceStateRepository(pool)
            p1 = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
            svc1 = IssuanceService(p1, operational_state=repo)
            await svc1.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            p2 = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
            svc2 = IssuanceService(p2, operational_state=repo)
            r = await svc2.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.REVOKE,
                    sub=SubscriptionSnapshotState.INACTIVE,
                    idem="rev-cross-1",
                    link=ikey,
                )
            )
            assert r.category is IssuanceOutcomeCategory.REVOKED
            assert p2.revoke_access_calls == 1
            row = await repo.fetch_by_issue_keys(internal_user_id=uid, issue_idempotency_key=ikey)
            assert row is not None
            assert row.state is IssuanceStatePersistence.REVOKED
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_service_idempotent_issue_does_not_overwrite_ref(pg_url: str) -> None:
    uid = f"{_KEY_PREFIX}u-ref"
    ikey = f"{_KEY_PREFIX}ik-ref"
    first_ref = f"issuance-ref:fake:{_KEY_PREFIX}first"[:64]
    alt_ref = f"issuance-ref:fake:{_KEY_PREFIX}alt-different"[:64]

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM issuance_state WHERE internal_user_id = $1::text", uid)
            repo = PostgresIssuanceStateRepository(pool)
            p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)

            class _FixedRefProvider(FakeIssuanceProvider):
                def __init__(self, ref: str) -> None:
                    super().__init__(FakeProviderMode.SUCCESS)
                    self._fixed_ref = ref

                async def create_or_ensure_access(
                    self,
                    *,
                    internal_user_id: str,
                    idempotency_key: str,
                    correlation_id: str,
                ) -> ProviderCreateResult:
                    self.create_or_ensure_calls += 1
                    return ProviderCreateResult(
                        outcome=CreateAccessOutcome.SUCCESS, issuance_ref=self._fixed_ref
                    )

            p_a = _FixedRefProvider(first_ref)
            svc_a = IssuanceService(p_a, operational_state=repo)
            a = await svc_a.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            assert a.safe_ref == first_ref
            p_b = _FixedRefProvider(alt_ref)
            svc_b = IssuanceService(p_b, operational_state=repo)
            b = await svc_b.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            assert b.category is IssuanceOutcomeCategory.ALREADY_ISSUED
            assert b.safe_ref == first_ref
            assert p_b.create_or_ensure_calls == 0
        finally:
            await pool.close()

    asyncio.run(main())


def test_postgres_issuance_service_resend_second_instance_after_issue_first(pg_url: str) -> None:
    uid = f"{_KEY_PREFIX}u-resend-cross"
    ikey = f"{_KEY_PREFIX}ik-resend-cross"

    async def main() -> None:
        pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute(_apply_011())
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM issuance_state WHERE internal_user_id = $1::text", uid)
            repo = PostgresIssuanceStateRepository(pool)
            p1 = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
            svc1 = IssuanceService(p1, operational_state=repo)
            issued = await svc1.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.ISSUE,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem=ikey,
                )
            )
            assert issued.category is IssuanceOutcomeCategory.ISSUED
            p2 = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
            svc2 = IssuanceService(p2, operational_state=repo)
            resend = await svc2.execute(
                _req(
                    internal_user_id=uid,
                    op=IssuanceOperationType.RESEND,
                    sub=SubscriptionSnapshotState.ACTIVE,
                    idem="resend-cross-1",
                    link=ikey,
                )
            )
            assert resend.category is IssuanceOutcomeCategory.DELIVERY_READY
            assert p2.get_safe_delivery_calls == 1
            assert resend.safe_ref is not None
            _assert_no_forbidden(resend.safe_ref)
        finally:
            await pool.close()

    asyncio.run(main())
