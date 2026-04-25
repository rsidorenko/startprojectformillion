"""
IssuanceService + optional operational state port (in-memory fake store).

RESEND remains process-local only: ``test_resend_not_hydrated_from_durable_store`` documents
that a second service instance does not see durable ISSUE for resend without in-memory ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.issuance.contracts import (
    IssuanceOperationType,
    IssuanceOutcomeCategory,
    IssuanceRequest,
)
from app.issuance.fake_provider import FakeIssuanceProvider, FakeProviderMode
from app.issuance.service import IssuanceService
from app.persistence.issuance_state_record import IssuanceStatePersistence, IssuanceStateRow
from app.security.errors import InternalErrorCategory, PersistenceDependencyError
from app.shared.correlation import new_correlation_id
from app.shared.types import SubscriptionSnapshotState


def _req(
    *,
    op: IssuanceOperationType,
    sub: SubscriptionSnapshotState | None,
    idem: str,
    link: str | None = None,
) -> IssuanceRequest:
    return IssuanceRequest(
        internal_user_id="user-1",
        subscription_state=sub,
        operation=op,
        idempotency_key=idem,
        correlation_id=new_correlation_id(),
        link_issue_idempotency_key=link,
    )


def _now_row(
    *,
    uid: str,
    ikey: str,
    ref: str,
    state: IssuanceStatePersistence,
    revoked_at: datetime | None = None,
) -> IssuanceStateRow:
    now = datetime.now(timezone.utc)
    return IssuanceStateRow(
        internal_user_id=uid,
        issue_idempotency_key=ikey,
        state=state,
        provider_issuance_ref=ref,
        created_at=now,
        updated_at=now,
        revoked_at=revoked_at,
    )


class FakeIssuanceOperationalState:
    """In-memory stand-in for Postgres semantics (tests only)."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], IssuanceStateRow] = {}
        self.fetch_calls = 0
        self.issue_or_get_calls = 0
        self.mark_revoked_calls = 0
        self.fail_on_fetch = False
        self.fail_on_issue_or_get = False
        self.fail_on_mark_revoked = False

    async def fetch_by_issue_keys(
        self, *, internal_user_id: str, issue_idempotency_key: str
    ) -> IssuanceStateRow | None:
        self.fetch_calls += 1
        if self.fail_on_fetch:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT)
        return self.rows.get((internal_user_id, issue_idempotency_key))

    async def issue_or_get(
        self,
        *,
        internal_user_id: str,
        issue_idempotency_key: str,
        provider_issuance_ref: str,
    ) -> IssuanceStateRow:
        self.issue_or_get_calls += 1
        if self.fail_on_issue_or_get:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT)
        k = (internal_user_id, issue_idempotency_key)
        if k in self.rows:
            return self.rows[k]
        row = _now_row(
            uid=internal_user_id,
            ikey=issue_idempotency_key,
            ref=provider_issuance_ref,
            state=IssuanceStatePersistence.ISSUED,
        )
        self.rows[k] = row
        return row

    async def mark_revoked(
        self, *, internal_user_id: str, issue_idempotency_key: str
    ) -> IssuanceStateRow | None:
        self.mark_revoked_calls += 1
        if self.fail_on_mark_revoked:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT)
        k = (internal_user_id, issue_idempotency_key)
        cur = self.rows.get(k)
        if cur is None:
            return None
        if cur.state is IssuanceStatePersistence.REVOKED:
            return cur
        now = datetime.now(timezone.utc)
        updated = IssuanceStateRow(
            internal_user_id=cur.internal_user_id,
            issue_idempotency_key=cur.issue_idempotency_key,
            state=IssuanceStatePersistence.REVOKED,
            provider_issuance_ref=cur.provider_issuance_ref,
            created_at=cur.created_at,
            updated_at=now,
            revoked_at=now,
        )
        self.rows[k] = updated
        return updated


@pytest.mark.asyncio
async def test_issue_persists_only_after_provider_success() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    svc = IssuanceService(p, operational_state=st)
    r = await svc.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem="ik-persist-1")
    )
    assert r.category is IssuanceOutcomeCategory.ISSUED
    assert st.issue_or_get_calls == 1
    assert p.create_or_ensure_calls == 1


@pytest.mark.asyncio
async def test_provider_unknown_does_not_persist() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.UNKNOWN)
    st = FakeIssuanceOperationalState()
    svc = IssuanceService(p, operational_state=st)
    r = await svc.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem="ik-no-persist")
    )
    assert r.category is IssuanceOutcomeCategory.INTERNAL_ERROR
    assert st.issue_or_get_calls == 0
    assert st.rows == {}


@pytest.mark.asyncio
async def test_duplicate_issue_skips_provider_when_store_has_issued_row() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    svc = IssuanceService(p, operational_state=st)
    ikey = "ik-dup-store"
    a = await svc.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem=ikey)
    )
    assert a.category is IssuanceOutcomeCategory.ISSUED
    assert p.create_or_ensure_calls == 1
    b = await svc.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem=ikey)
    )
    assert b.category is IssuanceOutcomeCategory.ALREADY_ISSUED
    assert a.safe_ref == b.safe_ref
    assert p.create_or_ensure_calls == 1
    assert st.issue_or_get_calls == 1


@pytest.mark.asyncio
async def test_issue_or_get_failure_after_provider_success_fail_closed() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    st.fail_on_issue_or_get = True
    svc = IssuanceService(p, operational_state=st)
    r = await svc.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem="ik-fail-persist")
    )
    assert r.category is IssuanceOutcomeCategory.INTERNAL_ERROR
    assert p.create_or_ensure_calls == 1
    assert st.issue_or_get_calls == 1
    st.fail_on_issue_or_get = False
    svc2 = IssuanceService(p, operational_state=st)
    r2 = await svc2.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem="ik-fail-persist")
    )
    assert r2.category is IssuanceOutcomeCategory.ISSUED
    assert st.issue_or_get_calls == 2


@pytest.mark.asyncio
async def test_revoke_calls_mark_revoked_and_is_idempotent() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    svc = IssuanceService(p, operational_state=st)
    ikey = "ik-rev-store"
    await svc.execute(_req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem=ikey))
    assert st.mark_revoked_calls == 0
    a = await svc.execute(
        _req(
            op=IssuanceOperationType.REVOKE,
            sub=SubscriptionSnapshotState.INACTIVE,
            idem="rev-1",
            link=ikey,
        )
    )
    assert a.category is IssuanceOutcomeCategory.REVOKED
    assert st.mark_revoked_calls == 1
    b = await svc.execute(
        _req(
            op=IssuanceOperationType.REVOKE,
            sub=SubscriptionSnapshotState.INACTIVE,
            idem="rev-1",
            link=ikey,
        )
    )
    assert b.category is IssuanceOutcomeCategory.REVOKED
    assert st.mark_revoked_calls == 1


@pytest.mark.asyncio
async def test_revoke_from_store_only_row_no_provider_second_time() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    ikey = "ik-cold-rev"
    ref = "issuance-ref:fake:preseed"
    st.rows[("user-1", ikey)] = _now_row(
        uid="user-1", ikey=ikey, ref=ref, state=IssuanceStatePersistence.ISSUED
    )
    svc = IssuanceService(p, operational_state=st)
    await svc.execute(
        _req(
            op=IssuanceOperationType.REVOKE,
            sub=SubscriptionSnapshotState.INACTIVE,
            idem="r-only",
            link=ikey,
        )
    )
    assert p.revoke_access_calls == 1
    assert st.mark_revoked_calls == 1


@pytest.mark.asyncio
async def test_revoke_idempotent_when_store_already_revoked() -> None:
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    ikey = "ik-already-rev"
    ref = "issuance-ref:fake:revoked-at-rest"
    now = datetime.now(timezone.utc)
    st.rows[("user-1", ikey)] = IssuanceStateRow(
        internal_user_id="user-1",
        issue_idempotency_key=ikey,
        state=IssuanceStatePersistence.REVOKED,
        provider_issuance_ref=ref,
        created_at=now,
        updated_at=now,
        revoked_at=now,
    )
    svc = IssuanceService(p, operational_state=st)
    r = await svc.execute(
        _req(
            op=IssuanceOperationType.REVOKE,
            sub=SubscriptionSnapshotState.INACTIVE,
            idem="r-idem",
            link=ikey,
        )
    )
    assert r.category is IssuanceOutcomeCategory.REVOKED
    assert p.revoke_access_calls == 0
    assert st.mark_revoked_calls == 0


@pytest.mark.asyncio
async def test_resend_not_hydrated_from_durable_store_process_local_resend_slice() -> None:
    """Durable ISSUE does not populate process-local ledger for a new IssuanceService instance."""
    p = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    st = FakeIssuanceOperationalState()
    svc1 = IssuanceService(p, operational_state=st)
    ikey = "ik-resend-boundary"
    await svc1.execute(
        _req(op=IssuanceOperationType.ISSUE, sub=SubscriptionSnapshotState.ACTIVE, idem=ikey)
    )
    p2 = FakeIssuanceProvider(FakeProviderMode.SUCCESS)
    svc2 = IssuanceService(p2, operational_state=st)
    r = await svc2.execute(
        _req(
            op=IssuanceOperationType.RESEND,
            sub=SubscriptionSnapshotState.ACTIVE,
            idem="rs-1",
            link=ikey,
        )
    )
    assert r.category is IssuanceOutcomeCategory.UNSAFE_TO_DELIVER
    assert p2.get_safe_delivery_calls == 0
