"""ADM-01 policy read: derive low-cardinality policy flag from subscription snapshot semantics."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.admin_support.contracts import AdminPolicyFlag, Adm01PolicyReadPort
from app.application.interfaces import SubscriptionSnapshot
from app.shared.types import SubscriptionSnapshotState


@runtime_checkable
class _SubscriptionSnapshotReader(Protocol):
    """Tests may inject fakes; production uses :class:`PostgresSubscriptionSnapshotReader`."""

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None: ...


class Adm01SubscriptionPolicyReadAdapter(Adm01PolicyReadPort):
    """
    Map subscription snapshot state to an ADM-01 policy flag.

    Fail-closed policy:
    - missing snapshot -> UNKNOWN
    - unknown/non-enumerated state labels -> UNKNOWN
    - NEEDS_REVIEW -> ENFORCE_MANUAL_REVIEW
    - all known non-review states -> DEFAULT
    """

    def __init__(self, snapshots: _SubscriptionSnapshotReader) -> None:
        self._snapshots = snapshots

    async def get_policy_flag(self, internal_user_id: str) -> AdminPolicyFlag:
        snapshot = await self._snapshots.get_for_user(internal_user_id)
        if snapshot is None:
            return AdminPolicyFlag.UNKNOWN

        try:
            state = SubscriptionSnapshotState(snapshot.state_label)
        except ValueError:
            return AdminPolicyFlag.UNKNOWN

        if state is SubscriptionSnapshotState.NEEDS_REVIEW:
            return AdminPolicyFlag.ENFORCE_MANUAL_REVIEW

        if state in (
            SubscriptionSnapshotState.ACTIVE,
            SubscriptionSnapshotState.INACTIVE,
            SubscriptionSnapshotState.ABSENT,
            SubscriptionSnapshotState.NOT_ELIGIBLE,
        ):
            return AdminPolicyFlag.DEFAULT

        return AdminPolicyFlag.UNKNOWN
