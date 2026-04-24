"""Pure UC-05 apply decision (no I/O) for subscription snapshot transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.billing_apply_rules import (
    UC05_ALLOWLISTED_EVENT_TYPES,
    UC05_NO_USER_SENTINEL,
)
from app.persistence.billing_events_ledger_contracts import (
    BillingEventLedgerRecord,
    BillingEventLedgerStatus,
)
from app.persistence.billing_subscription_apply_contracts import (
    BillingSubscriptionApplyOutcome,
    BillingSubscriptionApplyReason,
)
from app.shared.types import SubscriptionSnapshotState


class UC05ApplyPath(str, Enum):
    """Result path before durable persistence (handler maps to operation outcomes)."""

    FACT_NOT_FOUND = "fact_not_found"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    PERSIST = "persist"


@dataclass(frozen=True, slots=True)
class UC05PersistInstruction:
    """Durable work for a first-time apply of this internal_fact_ref."""

    internal_fact_ref: str
    # Row in billing_subscription_apply_records (NOT NULL user column; may be sentinel)
    record_internal_user_id: str
    apply_outcome: BillingSubscriptionApplyOutcome
    reason: BillingSubscriptionApplyReason
    # If set, upsert subscription_snapshots to this state_label (UserSnapshotState value string)
    snapshot_state_label: str | None
    # Audit: internal user from ledger (optional)
    audit_internal_user_id: str | None
    billing_provider_key: str
    external_event_id: str
    event_type: str
    billing_event_status: str


def first_time_decision(
    fact: BillingEventLedgerRecord,
) -> UC05PersistInstruction:
    """Compute durable apply for a fact that is not yet present in idempotency store.

    Precondition: caller has verified no idempotency row for ``fact.internal_fact_ref`` yet.
    """
    st = fact.status
    if st is not BillingEventLedgerStatus.ACCEPTED:
        return UC05PersistInstruction(
            internal_fact_ref=fact.internal_fact_ref,
            record_internal_user_id=UC05_NO_USER_SENTINEL
            if fact.internal_user_id is None
            else fact.internal_user_id,
            apply_outcome=BillingSubscriptionApplyOutcome.NO_ACTIVATION,
            reason=BillingSubscriptionApplyReason.LEDGER_STATUS_NOT_ACCEPTED,
            snapshot_state_label=None,
            audit_internal_user_id=fact.internal_user_id,
            billing_provider_key=fact.billing_provider_key,
            external_event_id=fact.external_event_id,
            event_type=fact.event_type,
            billing_event_status=st.value,
        )

    if not fact.internal_user_id:
        return UC05PersistInstruction(
            internal_fact_ref=fact.internal_fact_ref,
            record_internal_user_id=UC05_NO_USER_SENTINEL,
            apply_outcome=BillingSubscriptionApplyOutcome.NEEDS_REVIEW,
            reason=BillingSubscriptionApplyReason.MISSING_INTERNAL_USER,
            snapshot_state_label=None,
            audit_internal_user_id=None,
            billing_provider_key=fact.billing_provider_key,
            external_event_id=fact.external_event_id,
            event_type=fact.event_type,
            billing_event_status=st.value,
        )

    uid = fact.internal_user_id
    if fact.event_type not in UC05_ALLOWLISTED_EVENT_TYPES:
        return UC05PersistInstruction(
            internal_fact_ref=fact.internal_fact_ref,
            record_internal_user_id=uid,
            apply_outcome=BillingSubscriptionApplyOutcome.NEEDS_REVIEW,
            reason=BillingSubscriptionApplyReason.UNKNOWN_EVENT_TYPE,
            snapshot_state_label=SubscriptionSnapshotState.NEEDS_REVIEW.value,
            audit_internal_user_id=uid,
            billing_provider_key=fact.billing_provider_key,
            external_event_id=fact.external_event_id,
            event_type=fact.event_type,
            billing_event_status=st.value,
        )

    return UC05PersistInstruction(
        internal_fact_ref=fact.internal_fact_ref,
        record_internal_user_id=uid,
        apply_outcome=BillingSubscriptionApplyOutcome.ACTIVE_APPLIED,
        reason=BillingSubscriptionApplyReason.OK,
        snapshot_state_label=SubscriptionSnapshotState.ACTIVE.value,
        audit_internal_user_id=uid,
        billing_provider_key=fact.billing_provider_key,
        external_event_id=fact.external_event_id,
        event_type=fact.event_type,
        billing_event_status=st.value,
    )
