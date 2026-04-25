"""Thin slice-1 composition: in-memory adapters + UC-01 / UC-02 handlers (no framework, no transport)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from app.application.handlers import BootstrapIdentityHandler, GetSubscriptionStatusHandler
from app.application.telegram_access_resend import (
    AccessResendCooldownStore,
    InMemoryAccessResendCooldownStore,
    IssuanceStateForResendLookup,
    TelegramAccessResendDisabledHitMarker,
    TelegramAccessResendHandler,
    telegram_access_resend_enabled_from_env,
)
from app.application.interfaces import (
    AuditAppender,
    IdempotencyRepository,
    OutboundDeliveryLedger,
    SubscriptionSnapshot,
    SubscriptionSnapshotReader,
    SubscriptionSnapshotWriter,
    UserIdentityRepository,
)
from app.persistence.in_memory import (
    InMemoryAuditAppender,
    InMemoryIdempotencyRepository,
    InMemoryOutboundDeliveryLedger,
    InMemorySubscriptionSnapshotReader,
    InMemoryUserIdentityRepository,
)
from app.issuance.service import IssuanceService


@dataclass(frozen=True, slots=True)
class Slice1Composition:
    """Wired handlers for slice 1; shared identity store links UC-01 and UC-02."""

    bootstrap: BootstrapIdentityHandler
    get_status: GetSubscriptionStatusHandler
    identity: UserIdentityRepository
    idempotency: IdempotencyRepository
    audit: AuditAppender
    snapshots: SubscriptionSnapshotReader
    outbound_delivery: OutboundDeliveryLedger
    access_resend: TelegramAccessResendHandler


def build_slice1_composition(
    *,
    initial_snapshots: Mapping[str, SubscriptionSnapshot] | None = None,
    identity: UserIdentityRepository | None = None,
    idempotency: IdempotencyRepository | None = None,
    snapshots: SubscriptionSnapshotReader | None = None,
    audit: AuditAppender | None = None,
    outbound_delivery: OutboundDeliveryLedger | None = None,
    issuance_service: IssuanceService | None = None,
    issuance_state_lookup: IssuanceStateForResendLookup | None = None,
    resend_cooldown: AccessResendCooldownStore | None = None,
    resend_disabled_hit_marker: TelegramAccessResendDisabledHitMarker | None = None,
    access_resend_enabled: bool | None = None,
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
    delivery = outbound_delivery or InMemoryOutboundDeliveryLedger()
    cooldown = resend_cooldown or InMemoryAccessResendCooldownStore()
    enabled = (
        access_resend_enabled
        if access_resend_enabled is not None
        else telegram_access_resend_enabled_from_env(os.environ.get)
    )
    return Slice1Composition(
        bootstrap=BootstrapIdentityHandler(identity, idempotency, audit, snapshot_writer),
        get_status=GetSubscriptionStatusHandler(identity, snapshots),
        identity=identity,
        idempotency=idempotency,
        audit=audit,
        snapshots=snapshots,
        outbound_delivery=delivery,
        access_resend=TelegramAccessResendHandler(
            identity=identity,
            snapshots=snapshots,
            issuance_service=issuance_service,
            issuance_state_lookup=issuance_state_lookup,
            cooldown=cooldown,
            disabled_hit_marker=resend_disabled_hit_marker,
            enabled=enabled,
        ),
    )
