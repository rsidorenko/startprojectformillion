"""Thin slice-1 composition: in-memory adapters + UC-01 / UC-02 handlers (no framework, no transport)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from app.application.handlers import BootstrapIdentityHandler, GetSubscriptionStatusHandler
from app.application.interfaces import (
    AuditAppender,
    IdempotencyRepository,
    SubscriptionSnapshot,
    SubscriptionSnapshotReader,
    SubscriptionSnapshotWriter,
    UserIdentityRepository,
)
from app.persistence.in_memory import (
    InMemoryAuditAppender,
    InMemoryIdempotencyRepository,
    InMemorySubscriptionSnapshotReader,
    InMemoryUserIdentityRepository,
)


@dataclass(frozen=True, slots=True)
class Slice1Composition:
    """Wired handlers for slice 1; shared identity store links UC-01 and UC-02."""

    bootstrap: BootstrapIdentityHandler
    get_status: GetSubscriptionStatusHandler
    identity: UserIdentityRepository
    idempotency: IdempotencyRepository
    audit: AuditAppender
    snapshots: SubscriptionSnapshotReader


def build_slice1_composition(
    *,
    initial_snapshots: Mapping[str, SubscriptionSnapshot] | None = None,
    identity: UserIdentityRepository | None = None,
    idempotency: IdempotencyRepository | None = None,
    snapshots: SubscriptionSnapshotReader | None = None,
    audit: AuditAppender | None = None,
) -> Slice1Composition:
    if (identity is None) ^ (idempotency is None):
        raise ValueError("identity and idempotency must both be provided or both omitted")
    if identity is None:
        if snapshots is not None:
            raise ValueError("snapshots must be omitted when identity and idempotency are defaulted")
        if audit is not None:
            raise ValueError("audit must be omitted when identity and idempotency are defaulted")
        identity = InMemoryUserIdentityRepository()
        idempotency = InMemoryIdempotencyRepository()
    elif snapshots is None:
        raise ValueError("snapshots must be provided when identity and idempotency are explicit")
    if audit is None:
        audit = InMemoryAuditAppender()
    if snapshots is None:
        snapshots = InMemorySubscriptionSnapshotReader(initial_snapshots)
    snapshot_writer = cast(SubscriptionSnapshotWriter, snapshots)
    return Slice1Composition(
        bootstrap=BootstrapIdentityHandler(identity, idempotency, audit, snapshot_writer),
        get_status=GetSubscriptionStatusHandler(identity, snapshots),
        identity=identity,
        idempotency=idempotency,
        audit=audit,
        snapshots=snapshots,
    )
