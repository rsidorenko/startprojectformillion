"""Unit tests for :class:`Adm01SubscriptionPolicyReadAdapter` (no DB/network)."""

from __future__ import annotations

import pytest

from app.admin_support.adm01_subscription_policy_read_adapter import (
    Adm01SubscriptionPolicyReadAdapter,
)
from app.admin_support.contracts import AdminPolicyFlag
from app.application.interfaces import SubscriptionSnapshot
from app.security.errors import InternalErrorCategory, PersistenceDependencyError

_FORBIDDEN_MARKERS = (
    "provider_issuance_ref",
    "issue_idempotency_key",
    "internal_fact_ref",
    "external_event_id",
    "DATABASE_URL",
    "postgres://",
    "postgresql://",
    "Bearer ",
    "PRIVATE KEY",
    "raw-billing-payload",
)


class _FakeSnapshots:
    def __init__(self, current: SubscriptionSnapshot | None) -> None:
        self._current = current

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        del internal_user_id
        return self._current


class _ErrorSnapshots:
    def __init__(self, err: Exception) -> None:
        self._err = err

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        del internal_user_id
        raise self._err


def _assert_no_forbidden_markers(text: str) -> None:
    for marker in _FORBIDDEN_MARKERS:
        assert marker not in text


@pytest.mark.asyncio
async def test_missing_snapshot_maps_to_unknown_fail_closed() -> None:
    a = Adm01SubscriptionPolicyReadAdapter(_FakeSnapshots(None))
    out = await a.get_policy_flag("u-1")
    assert out is AdminPolicyFlag.UNKNOWN
    _assert_no_forbidden_markers(repr(out))


@pytest.mark.asyncio
async def test_needs_review_maps_to_enforce_manual_review() -> None:
    a = Adm01SubscriptionPolicyReadAdapter(
        _FakeSnapshots(SubscriptionSnapshot(internal_user_id="u-1", state_label="needs_review")),
    )
    out = await a.get_policy_flag("u-1")
    assert out is AdminPolicyFlag.ENFORCE_MANUAL_REVIEW


@pytest.mark.asyncio
async def test_known_non_review_states_map_to_default() -> None:
    for label in ("active", "inactive", "absent", "not_eligible"):
        a = Adm01SubscriptionPolicyReadAdapter(
            _FakeSnapshots(SubscriptionSnapshot(internal_user_id="u-1", state_label=label)),
        )
        out = await a.get_policy_flag("u-1")
        assert out is AdminPolicyFlag.DEFAULT


@pytest.mark.asyncio
async def test_unknown_snapshot_label_maps_to_unknown() -> None:
    a = Adm01SubscriptionPolicyReadAdapter(
        _FakeSnapshots(SubscriptionSnapshot(internal_user_id="u-1", state_label="unexpected_state")),
    )
    out = await a.get_policy_flag("u-1")
    assert out is AdminPolicyFlag.UNKNOWN


@pytest.mark.asyncio
async def test_persistence_error_propagates() -> None:
    a = Adm01SubscriptionPolicyReadAdapter(
        _ErrorSnapshots(
            PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT),
        ),
    )
    with pytest.raises(PersistenceDependencyError) as e:
        await a.get_policy_flag("u-1")
    assert e.value.category is InternalErrorCategory.PERSISTENCE_TRANSIENT
