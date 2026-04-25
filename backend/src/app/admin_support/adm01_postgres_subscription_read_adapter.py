"""ADM-01 subscription read: project persisted snapshot to admin-safe subscription summary."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.admin_support.contracts import Adm01SubscriptionReadPort
from app.application.interfaces import SubscriptionSnapshot


@runtime_checkable
class _SubscriptionSnapshotReader(Protocol):
    """Tests may inject fakes; production uses :class:`PostgresSubscriptionSnapshotReader`."""

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None: ...


class Adm01PostgresSubscriptionReadAdapter(Adm01SubscriptionReadPort):
    """
    Reuses subscription snapshot reader semantics for ADM-01 lookup.

    Missing snapshot returns ``None`` to preserve existing endpoint projection
    (`internal_user_id`/`subscription_state_label` become `null`).
    """

    def __init__(self, snapshots: _SubscriptionSnapshotReader) -> None:
        self._snapshots = snapshots

    async def get_subscription_snapshot(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        return await self._snapshots.get_for_user(internal_user_id)
