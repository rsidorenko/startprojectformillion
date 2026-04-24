"""Slice-1 composition tests using application/bootstrap.py."""

from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest

from app.application.bootstrap import Slice1Composition, build_slice1_composition
from app.application.handlers import BootstrapIdentityInput, GetSubscriptionStatusInput
from app.application.interfaces import SubscriptionSnapshot
from app.persistence.in_memory import (
    InMemoryAuditAppender,
    InMemoryIdempotencyRepository,
    InMemorySubscriptionSnapshotReader,
    InMemoryUserIdentityRepository,
)
from app.security.idempotency import build_bootstrap_idempotency_key
from app.shared.correlation import new_correlation_id
from app.shared.types import (
    OperationOutcomeCategory,
    SafeUserStatusCategory,
    SubscriptionSnapshotState,
)


def _run(coro):
    return asyncio.run(coro)


def _allowed_composition_attrs() -> frozenset[str]:
    return frozenset(Slice1Composition.__dataclass_fields__)


def test_bootstrap_then_get_status_end_to_end() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        uid, uupd = 500, 10
        boot = await c.bootstrap.handle(
            BootstrapIdentityInput(telegram_user_id=uid, telegram_update_id=uupd, correlation_id=cid),
        )
        assert boot.outcome is OperationOutcomeCategory.SUCCESS
        assert boot.internal_user_id == f"u{uid}"
        snap = await c.snapshots.get_for_user(f"u{uid}")
        assert snap == SubscriptionSnapshot(
            internal_user_id=f"u{uid}",
            state_label=SubscriptionSnapshotState.INACTIVE.value,
        )
        st = await c.get_status.handle(GetSubscriptionStatusInput(telegram_user_id=uid, correlation_id=cid))
        assert st.outcome is OperationOutcomeCategory.SUCCESS
        assert st.safe_status is SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE

    _run(main())


def test_duplicate_bootstrap_idempotent_end_to_end() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        inp = BootstrapIdentityInput(telegram_user_id=77, telegram_update_id=3, correlation_id=cid)
        r1 = await c.bootstrap.handle(inp)
        r2 = await c.bootstrap.handle(inp)
        assert r1.outcome is r2.outcome is OperationOutcomeCategory.SUCCESS
        assert r2.idempotent_replay is True
        assert r1.internal_user_id == r2.internal_user_id
        snap = await c.snapshots.get_for_user(r1.internal_user_id or "")
        assert snap is not None
        assert snap.state_label == SubscriptionSnapshotState.INACTIVE.value

    _run(main())


def test_bootstrap_replay_put_if_absent_preserves_snapshot_state_label() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        inp = BootstrapIdentityInput(telegram_user_id=88, telegram_update_id=1, correlation_id=cid)
        await c.bootstrap.handle(inp)
        iid = "u88"
        await c.snapshots.upsert_for_tests(
            iid,
            SubscriptionSnapshot(internal_user_id=iid, state_label=SubscriptionSnapshotState.NEEDS_REVIEW.value),
        )
        r2 = await c.bootstrap.handle(inp)
        assert r2.idempotent_replay is True
        snap = await c.snapshots.get_for_user(iid)
        assert snap is not None
        assert snap.state_label == SubscriptionSnapshotState.NEEDS_REVIEW.value

    _run(main())


def test_audit_once_first_bootstrap_only() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        inp = BootstrapIdentityInput(telegram_user_id=20, telegram_update_id=7, correlation_id=cid)
        await c.bootstrap.handle(inp)
        await c.bootstrap.handle(inp)
        events = await c.audit.recorded_events()
        assert len(events) == 1
        assert events[0].operation == "uc01_bootstrap_identity"

    _run(main())


def test_status_bootstrapped_no_snapshot_fail_closed() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        uid = 33
        await c.bootstrap.handle(
            BootstrapIdentityInput(telegram_user_id=uid, telegram_update_id=1, correlation_id=cid),
        )
        st = await c.get_status.handle(GetSubscriptionStatusInput(telegram_user_id=uid, correlation_id=cid))
        assert st.outcome is OperationOutcomeCategory.SUCCESS
        assert st.safe_status is SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE

    _run(main())


def test_composition_has_no_extra_service_surface() -> None:
    c = build_slice1_composition()
    allowed = _allowed_composition_attrs()
    assert {f.name for f in fields(c)} == allowed
    assert allowed == frozenset(
        {
            "bootstrap",
            "get_status",
            "identity",
            "idempotency",
            "audit",
            "snapshots",
            "outbound_delivery",
        },
    )
    for name in allowed:
        assert "billing" not in name
        assert "issuance" not in name
        assert "admin" not in name


def test_explicit_identity_requires_snapshots_reader() -> None:
    with pytest.raises(ValueError, match="snapshots must be provided"):
        build_slice1_composition(
            identity=InMemoryUserIdentityRepository(),
            idempotency=InMemoryIdempotencyRepository(),
        )


def test_snapshots_reader_rejected_without_explicit_identity_pair() -> None:
    with pytest.raises(ValueError, match="snapshots must be omitted"):
        build_slice1_composition(snapshots=InMemorySubscriptionSnapshotReader())


def test_audit_rejected_without_explicit_identity_pair() -> None:
    with pytest.raises(ValueError, match="audit must be omitted"):
        build_slice1_composition(audit=InMemoryAuditAppender())


def test_explicit_audit_instance_is_wired() -> None:
    async def main() -> None:
        custom = InMemoryAuditAppender()
        c = build_slice1_composition(
            identity=InMemoryUserIdentityRepository(),
            idempotency=InMemoryIdempotencyRepository(),
            snapshots=InMemorySubscriptionSnapshotReader(),
            audit=custom,
        )
        assert c.audit is custom
        cid = new_correlation_id()
        await c.bootstrap.handle(
            BootstrapIdentityInput(telegram_user_id=9001, telegram_update_id=2, correlation_id=cid),
        )
        events = await custom.recorded_events()
        assert len(events) == 1

    _run(main())


def test_idempotency_key_stable_for_replay() -> None:
    """Same Telegram ids produce same idempotency key (replay detection)."""

    k1 = build_bootstrap_idempotency_key(1, 5)
    k2 = build_bootstrap_idempotency_key(1, 5)
    assert k1 == k2
